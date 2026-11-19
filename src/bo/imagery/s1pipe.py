"""Sentinel-1 RTC monthly composites for one chip with one fixed relative orbit.

Decision (GRD vs RTC): Planetary Computer ``sentinel-1-rtc`` (gamma0 terrain-flattened, 10 m, UTM,
float32 COG, CC BY 4.0) is used. ``sentinel-1-grd`` on the same platform is not geocoded or
cloud-optimised, so windowed reads onto a UTM chip grid are not possible without downloading whole
scenes. The values are linear gamma0 power; dB = 10 log10. Limitations: the RTC processor
(Catalyst, PlanetDEM) is not documented to us in detail; thermal-noise handling of old IPF
versions (before 2018/2019, docs/research/sentinel1.md) is whatever the processor did, so
level steps at IPF dates remain possible (R4).
"""

from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from rasterio.enums import Resampling
from shapely.geometry import box, shape

from .composite import masked_median, month_index
from .config import PC_S1_RTC, S1_NODATA, ChipConfig
from .geo import ChipGrid
from .io import default_workers, read_on_grid, stac_client
from .quota import GLOBAL, Counters
from .s1 import OrbitChoice, select_orbit, speckle_filter, to_db


def search_s1(lon_lat_bbox, start: str, end: str, client=None, counters: Counters = GLOBAL):
    client = client or stac_client()
    s = client.search(
        collections=[PC_S1_RTC], bbox=lon_lat_bbox, datetime=f"{start}/{end}", limit=500
    )
    items = list(s.items())
    counters.add(stac_searches=max(1, len(items) // 500 + 1))
    return items


def item_records(items: list, grid: ChipGrid) -> list[dict]:
    chip = box(*grid.bounds_lonlat())
    out = []
    for it in items:
        p = it.properties
        out.append({
            "item": it, "relative_orbit": p.get("sat:relative_orbit"),
            "direction": p.get("sat:orbit_state"),
            "date": pd.Timestamp(it.datetime).date(),
            "covers": shape(it.geometry).contains(chip),
        })
    return out


def read_scene(item, grid: ChipGrid, cfg: ChipConfig, counters: Counters):
    """VV and VH in dB on the chip grid (read with a margin when a speckle filter is on)."""
    pad = 2 if cfg.speckle else 0
    out = {}
    for pol in cfg.pols:
        lin = read_on_grid(
            item.assets[pol].href, grid, Resampling.bilinear, S1_NODATA, counters, pad=pad
        )
        lin = np.where(lin == S1_NODATA, np.nan, lin.astype(np.float32))
        if cfg.speckle:
            lin = speckle_filter(lin, cfg.speckle)[pad:-pad, pad:-pad]
        out[pol] = to_db(lin)
    return out


def build_s1(
    grid: ChipGrid, start: str, end: str, cfg: ChipConfig | None = None,
    counters: Counters = GLOBAL, client=None, workers: int | None = None,
    orbit: tuple[int, str] | None = None, months: np.ndarray | None = None,
) -> dict | None:
    cfg = cfg or ChipConfig()
    items = search_s1(grid.bounds_lonlat(), start, end, client, counters)
    recs = item_records(items, grid)
    choice: OrbitChoice | None = select_orbit(recs)
    if choice is None:
        return None
    if orbit is not None:
        choice = OrbitChoice(orbit[0], orbit[1], 0, choice.candidates)
    sel = [r for r in recs if r["covers"] and r["relative_orbit"] == choice.relative_orbit
           and r["direction"] == choice.direction]
    # one scene per acquisition day (adjacent slices can both cover the chip)
    by_day: dict = {}
    for r in sorted(sel, key=lambda r: r["item"].id):
        by_day.setdefault(r["date"], r)
    sel = list(by_day.values())
    with ThreadPoolExecutor(workers or default_workers()) as ex:
        scenes = list(ex.map(lambda r: read_scene(r["item"], grid, cfg, counters), sel))
    months = months if months is not None else month_index(start, end)
    H, W = grid.shape
    T = len(months)
    vv = np.full((T, H, W), np.nan, np.float32)
    vh = np.full((T, H, W), np.nan, np.float32)
    cnt = np.zeros((T, H, W), np.uint16)
    n_scenes = np.zeros(T, np.int16)
    by_m: dict[int, list[int]] = defaultdict(list)
    lookup = {m: i for i, m in enumerate(months)}
    items_by_month: dict[str, list[str]] = {}
    for k, r in enumerate(sel):
        m = np.datetime64(pd.Timestamp(r["item"].datetime).tz_convert("UTC").tz_localize(None), "M")
        if m in lookup:
            by_m[lookup[m]].append(k)
    for i, ks in by_m.items():
        n_scenes[i] = len(ks)
        items_by_month[str(months[i])] = sorted(sel[k]["item"].id for k in ks)
        for pol, dst in (("vv", vv), ("vh", vh)):
            if pol not in cfg.pols:
                continue
            vals = np.stack([scenes[k][pol] for k in ks])
            med, c = masked_median(vals, np.isfinite(vals))
            dst[i] = med
            if pol == cfg.pols[0]:
                cnt[i] = c
    return {
        "months": months, "vv_db": vv, "vh_db": vh, "count": cnt, "n_scenes": n_scenes,
        "relative_orbit": int(choice.relative_orbit), "direction": choice.direction,
        "orbit_candidates": json.dumps([list(c) for c in choice.candidates]),
        "items_by_month": json.dumps(items_by_month),
        "speckle": cfg.speckle or "none", "pols": ",".join(cfg.pols),
    }
