"""Sentinel-2 L2A monthly composites for one chip (Planetary Computer, COG windowed reads)."""

from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from rasterio.enums import Resampling

from .composite import masked_median, month_index
from .config import ALT_CLEAR_RULE, PC_S2, ChipConfig
from .geo import ChipGrid
from .io import default_workers, read_on_grid, stac_client
from .masking import clear_mask
from .quota import GLOBAL, Counters
from .reflectance import dn_to_reflectance, parse_baseline

SCL_CLASSES = tuple(range(12))


@dataclass
class S2Obs:
    """One pass (all items of one data take) cut to the chip."""

    key: str
    date: pd.Timestamp
    item_ids: list[str]
    baselines: dict[str, str]
    scl_frac: np.ndarray  # (12,) fraction of chip pixels per SCL class
    clear: np.ndarray  # (H, W) bool, primary rule
    clear_alt: np.ndarray  # (H, W) bool, alternative rule
    refl: np.ndarray | None  # (B, H, W) float32, NaN where not clear; None if nothing clear
    scene_rows: list[dict] = field(default_factory=list)


def dedupe_items(items: list) -> list:
    """One item per (MGRS tile, data take); the highest processing baseline wins.

    Planetary Computer can hold the same granule under several baselines after reprocessing.
    """
    best: dict[tuple, object] = {}
    for it in items:
        p = it.properties
        key = (p.get("s2:mgrs_tile"), p.get("s2:datatake_id") or it.datetime.isoformat()[:16])
        try:
            bl = parse_baseline(p.get("s2:processing_baseline"))
        except ValueError:
            bl = (-1, -1)
        if key not in best or bl > best[key][0]:
            best[key] = (bl, it)
    return [v[1] for v in best.values()]


def search_s2(lon_lat_bbox, start: str, end: str, client=None, counters: Counters = GLOBAL):
    client = client or stac_client()
    s = client.search(
        collections=[PC_S2], bbox=lon_lat_bbox, datetime=f"{start}/{end}", limit=500
    )
    items = list(s.items())
    counters.add(stac_searches=max(1, len(items) // 500 + 1))
    return items


def _read_item(item, grid: ChipGrid, cfg: ChipConfig, counters: Counters):
    """Read SCL, then the reflectance bands only if something is clear."""
    scl = read_on_grid(item.assets["SCL"].href, grid, Resampling.nearest, 0, counters)
    frac = np.bincount(scl.ravel().astype(int), minlength=12)[:12] / scl.size
    clear = clear_mask(scl, cfg.clear_rule)
    alt = clear_mask(scl, ALT_CLEAR_RULE)
    baseline = item.properties.get("s2:processing_baseline")
    refl = None
    if clear.any():
        arrs = []
        for b in cfg.bands:
            dn = read_on_grid(item.assets[b].href, grid, Resampling.nearest, 0, counters)
            r = dn_to_reflectance(dn, baseline)
            arrs.append(r)
        refl = np.stack(arrs)
        # DN 0 (no data) in any band removes the pixel from the clear set
        nod = ~np.isfinite(refl).all(axis=0)
        clear = clear & ~nod
        alt = alt & ~nod
        refl = np.where(clear[None], refl, np.nan).astype(np.float32)
        if not clear.any():
            refl = None
    return scl, frac, clear, alt, refl, baseline


def read_obs(items_one_pass: list, grid: ChipGrid, cfg: ChipConfig, counters: Counters) -> S2Obs:
    """Read all items of one data take and merge them pixel-wise (overlapping tiles)."""
    clear = np.zeros(grid.shape, bool)
    alt = np.zeros(grid.shape, bool)
    refl = np.full((len(cfg.bands),) + grid.shape, np.nan, np.float32)
    frac_acc = None
    rows = []
    baselines = {}
    for it in sorted(items_one_pass, key=lambda i: i.id):
        _scl, frac, c, a, r, bl = _read_item(it, grid, cfg, counters)
        baselines[it.id] = str(bl)
        new = c & ~clear
        if r is not None:
            refl[:, new] = r[:, new]
        clear |= c
        alt |= a
        frac_acc = frac if frac_acc is None else np.maximum(frac_acc, frac)
        rows.append({
            "item_id": it.id, "datetime": it.datetime, "baseline": str(bl),
            "tile": it.properties.get("s2:mgrs_tile"), "platform": it.properties.get("platform"),
            "clear_frac": float(c.mean()), "clear_alt_frac": float(a.mean()),
            **{f"scl_{k}": float(frac[k]) for k in SCL_CLASSES},
        })
    date = pd.Timestamp(items_one_pass[0].datetime).tz_convert("UTC").tz_localize(None)
    return S2Obs(
        key=str(items_one_pass[0].properties.get("s2:datatake_id") or date),
        date=date, item_ids=[i.id for i in items_one_pass], baselines=baselines,
        scl_frac=frac_acc, clear=clear, clear_alt=alt, refl=refl if clear.any() else None,
        scene_rows=rows,
    )


def item_epsg(item) -> int | None:
    """UTM EPSG of the item's tile: STAC projection field if present, else the zone in the MGRS tile name."""
    code = item.properties.get("proj:code") or item.properties.get("proj:epsg")
    if code is not None:
        return int(str(code).split(":")[-1])
    tile = item.properties.get("s2:mgrs_tile")
    if tile and tile[:2].isdigit():
        return 32600 + int(tile[:2])
    return None


def group_passes(items: list, grid_epsg: int | None = None) -> list[list]:
    """Group items by data take. With ``grid_epsg`` a pass keeps only tiles of the chip's own UTM zone when it has
    any (m10 of the review: no mixing of warped neighbouring-zone tiles with native ones near zone borders);
    a pass that only has neighbouring-zone tiles is read warped, as before."""
    groups: dict[str, list] = defaultdict(list)
    for it in items:
        k = it.properties.get("s2:datatake_id") or it.datetime.isoformat()[:16]
        groups[k].append(it)
    out = []
    for g in groups.values():
        if grid_epsg is not None:
            native = [i for i in g if item_epsg(i) == grid_epsg]
            if native:
                g = native
        out.append(g)
    return out


def composite_months(obs: list[S2Obs], months: np.ndarray, grid: ChipGrid, cfg: ChipConfig):
    """Monthly median reflectance and clear counts. Months without clear data stay NaN, count 0."""
    T, B = len(months), len(cfg.bands)
    H, W = grid.shape
    refl = np.full((T, B, H, W), np.nan, np.float32)
    count = np.zeros((T, H, W), np.uint16)
    count_alt = np.zeros((T, H, W), np.uint16)
    n_pass = np.zeros(T, np.int16)
    n_used = np.zeros(T, np.int16)
    items_by_month: dict[str, list[str]] = {}
    by_m: dict[int, list[S2Obs]] = defaultdict(list)
    lookup = {m: i for i, m in enumerate(months)}
    for o in obs:
        m = np.datetime64(o.date, "M")
        if m in lookup:
            by_m[lookup[m]].append(o)
    for i, lst in by_m.items():
        n_pass[i] = len(lst)
        items_by_month[str(months[i])] = sorted(x for o in lst for x in o.item_ids)
        used = [o for o in lst if o.refl is not None]
        n_used[i] = len(used)
        count_alt[i] = np.sum([o.clear_alt for o in lst], axis=0)
        if used:
            vals = np.stack([o.refl for o in used])
            valid = np.stack([o.clear for o in used])
            med, cnt = masked_median(vals, valid)
            refl[i], count[i] = med, cnt
    return refl, count, count_alt, n_pass, n_used, items_by_month


def build_s2(
    grid: ChipGrid, lon: float, lat: float, start: str, end: str, cfg: ChipConfig | None = None,
    counters: Counters = GLOBAL, client=None, workers: int | None = None,
    months: np.ndarray | None = None,
) -> dict:
    cfg = cfg or ChipConfig()
    items = dedupe_items(search_s2(grid.bounds_lonlat(), start, end, client, counters))
    months = months if months is not None else month_index(start, end)
    passes = group_passes(items, grid.epsg)  # native-zone tiles preferred (m10)
    with ThreadPoolExecutor(workers or default_workers()) as ex:
        obs = list(ex.map(lambda p: read_obs(p, grid, cfg, counters), passes))
    refl, count, count_alt, n_pass, n_used, by_month = composite_months(obs, months, grid, cfg)
    rows = [r for o in obs for r in o.scene_rows]
    baselines = {k: v for o in obs for k, v in o.baselines.items()}
    return {
        "months": months, "refl": refl, "count": count, "count_alt": count_alt,
        "n_passes": n_pass, "n_used": n_used, "items_by_month": json.dumps(by_month),
        "baselines": json.dumps(baselines), "scene_log": pd.DataFrame(rows),
    }
