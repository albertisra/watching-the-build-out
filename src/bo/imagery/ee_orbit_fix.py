"""Refetch the whole Sentinel-1 series of ee_r1 stores whose orbit differs from the SH or PC store at the same
coordinates (A41 violation, v0 was not consulted). Earth Engine only, forced orbit, S2 variables untouched.

Replaces ``s1_vv_db``, ``s1_vh_db``, ``s1_count``, ``s1_n_scenes`` and the orbit attributes for all months, so the
series never mixes orbits. Usage: ``uv run python -m bo.imagery.ee_orbit_fix [--run]``
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from bo import paths

from .eequeue import EECU_PER_REQUEST, YEARS_S1
from .s1_refetch import grid_of
from .store import read_site, write_site

STAGE = "ee_s1_orbit_fix_req"


def mismatches() -> pd.DataFrame:
    from .ee_orbit_check import run

    d = run()
    return d[~d.match].drop_duplicates("queue_id")


def apply_s1(ds, vv, vh, cnt, n_scenes, orbit: int, direction: str, old: tuple, ref_id: str, ref_root: str) -> None:
    """Replace the S1 variables and orbit attributes in place (pure, tested)."""
    ds["s1_vv_db"].values[:] = vv
    ds["s1_vh_db"].values[:] = vh
    ds["s1_count"].values[:] = cnt
    ds["s1_n_scenes"].values[:] = n_scenes
    ds.attrs["s1_relative_orbit"], ds.attrs["s1_pass_direction"] = int(orbit), direction
    ds.attrs["s1_orbit_rule"] = (f"A41: orbit reused from {ref_root}/{ref_id}; refetched 2026-11-19 after the first build "
                                 f"used the fallback (orbit {old[0]} {old[1]})")
    ds.attrs.pop("s1_refetch_a42", None)  # the whole series is new and already carries the per-scene A42 mask
    ds.attrs["s1_orbit_fix"] = json.dumps({"old": list(old), "new": [int(orbit), direction], "ref": f"{ref_root}/{ref_id}"})


def fix_site(row, root) -> int:
    from . import eechips as E
    from .quota import append_ee_row

    E.init()
    ds = read_site(row.queue_id, root).load()
    grid = grid_of(ds)
    months = pd.DatetimeIndex(ds.month.values)
    vv, vh = np.full(ds.s1_vv_db.shape, np.nan, np.float32), np.full(ds.s1_vh_db.shape, np.nan, np.float32)
    cnt, n1 = np.zeros(ds.s1_count.shape, np.uint16), np.zeros(len(months), ds.s1_n_scenes.dtype)
    n = 0
    for y in YEARS_S1:
        r = E.split_s1(E.fetch_array(E.s1_year_image(E.chip_geometry(grid), y, int(row.ref_orbit), row.ref_direction), grid))
        append_ee_row(STAGE, EECU_PER_REQUEST["s1"], f"ESTIMATE batch x3, {row.queue_id} s1 {y} orbit fix")
        n += 1
        for mo in range(12):
            idx = np.nonzero((months.year == y) & (months.month == mo + 1))[0]
            if len(idx):
                i = int(idx[0])
                vv[i], vh[i], cnt[i] = r["db"][mo, 0], r["db"][mo, 1], r["count"][mo]
                n1[i] = int(cnt[i].max())
    old = (ds.attrs.get("s1_relative_orbit"), ds.attrs.get("s1_pass_direction"))
    apply_s1(ds, vv, vh, cnt, n1, int(row.ref_orbit), row.ref_direction, old, row.ref_id, row.ref_root)
    write_site(ds, row.queue_id, root)
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    mm = mismatches()
    print(mm[["queue_id", "ref_id", "ee_orbit", "ee_direction", "ref_orbit", "ref_direction"]].to_string())
    if a.run:
        for r in mm.itertuples():
            print(r.queue_id, "requests", fix_site(r, paths.CHIPS / "ee_r1"))
