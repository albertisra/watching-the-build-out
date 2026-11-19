"""Refetch Sentinel-1 site-months flagged by ``s1_refetch_plan`` with the per-scene A42 mask (review N3).

Each store is refetched from its own platform (ee_r1 from Earth Engine; sh_v1 and sh_v1_s1 from Sentinel Hub) on the
orbit and direction stored in it, so no platform or orbit is mixed. Per site-year window the monthly VV, VH, count and
n_scenes are replaced; months outside the windows stay as they were. Every request is written to the quota log.
Usage: ``uv run python -m bo.imagery.s1_refetch --platform ee|sh [--run] [--limit N]``
"""

from __future__ import annotations

import argparse
import json

import affine
import numpy as np
import pandas as pd

from bo import paths

from .geo import ChipGrid
from .store import read_site, write_site

PLAN = paths.RESULTS / "imagery" / "s1_refetch_site_months.csv"
TAG = "#a42-perscene"
EE_EECU_PER_REQUEST = 9.0  # measured batch mean 3.0 EECU-s x 3 margin (eequeue.EECU_PER_REQUEST)


def windows_by_site(plan: pd.DataFrame) -> dict:
    """(root, site_id) -> [(year, first suspect month, last suspect month)]."""
    p = plan.assign(year=plan.month.str[:4].astype(int), mo=plan.month.str[5:7].astype(int))
    g = p.groupby(["root", "site_id", "year"]).mo.agg(["min", "max"]).reset_index()
    out: dict = {}
    for r in g.itertuples():
        out.setdefault((r.root, r.site_id), []).append((int(r.year), int(r.min), int(r.max)))
    return out


def grid_of(ds) -> ChipGrid:
    return ChipGrid(int(ds.attrs["crs_epsg"]), affine.Affine(*ds.attrs["transform"]),
                    int(ds.attrs["chip_size_px"]), float(ds.attrs["resolution_m"]))


def refetch_ee(site_id: str, root, wins) -> int:
    from . import eechips as E
    from .quota import append_ee_row

    ds = read_site(site_id, root).load()
    done = set(json.loads(ds.attrs.get("s1_refetch_a42", "[]")))
    grid, orbit, direc = grid_of(ds), int(ds.attrs["s1_relative_orbit"]), ds.attrs["s1_pass_direction"]
    months = pd.DatetimeIndex(ds.month.values)
    n = 0
    for y, m0, m1 in wins:
        key = f"{y}-{m0:02d}..{m1:02d}"
        if key in done:
            continue
        r = E.split_s1(E.fetch_array(E.s1_year_image(E.chip_geometry(grid), y, orbit, direc), grid))
        append_ee_row("ee_s1_refetch_a42", EE_EECU_PER_REQUEST, f"ESTIMATE batch x3, {site_id} s1 {y}")
        n += 1
        for mo in range(m0, m1 + 1):
            idx = np.nonzero((months.year == y) & (months.month == mo))[0]
            if len(idx):
                i = int(idx[0])
                ds["s1_vv_db"].values[i], ds["s1_vh_db"].values[i] = r["db"][mo - 1, 0], r["db"][mo - 1, 1]
                ds["s1_count"].values[i] = r["count"][mo - 1]
                ds["s1_n_scenes"].values[i] = int(r["count"][mo - 1].max())
        done.add(key)
        ds.attrs["s1_refetch_a42"] = json.dumps(sorted(done))
        write_site(ds, site_id, root)
    return n


def refetch_sh(site_id: str, root, wins) -> int:
    from .shrefetch import refetch_site

    return refetch_site(site_id, root, "sh_s1_refetch_a42_req", windows=wins, tag=TAG)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["ee", "sh"], required=True)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--pu-cap", type=float, default=9500.0)
    a = ap.parse_args()
    wins = windows_by_site(pd.read_csv(PLAN))
    items = [(k, w) for k, w in sorted(wins.items()) if (k[0] == "ee_r1") == (a.platform == "ee")]
    if a.limit:
        items = items[:a.limit]
    print(len(items), "stores", sum(len(w) for _, w in items), "requests planned")
    if a.run:
        if a.platform == "ee":
            from . import eechips as E
            from .eequeue import eecu_used_this_month

            E.init()
        else:
            from . import shcost
        from concurrent.futures import ThreadPoolExecutor

        def one(it):
            (rt, sid), w = it
            root = paths.CHIPS / rt
            if a.platform == "ee":
                if eecu_used_this_month() / 3600 > 100:
                    return sid, "EE cap stop"
                return sid, E.scrub(str(refetch_ee(sid, root, w)))
            if shcost.used_this_month()[0] + 100 > a.pu_cap:
                return sid, "PU cap stop"
            return sid, refetch_sh(sid, root, w)  # one store per worker, so no store is written twice at once

        with ThreadPoolExecutor(a.workers) as ex:
            for sid, res in ex.map(one, items):
                print(sid, res, flush=True)
