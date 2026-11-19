"""Footprint proposals on DOP chips: panel arrays, container rows and site pads (version 0).

Method (colour thresholds plus morphology, CPU only, no training data; thresholds are
assumptions recorded in ``docs/assumptions.md`` entry B-FP1):

1. The chip is block-averaged to ``WORK_RES_M`` (0.4 m) to suppress sensor noise.
2. Vegetation is removed with the excess-green index ExG = 2g - r - b on the 0..1 scaled image.
3. Three class masks on the remaining pixels:
   * ``panel_array``: dark (V < 0.45) and blue-grey (b >= r - 0.02);
   * ``container_row``: bright and unsaturated (V > 0.65, S < 0.15);
   * ``site_pad``: mid-bright, unsaturated, low local texture (bare gravel or concrete).
4. Binary opening (radius 1.2 m panels, 0.4 m containers, 1.8 m pads) removes lines and thin features (this is deliberate: the tool
   outlines extents of arrays, container rows and pads only and must never trace fences, gates
   or other protective equipment); closing joins gaps inside an array.
5. Components are polygonised, simplified, and kept if area, rectangularity (area divided by the
   area of the minimum rotated rectangle) and distance from the chip centre pass the limits.
6. Only the cluster of polygons linked to the candidate nearest the chip centre is kept
   (``cluster_only``); roofs, roads and fields elsewhere in the chip are dropped.

Output polygons carry area in m2 in the chip's projected CRS (EPSG:25832/25833, so planar area is
within about 0.1 % of true area at German latitudes) and the manual correction data model:
``polygon_id, source ("auto" | "manual"), version, is_current``. A correction made in the
labelling app is added with :func:`revise`; the earlier row is kept with ``is_current = False``.
Quantity label: detected (model output from imagery), never observed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import geopandas as gpd
import numpy as np
import pandas as pd
from affine import Affine
from rasterio import features
from scipy import ndimage as ndi
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from skimage import morphology

from bo.imagery import dop

ALGO = "thresh-morph-v0"
WORK_RES_M = 0.4
KINDS = ("panel_array", "container_row", "site_pad")


@dataclass(frozen=True)
class Params:
    exg_veg: float = 0.04
    panel_v_max: float = 0.45
    container_v_min: float = 0.65
    container_s_max: float = 0.15
    pad_v_range: tuple[float, float] = (0.30, 0.65)
    pad_s_max: float = 0.25
    pad_texture_max: float = 0.05
    open_radius_m: dict = None  # type: ignore[assignment]  # per kind, metres
    close_radius_m: float = 1.2
    min_width_m: dict = None  # type: ignore[assignment]  # short side of min rotated rectangle
    min_area_m2: dict = None  # type: ignore[assignment]
    max_area_m2: float = 150_000.0
    min_rectangularity: dict = None  # type: ignore[assignment]
    max_pad_area_m2: float = 8_000.0
    pad_max_gap_m: float = 15.0  # a pad must lie within this distance of a panel or container polygon
    max_centre_dist_m: float = 250.0
    seed_radius_m: float = 150.0  # nearest polygon within this distance of the chip centre seeds the site
    link_dist_m: float = 40.0  # polygons within this distance of the growing site are kept
    cluster_only: bool = True

    def open_radius(self, kind: str) -> float:
        d = self.open_radius_m or {"panel_array": 1.2, "container_row": 0.4, "site_pad": 1.8}
        return d[kind]

    def min_width(self, kind: str) -> float:
        d = self.min_width_m or {"panel_array": 3.0, "container_row": 2.0, "site_pad": 4.0}
        return d[kind]

    def min_rect(self, kind: str) -> float:
        d = self.min_rectangularity or {"panel_array": 0.70, "container_row": 0.60, "site_pad": 0.50}
        return d[kind]

    def min_area(self, kind: str) -> float:
        d = self.min_area_m2 or {"panel_array": 60.0, "container_row": 12.0, "site_pad": 100.0}
        return d[kind]


def block_mean(arr: np.ndarray, factor: int) -> np.ndarray:
    """Block-average a (C, H, W) array by an integer factor (crops the remainder)."""
    c, h, w = arr.shape
    h2, w2 = h // factor * factor, w // factor * factor
    a = arr[:, :h2, :w2].astype(np.float32).reshape(c, h2 // factor, factor, w2 // factor, factor)
    return a.mean(axis=(2, 4))


def class_masks(rgb01: np.ndarray, p: Params) -> dict[str, np.ndarray]:
    """Per-pixel class masks from a (3, H, W) float image scaled to 0..1."""
    r, g, b = rgb01
    v = rgb01.max(axis=0)
    mn = rgb01.min(axis=0)
    s = np.where(v > 0, (v - mn) / np.maximum(v, 1e-6), 0.0)
    exg = 2 * g - r - b
    veg = exg > p.exg_veg
    gray = rgb01.mean(axis=0)
    tex = np.sqrt(np.maximum(ndi.uniform_filter(gray**2, 5) - ndi.uniform_filter(gray, 5) ** 2, 0))
    panel = (v < p.panel_v_max) & (b >= r - 0.02) & ~veg
    container = (v > p.container_v_min) & (s < p.container_s_max) & ~veg
    pad = (~veg & ~panel & ~container & (v >= p.pad_v_range[0]) & (v <= p.pad_v_range[1])
           & (s < p.pad_s_max) & (tex < p.pad_texture_max))
    return {"panel_array": panel, "container_row": container, "site_pad": pad}


def _clean(mask: np.ndarray, res: float, p: Params, kind: str) -> np.ndarray:
    ro = max(1, round(p.open_radius(kind) / res))
    rc = max(1, round(p.close_radius_m / res))
    m = morphology.closing(mask, morphology.disk(rc))
    m = morphology.opening(m, morphology.disk(ro))
    return ndi.binary_fill_holes(m)


def short_side(geom: BaseGeometry) -> float:
    """Length of the short side of the minimum rotated rectangle (m in a projected CRS)."""
    xy = list(geom.minimum_rotated_rectangle.exterior.coords)
    e = [np.hypot(xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]) for i in range(2)]
    return float(min(e))


def rectangularity(geom: BaseGeometry) -> float:
    mrr = geom.minimum_rotated_rectangle
    return float(geom.area / mrr.area) if mrr.area > 0 else 0.0


def polygon_area_m2(geom: BaseGeometry) -> float:
    """Planar area in m2. Valid only for geometries in a projected metric CRS."""
    return float(geom.area)


def _site_cluster(rows: list[dict], centre: Point, p: Params) -> list[dict]:
    """Keep the cluster of polygons connected (gap <= link_dist_m) to the one nearest the centre.

    A chip of 640 m holds roofs, roads and fields as well as the site. The registered point lies
    on or near the site, so the nearest candidate within ``seed_radius_m`` seeds the site and the
    others join if they lie within ``link_dist_m`` of any member. No seed means no site outline.
    """
    if not rows:
        return rows
    d = [r["geometry"].distance(centre) if r["kind"] != "site_pad" else np.inf for r in rows]
    i0 = int(np.argmin(d))
    if d[i0] > p.seed_radius_m:
        return []
    members = {i0}
    changed = True
    while changed:
        changed = False
        for i, r in enumerate(rows):
            if i in members:
                continue
            if any(r["geometry"].distance(rows[j]["geometry"]) <= p.link_dist_m for j in members):
                members.add(i)
                changed = True
    return [rows[i] for i in sorted(members)]


def propose(array: np.ndarray, transform: Affine, epsg: int, site_id: str,
            flight_date: str | None = None, params: Params | None = None) -> gpd.GeoDataFrame:
    """Propose footprint polygons on a (3, H, W) uint8 chip. Returns a GeoDataFrame in ``epsg``."""
    p = params or Params()
    res0 = abs(transform.a)
    factor = max(1, round(WORK_RES_M / res0))
    res = res0 * factor
    small = block_mean(array[:3], factor) / 255.0
    tr = Affine(res, 0, transform.c, 0, -res, transform.f)
    h, w = small.shape[1:]
    cx, cy = tr @ (w / 2, h / 2)
    masks = class_masks(small, p)
    rows = []
    for kind in KINDS:
        m = _clean(masks[kind], res, p, kind)
        lab, n = ndi.label(m)
        if n == 0:
            continue
        for geom_json, val in features.shapes(lab.astype(np.int32), mask=lab > 0, transform=tr):
            g = shape(geom_json).simplify(res * 0.5)
            a = polygon_area_m2(g)
            if a < p.min_area(kind) or a > p.max_area_m2:
                continue
            if kind == "site_pad" and a > p.max_pad_area_m2:
                continue
            if short_side(g) < p.min_width(kind):
                continue
            if rectangularity(g) < p.min_rect(kind):
                continue
            if g.centroid.distance(Point(cx, cy)) > p.max_centre_dist_m:
                continue
            rows.append({"kind": kind, "geometry": g, "area_m2": a})
    equip = [r["geometry"] for r in rows if r["kind"] != "site_pad"]
    rows = [r for r in rows if r["kind"] != "site_pad"
            or any(r["geometry"].distance(e) <= p.pad_max_gap_m for e in equip)]
    if p.cluster_only:
        rows = _site_cluster(rows, Point(cx, cy), p)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    counters: dict[str, int] = {}
    recs = []
    for r in sorted(rows, key=lambda r: (r["kind"], -r["area_m2"])):
        counters[r["kind"]] = counters.get(r["kind"], 0) + 1
        recs.append({
            "polygon_id": f"{site_id}-{r['kind']}-{counters[r['kind']]:03d}",
            "site_id": site_id, "kind": r["kind"], "area_m2": round(r["area_m2"], 2),
            "source": "auto", "version": 1, "is_current": True, "algo": ALGO,
            "flight_date": flight_date, "res_m": res, "created_utc": now,
            "quantity_type": "detected", "geometry": r["geometry"],
        })
    cols = ["polygon_id", "site_id", "kind", "area_m2", "source", "version", "is_current", "algo",
            "flight_date", "res_m", "created_utc", "quantity_type", "geometry"]
    return gpd.GeoDataFrame(recs, columns=cols, geometry="geometry", crs=f"EPSG:{epsg}")


def revise(gdf: gpd.GeoDataFrame, polygon_id: str, new_geom: BaseGeometry,
           kind: str | None = None) -> gpd.GeoDataFrame:
    """Manual correction: keep the old row (``is_current`` False) and add a new version.

    ``polygon_id`` stays the same; ``version`` increases; ``source`` becomes ``"manual"``;
    ``area_m2`` is recomputed from the new geometry in the table's projected CRS.
    """
    cur = gdf[(gdf.polygon_id == polygon_id) & gdf.is_current]
    if cur.empty:
        raise KeyError(polygon_id)
    old = cur.iloc[0]
    out = gdf.copy()
    out.loc[cur.index, "is_current"] = False
    new = old.copy()
    new["geometry"] = new_geom
    new["area_m2"] = round(polygon_area_m2(new_geom), 2)
    new["source"] = "manual"
    new["version"] = int(old["version"]) + 1
    new["is_current"] = True
    if kind:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        new["kind"] = kind
    new["created_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    return gpd.GeoDataFrame(
        pd.concat([out, new.to_frame().T], ignore_index=True),
        geometry="geometry", crs=gdf.crs)


# ---------------------------------------------------------------- batch run

def main() -> None:
    from bo import paths

    idx = pd.read_parquet(paths.PROCESSED / "pilot" / "dop_chips_v0.parquet")
    epsgs = sorted(set(idx.loc[idx.chip_ok, "epsg"].astype(int)))
    import rasterio

    summ = []
    for e in epsgs:
        parts = []
        for r in idx[idx.chip_ok & (idx.epsg == e)].itertuples():
            with rasterio.open(paths.REPO_ROOT / r.chip_path) as s:
                arr, tr = s.read(), s.transform
            g = propose(arr, tr, e, r.pilot_id, r.flight_date)
            summ.append({"pilot_id": r.pilot_id, "state": r.state, "epsg": e,
                         **{f"n_{k}": int((g.kind == k).sum()) if len(g) else 0 for k in KINDS},
                         **{f"area_m2_{k}": float(g.loc[g.kind == k, "area_m2"].sum()) if len(g) else 0.0
                            for k in KINDS}})
            if len(g):
                parts.append(g)
        if parts:
            out = paths.PROCESSED / "footprints" / f"dop_footprints_v0_epsg{e}.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry",
                             crs=f"EPSG:{e}").to_parquet(out)
    s = pd.DataFrame(summ)
    s["quantity_type"] = "detected"
    s.to_parquet(paths.PROCESSED / "footprints" / "dop_footprint_summary_by_site.parquet")
    cols = [c for c in s.columns if c.startswith(("n_", "area_m2_"))]
    s = dop.drop_restricted(s)  # areas measured on use-restricted DOP stay out of results/
    agg = s.groupby("state")[cols].sum().reset_index()
    agg.insert(1, "n_chips", s.groupby("state").size().values)
    agg["quantity_type"] = "detected"
    res = paths.RESULTS / "imagery" / "dop_footprint_summary_by_state.csv"  # state aggregates only
    res.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(res, index=False)
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
