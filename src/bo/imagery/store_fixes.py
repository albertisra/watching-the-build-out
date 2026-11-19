"""In-place provenance and consistency fixes for existing chip stores (review m3, m4, m-new-5). No network, no quota.

``fix_ee_attrs``: Earth Engine stores inherited the Planetary Computer ``s2_offset_policy`` text; the harmonised
collection carries no client-side offset. Also states that per-month scene ids are not kept.
``zero_count_where_vv_nan``: a pixel with VV NaN cannot have a valid observation; the count follows VV (A42).
``backfill_range_flag``: adds ``s2_flag_range`` (A89) to stores written before it existed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from bo import paths

from .eechips import EE_OFFSET_POLICY, ITEMS_NOT_KEPT_NOTE
from .qc import add_flags
from .store import read_site, write_site


def fix_ee_attrs(ds) -> bool:
    """Overwrite the wrong offset policy on an Earth Engine store (in memory). True if anything changed."""
    if ds.attrs.get("source") != "earthengine":
        return False
    changed = ds.attrs.get("s2_offset_policy") != EE_OFFSET_POLICY
    ds.attrs["s2_offset_policy"] = EE_OFFSET_POLICY
    for k in ("s2_items_by_month", "s1_items_by_month"):
        if k in ds.attrs and ds.attrs[k] == "{}":
            ds.attrs[k + "_note"] = ITEMS_NOT_KEPT_NOTE
            changed = True
    return changed


def zero_count_where_vv_nan(ds) -> int:
    """Set s1_count to 0 where s1_vv_db is NaN (in memory). Returns the number of pixels changed."""
    if "s1_vv_db" not in ds or "s1_count" not in ds:
        return 0
    cnt = ds.s1_count.values.copy()
    bad = np.isnan(ds.s1_vv_db.values) & (cnt > 0)
    n = int(bad.sum())
    if n:
        cnt[bad] = 0
        ds["s1_count"] = (ds.s1_count.dims, cnt)
        ds.attrs["s1_count_fix"] = (f"count set to 0 where VV is NaN ({n} pixels), 2026-11-19, review m-new-5; "
                                    "no refetch")
    return n


def run(root: Path, what: str) -> dict:
    stats = {"stores": 0, "changed": 0, "pixels": 0}
    for p in sorted(root.glob("*.zarr")):
        sid = p.stem
        ds = read_site(sid, root).load()
        stats["stores"] += 1
        ch, px = False, 0
        if what == "ee_attrs":
            ch = fix_ee_attrs(ds)
        elif what == "s1_count":
            px = zero_count_where_vv_nan(ds)
            ch = px > 0
        elif what == "range_flag":
            before = ds["s2_flag_range"].values.sum() if "s2_flag_range" in ds else -1
            add_flags(ds)
            ch = True
            px = int(ds["s2_flag_range"].values.sum()) if "s2_flag_range" in ds else 0
            _ = before
        if ch:
            write_site(ds, sid, root)
            stats["changed"] += 1
            stats["pixels"] += px
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ee_attrs", "s1_count", "range_flag"])
    ap.add_argument("--root", required=True, help="chip store directory relative to the repository, e.g. data/chips/ee_r1")
    a = ap.parse_args()
    print(run(paths.REPO_ROOT / a.root, a.what))
