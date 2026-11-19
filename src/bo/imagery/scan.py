"""Track A national scan: streaming per-tile monthly change features, candidates only.

For each MGRS tile and month the pipeline reads Sentinel-2 L2A COGs from Planetary Computer in
row strips, builds the monthly median of clear pixels (SCL rule of A5, per-item offset of R5),
derives NDVI and SWIR (B11) per month and keeps only candidate polygons with their monthly feature
series. No scene is stored. To limit bytes it reads a reduced band set (B04, B08, B11, SCL) at
20 m through the COG overviews (``scale`` 2). 20 m pixels are 400 m2, so a 1 MW battery site of
a few hundred m2 is at or below the detection limit of this scan (R2); the scan is therefore a
benchmark of cost and of the streaming design, and its candidates are labelled *detected*, not
validated.

Candidate rule (parameters in ``ScanConfig``, fixed before any result was inspected): a pixel is a
candidate when its median NDVI over the first ``n_base`` months is at least ``ndvi_base_min``
(vegetated land) and its NDVI over the last ``n_recent`` months falls at least ``ndvi_drop``
below that, with at least ``min_clear_months`` valid months in each window, and the B11 median
does not fall. Connected pixels (8-neighbourhood) of at least ``min_px`` pixels form a candidate.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from functools import partial

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.enums import Resampling
from rasterio.windows import Window
from scipy import ndimage
from shapely.geometry import shape

from bo import paths

from .composite import masked_median, month_index
from .config import PC_S2
from .io import GDAL_ENV, signed, stac_client
from .masking import clear_mask
from .netcount import ensure_proxy
from .quota import GLOBAL, Stage
from .reflectance import dn_to_reflectance

BANDS = ("B04", "B08", "B11")


@dataclass(frozen=True)
class ScanConfig:
    scale: int = 2  # 1 = 10 m, 2 = 20 m (reads the overview)
    strip_rows: int = 512  # output rows per strip, aligned to the COG block size at 20 m
    max_scene_cloud: float = 60.0  # scene-level eo:cloud_cover filter from STAC (no bytes)
    n_base: int = 3
    n_recent: int = 3
    ndvi_base_min: float = 0.4
    ndvi_drop: float = 0.25
    min_clear_months: int = 2
    min_px: int = 4
    max_px: int = 40_000


def ndvi(b04: np.ndarray, b08: np.ndarray) -> np.ndarray:
    s = b08 + b04
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(s > 0, (b08 - b04) / s, np.nan).astype(np.float32)


def candidate_mask(ndvi_ts: np.ndarray, b11_ts: np.ndarray, cfg: ScanConfig) -> np.ndarray:
    """ndvi_ts, b11_ts: (T, H, W) monthly medians with NaN for missing months."""
    base = ndvi_ts[: cfg.n_base]
    rec = ndvi_ts[-cfg.n_recent:]
    nb = np.isfinite(base).sum(0)
    nr = np.isfinite(rec).sum(0)
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mb = np.nanmedian(base, axis=0)
            mr = np.nanmedian(rec, axis=0)
            sb = np.nanmedian(b11_ts[: cfg.n_base], axis=0)
            sr = np.nanmedian(b11_ts[-cfg.n_recent:], axis=0)
    ok = (nb >= cfg.min_clear_months) & (nr >= cfg.min_clear_months)
    return ok & (mb >= cfg.ndvi_base_min) & ((mb - mr) >= cfg.ndvi_drop) & (sr >= sb)


def label_components(mask: np.ndarray, cfg: ScanConfig):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return lab, np.array([], int)
    sizes = np.bincount(lab.ravel())[1:]
    keep = np.nonzero((sizes >= cfg.min_px) & (sizes <= cfg.max_px))[0] + 1
    return lab, keep


def tile_windows(part_xy_bounds, transform, shape_hw, scale: int):
    """Row/column range of a 20 m (``scale`` * 10 m) grid covering the projected bounds."""
    res = 10.0 * scale
    x0, y0, x1, y1 = part_xy_bounds
    c0 = max(int(np.floor((x0 - transform.c) / res)), 0)
    c1 = min(int(np.ceil((x1 - transform.c) / res)), shape_hw[1])
    r0 = max(int(np.floor((transform.f - y1) / res)), 0)
    r1 = min(int(np.ceil((transform.f - y0) / res)), shape_hw[0])
    return r0, r1, c0, c1


def _read(href, window10, out_hw, resampling):
    """One windowed read at the output size; GDAL picks the overview."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(signed(href)) as src:
        GLOBAL.add(cog_opens=1)
        arr = src.read(1, window=window10, out_shape=out_hw, resampling=resampling,
                       boundless=True, fill_value=0)
    GLOBAL.add(cog_window_reads=1, decoded_bytes=int(arr.nbytes))
    return arr


def read_scene_strip(item, r0, r1, c0, c1, cfg: ScanConfig, tile_shape10=None):
    """SCL, B04, B08, B11 for rows r0:r1, cols c0:c1 of the 20 m grid, as reflectance."""
    s = cfg.scale
    win10 = Window(c0 * s, r0 * s, (c1 - c0) * s, (r1 - r0) * s)
    hw = (r1 - r0, c1 - c0)
    scl = _read(item.assets["SCL"].href, Window(c0 * s // 2, r0 * s // 2, (c1 - c0) * s // 2,
                                                (r1 - r0) * s // 2), hw, Resampling.nearest)
    clear = clear_mask(scl, "scl_456")
    out = {"clear": clear}
    bl = item.properties.get("s2:processing_baseline")
    if not clear.any():
        return out
    for b in BANDS:
        # B04, B08 are 10 m files; B11 is a 20 m file (window in its own pixels)
        w = win10 if b != "B11" else Window(c0 * s // 2, r0 * s // 2, (c1 - c0) * s // 2,
                                            (r1 - r0) * s // 2)
        dn = _read(item.assets[b].href, w, hw, Resampling.average if b != "B11"
                   else Resampling.nearest)
        out[b] = dn_to_reflectance(dn, bl)
    return out


def scan_part(items_by_month: dict, months, part_bounds, tile_transform, tile_shape10, cfg,
              workers: int = 8):
    """Process one tile-part: returns candidate rows."""
    from concurrent.futures import ThreadPoolExecutor

    assert cfg.scale == 2, "only the 20 m overview level is implemented"
    shp = (tile_shape10[0] // cfg.scale, tile_shape10[1] // cfg.scale)
    r0, r1, c0, c1 = tile_windows(part_bounds, tile_transform, shp, cfg.scale)
    rows_all = []
    for rs in range(r0, r1, cfg.strip_rows):
        re_ = min(rs + cfg.strip_rows, r1)
        T = len(months)
        H, W = re_ - rs, c1 - c0
        nd = np.full((T, H, W), np.nan, np.float32)
        b11 = np.full((T, H, W), np.nan, np.float32)
        cnt = np.zeros((T, H, W), np.uint8)
        for ti, m in enumerate(months):
            its = items_by_month.get(str(m), [])
            if not its:
                continue
            fn = partial(read_scene_strip, r0=rs, r1=re_, c0=c0, c1=c1, cfg=cfg,
                         tile_shape10=tile_shape10)
            with ThreadPoolExecutor(workers) as ex:
                res = list(ex.map(fn, its))
            valid = np.stack([r["clear"] for r in res])
            used = [r for r in res if "B04" in r]
            if not used:
                continue
            v = np.stack([r["clear"] & np.isfinite(r["B04"]) & np.isfinite(r["B08"])
                          & np.isfinite(r["B11"]) for r in used])
            n = np.stack([ndvi(r["B04"], r["B08"]) for r in used])
            med_n, c = masked_median(n, v)
            med_s, _ = masked_median(np.stack([r["B11"] for r in used]), v)
            nd[ti], b11[ti], cnt[ti] = med_n, med_s, np.minimum(c, 255).astype(np.uint8)
            del valid
        mask = candidate_mask(nd, b11, cfg)
        lab, keep = label_components(mask, cfg)
        for k in keep:
            sel = lab == k
            poly = [shape(g) for g, _ in features.shapes(
                sel.astype(np.uint8), mask=sel,
                transform=rasterio.Affine(10.0 * cfg.scale, 0, tile_transform.c + c0 * 10.0 * cfg.scale,
                                          0, -10.0 * cfg.scale,
                                          tile_transform.f - rs * 10.0 * cfg.scale))]
            geom = poly[0] if len(poly) == 1 else poly[0].union(poly[1])
            with np.errstate(all="ignore"):
                import warnings

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    series_n = np.nanmean(nd[:, sel], axis=1)
                    series_s = np.nanmean(b11[:, sel], axis=1)
            rows_all.append({
                "geometry": geom, "n_px": int(sel.sum()),
                "ndvi_series": json.dumps([None if not np.isfinite(x) else round(float(x), 4)
                                           for x in series_n]),
                "b11_series": json.dumps([None if not np.isfinite(x) else round(float(x), 4)
                                          for x in series_s]),
                "clear_px_series": json.dumps([float(cnt[t][sel].mean()) for t in range(T)]),
            })
    return rows_all


def merge_candidates(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Merge strip fragments inside a tile (pixel-weighted) and drop tile-overlap duplicates.

    Fragments of one candidate cut by a strip border touch each other: their pixel counts add and
    their series are averaged with pixel weights. Candidates seen from two tiles (10 km overlap)
    keep the version with more pixels.
    """
    if g.empty:
        return g
    orig_crs = g.crs
    if g.crs is not None and g.crs.is_geographic:
        g = g.to_crs(25832)  # metric CRS: the 1 m touching buffer below needs metres
    out = []
    for tile, gt in g.groupby("tile"):
        gt = gt.reset_index(drop=True)
        m = gt.geometry.buffer(1.0)
        merged = gpd.GeoSeries([m.union_all()], crs=gt.crs).explode(index_parts=False).reset_index(drop=True)
        gid = np.full(len(gt), -1)
        for k, mg in enumerate(merged):
            gid[m.intersects(mg).values] = k
        for k in np.unique(gid):
            sub = gt[gid == k]
            w = sub.n_px.values.astype(float)

            def wmean(col, sub=sub, w=w):
                arr = np.array([[np.nan if x is None else x for x in json.loads(v)]
                                for v in sub[col]], float)
                ok = np.isfinite(arr)
                num = np.where(ok, arr * w[:, None], 0).sum(0)
                den = np.where(ok, w[:, None], 0).sum(0)
                with np.errstate(all="ignore"):
                    r = np.where(den > 0, num / den, np.nan)
                return json.dumps([None if not np.isfinite(x) else round(float(x), 4) for x in r])

            out.append({"geometry": sub.geometry.union_all(), "n_px": int(w.sum()), "tile": tile,
                        "ndvi_series": wmean("ndvi_series"), "b11_series": wmean("b11_series"),
                        "clear_px_series": wmean("clear_px_series")})
    res = gpd.GeoDataFrame(out, geometry="geometry", crs=g.crs).sort_values("n_px", ascending=False)
    if orig_crs is not None and orig_crs.is_geographic:
        res = res.to_crs(orig_crs)
    keep, taken = [], []
    for i, r in res.iterrows():
        if any(r.geometry.intersects(t) for t in taken):
            continue
        keep.append(i)
        taken.append(r.geometry)
    return res.loc[keep].reset_index(drop=True)


def run_scan(parts: gpd.GeoDataFrame, start: str, end: str, cfg: ScanConfig | None = None,
             stage: str = "scan_benchmark"):
    """Scan the polygons in ``parts`` (EPSG:4326). Returns (candidates GeoDataFrame, summary)."""
    cfg = cfg or ScanConfig()
    ensure_proxy()
    client = stac_client()
    months = month_index(start, end)
    t0 = time.time()
    summary = {"tiles": 0, "items_read": 0}
    cands = []
    with Stage(stage, "planetary_computer", note=f"{start}..{end} scale={cfg.scale}") as st:
        for pi, part in enumerate(parts.geometry):
            s = client.search(collections=[PC_S2], intersects=part.__geo_interface__,
                              datetime=f"{start}/{end}", limit=500,
                              query={"eo:cloud_cover": {"lt": cfg.max_scene_cloud}})
            GLOBAL.add(stac_searches=1)
            items = list(s.items())
            by_tile = defaultdict(list)
            for it in items:
                by_tile[it.properties.get("s2:mgrs_tile")].append(it)
            for tile, its in by_tile.items():
                from .s2pipe import dedupe_items

                its = dedupe_items(its)
                ibm = defaultdict(list)
                for it in its:
                    ibm[str(np.datetime64(it.datetime.replace(tzinfo=None), "M"))].append(it)
                with rasterio.Env(**GDAL_ENV), rasterio.open(
                        signed(its[0].assets["B04"].href)) as src:
                    tr10, shp10, crs = src.transform, src.shape, src.crs
                # the tile transform is at 10 m; scan grid is 10*scale
                part_m = gpd.GeoSeries([part], crs=4326).to_crs(crs).iloc[0]
                rows = scan_part(ibm, months, part_m.bounds, tr10, shp10, cfg)
                if rows:
                    g = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs).to_crs(4326)
                    g["tile"] = tile
                    cands.append(g)
                summary["tiles"] += 1
                summary["items_read"] += len(its)
    out = merge_candidates(pd.concat(cands, ignore_index=True)) if cands else gpd.GeoDataFrame()
    summary.update(elapsed_s=time.time() - t0, net_bytes=st.net_bytes, delta=st.delta,
                   n_candidates=len(out), months=len(months), scale=cfg.scale)
    return out, summary


_ = paths
