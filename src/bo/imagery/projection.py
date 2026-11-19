"""Projection of the network volume of a full-range chip build from measured per-scene costs.

Inputs are measured in this repository: bytes per Sentinel-1 scene and per Sentinel-2 pass from the
one-year single-site runs in ``results/imagery/quota_log.csv`` (stages ``split_no-s1`` and
``split_no-s2``), and counts of scenes per year from the Planetary Computer STAC for one site.
The output is a *modelled* volume; it is written to ``results/imagery/chip_cost_projection.csv``.
"""

from __future__ import annotations

import pandas as pd

from bo import paths

from .geo import chip_grid
from .io import stac_client
from .s1 import select_orbit
from .s1pipe import item_records, search_s1
from .s2pipe import dedupe_items, group_passes, search_s2


def scenes_per_year(lon: float, lat: float, start: str = "2015-01-01", end: str = "2026-10-31"):
    g = chip_grid(lon, lat)
    cl = stac_client()
    s1 = item_records(search_s1(g.bounds_lonlat(), start, end, cl), g)
    ch = select_orbit(s1)
    d1 = pd.Series([r["date"] for r in s1 if r["covers"] and r["relative_orbit"] == ch.relative_orbit
                    and r["direction"] == ch.direction]).drop_duplicates()
    s1y = pd.to_datetime(d1).dt.year.value_counts().sort_index()
    its = dedupe_items(search_s2(g.bounds_lonlat(), start, end, cl))
    s2y = pd.Series([p[0].datetime.year for p in group_passes(its)]).value_counts().sort_index()
    return s1y, s2y


def project(site_lon: float, site_lat: float, n_sites: int = 150) -> pd.DataFrame:
    q = pd.read_csv(paths.RESULTS / "imagery" / "quota_log.csv")
    s1 = q[q.stage == "split_no-s2"].iloc[0]
    s2 = q[q.stage == "split_no-s1"].iloc[0]
    s1y, s2y = scenes_per_year(site_lon, site_lat)
    # per-unit costs from the 2025 single-site runs (same site, same year)
    s1_scenes_2025 = int(s1y.get(2025, 0))
    s2_passes_2025 = int(s2y.get(2025, 0))
    mb_per_s1_scene = s1.net_bytes_gdal / 1e6 / s1_scenes_2025
    mb_per_s2_pass = s2.net_bytes_gdal / 1e6 / s2_passes_2025
    rows = []
    for name, y0 in (("S1 from 2015", 2015), ("S1 from 2017", 2017), ("S1 from 2019", 2019)):
        n = int(s1y[s1y.index >= y0].sum())
        rows.append({"component": name, "scenes_or_passes_per_site": n,
                     "mb_per_unit_measured": mb_per_s1_scene,
                     "gb_per_site": n * mb_per_s1_scene / 1000,
                     "gb_all_sites": n * mb_per_s1_scene / 1000 * n_sites})
    for name, y0 in (("S2 from 2015 (6 bands)", 2015), ("S2 from 2017 (6 bands)", 2017),
                     ("S2 from 2019 (6 bands)", 2019)):
        n = int(s2y[s2y.index >= y0].sum())
        rows.append({"component": name, "scenes_or_passes_per_site": n,
                     "mb_per_unit_measured": mb_per_s2_pass,
                     "gb_per_site": n * mb_per_s2_pass / 1000,
                     "gb_all_sites": n * mb_per_s2_pass / 1000 * n_sites})
    df = pd.DataFrame(rows)
    df["label"] = "modelled from measured per-scene bytes (site P002 2025)"
    df["n_sites"] = n_sites
    return df
