"""Windowed reads of cloud-optimised GeoTIFFs onto a chip grid, and Planetary Computer access."""

from __future__ import annotations

import os
import time

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window

from .config import PC_STAC
from .geo import ChipGrid
from .quota import GLOBAL, Counters

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "GDAL_HTTP_TIMEOUT": "60",
    "VSI_CACHE": "TRUE",
    "GDAL_NUM_THREADS": "1",
}


def stac_client() -> pystac_client.Client:
    """Anonymous PC STAC client. Hrefs are signed at read time (tokens last about 40 minutes)."""
    return pystac_client.Client.open(PC_STAC)


def signed(href: str, counters: Counters = GLOBAL) -> str:
    """Signed href; the planetary_computer package caches the SAS token until it expires."""
    return pc.sign(href)


def read_on_grid(
    href: str,
    grid: ChipGrid,
    resampling: Resampling = Resampling.nearest,
    fill_value: float = 0,
    counters: Counters = GLOBAL,
    sign: bool = True,
    band: int = 1,
    pad: int = 0,
    retries: int = 3,
) -> np.ndarray:
    """Read ``band`` of a COG onto ``grid`` (optionally padded by ``pad`` pixels all round).

    Same CRS as the grid: one windowed read with ``out_shape`` (nearest by default, so 20 m
    layers are replicated onto the 10 m grid and no values are invented). Different CRS (a tile
    from the neighbouring UTM zone): a warped read. Outside the raster the result is
    ``fill_value`` (boundless).
    """
    n = grid.size + 2 * pad
    l, b, r, t = grid.bounds
    pl, pb, pr, pt = l - pad * grid.res, b - pad * grid.res, r + pad * grid.res, t + pad * grid.res
    last: Exception | None = None
    for attempt in range(retries):
        try:
            url = signed(href, counters) if sign else href
            with rasterio.Env(**GDAL_ENV), rasterio.open(url) as src:
                counters.add(cog_opens=1)
                if src.crs is not None and src.crs.to_epsg() == grid.epsg:
                    inv = ~src.transform
                    c_a, r_a = inv @ (pl, pt)
                    c_b, r_b = inv @ (pr, pb)
                    win = Window(min(c_a, c_b), min(r_a, r_b), abs(c_b - c_a), abs(r_b - r_a))
                    arr = src.read(
                        band, window=win, out_shape=(n, n), resampling=resampling,
                        boundless=True, fill_value=fill_value,
                    )
                    if src.transform.e > 0:  # south-up raster (seen in some RTC scenes): flip
                        arr = arr[::-1]
                    if src.transform.a < 0:  # east-west flipped, not seen, handled for safety
                        arr = arr[:, ::-1]
                else:
                    from affine import Affine

                    tr = Affine(grid.res, 0, pl, 0, -grid.res, pt)
                    with WarpedVRT(
                        src, crs=f"EPSG:{grid.epsg}", transform=tr, width=n, height=n,
                        resampling=resampling, nodata=fill_value, add_alpha=False,
                        src_nodata=src.nodata if src.nodata is not None else fill_value,
                    ) as vrt:
                        arr = vrt.read(band)
                counters.add(cog_window_reads=1, decoded_bytes=int(arr.nbytes))
                return arr
        except (rasterio.errors.RasterioError, OSError, ValueError) as e:  # network, expired token
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"read failed for {href.split('?')[0]}: {last}")


def default_workers() -> int:
    return int(os.environ.get("BO_IMAGERY_WORKERS", "12"))
