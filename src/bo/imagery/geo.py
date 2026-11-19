"""Local UTM chip grids and coordinate transforms."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from affine import Affine
from pyproj import Transformer

from .config import DEFAULT_CHIP_SIZE, DEFAULT_RES_M


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the UTM zone containing the point (WGS84, north or south)."""
    zone = int(np.floor((lon + 180.0) / 6.0)) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


_TRANSFORMERS: dict[tuple[int, int, bool], Transformer] = {}


def transformer(src_epsg: int, dst_epsg: int) -> Transformer:
    key = (src_epsg, dst_epsg, True)
    if key not in _TRANSFORMERS:
        _TRANSFORMERS[key] = Transformer.from_crs(src_epsg, dst_epsg, always_xy=True)
    return _TRANSFORMERS[key]


@dataclass(frozen=True)
class ChipGrid:
    """A square chip on the local UTM grid. The origin is snapped to a multiple of ``res``."""

    epsg: int
    transform: Affine
    size: int
    res: float

    @property
    def shape(self) -> tuple[int, int]:
        return (self.size, self.size)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(left, bottom, right, top) in projected metres."""
        left = self.transform.c
        top = self.transform.f
        return (left, top - self.size * self.res, left + self.size * self.res, top)

    def pixel_center_xy(self, row: int, col: int) -> tuple[float, float]:
        x, y = self.transform @ (col + 0.5, row + 0.5)
        return float(x), float(y)

    def pixel_center_lonlat(self, row: int, col: int) -> tuple[float, float]:
        x, y = self.pixel_center_xy(row, col)
        lon, lat = transformer(self.epsg, 4326).transform(x, y)
        return float(lon), float(lat)

    def lonlat_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        """Fractional (row, col) of a lon/lat point; may lie outside the chip."""
        x, y = transformer(4326, self.epsg).transform(lon, lat)
        col, row = ~self.transform @ (x, y)
        return float(row), float(col)

    def bounds_lonlat(self) -> tuple[float, float, float, float]:
        """Lon/lat bounding box (min lon, min lat, max lon, max lat) of the chip corners."""
        l, b, r, t = self.bounds
        tr = transformer(self.epsg, 4326)
        xs, ys = tr.transform([l, r, l, r], [b, b, t, t])
        return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))

    def xy_coords(self) -> tuple[np.ndarray, np.ndarray]:
        """Pixel-centre x (columns) and y (rows) coordinates."""
        xs = self.transform.c + (np.arange(self.size) + 0.5) * self.res
        ys = self.transform.f - (np.arange(self.size) + 0.5) * self.res
        return xs, ys


def chip_grid(
    lon: float,
    lat: float,
    size: int = DEFAULT_CHIP_SIZE,
    res: float = DEFAULT_RES_M,
    epsg: int | None = None,
) -> ChipGrid:
    """Chip of ``size`` x ``size`` pixels centred on (lon, lat) on the local UTM grid.

    The upper-left corner is snapped to a multiple of ``res`` so that the chip aligns with the
    Sentinel-2 and Sentinel-1 RTC grids (both on 10 m multiples in UTM).
    """
    epsg = epsg or utm_epsg(lon, lat)
    x, y = transformer(4326, epsg).transform(lon, lat)
    half = size * res / 2.0
    left = np.round((x - half) / res) * res
    top = np.round((y + half) / res) * res
    return ChipGrid(epsg=epsg, transform=Affine(res, 0.0, left, 0.0, -res, top), size=size, res=res)
