"""Scan chip stores for Sentinel-1 fill values and impossible dB values (review M1, assumption A42) and repair in place.

Masking only: out-of-window VV/VH pixels become NaN and their VV count becomes 0. Nothing is refetched or interpolated.
Usage: ``uv run python -m bo.imagery.s1_fill_scan [--repair]``
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from bo import paths

from .s1 import S1_DB_CEIL, S1_DB_FLOOR, mask_s1_db
from .store import read_site, write_site

ROOTS = ["ee_r1", "sh_v1_s1", "sh_v1", "v0"]
OUT = paths.RESULTS / "imagery" / "s1_fill_value_scan.csv"


def scan_store(ds):
    """Return (row dict, masked vv, vh, count) for one opened dataset with S1 variables."""
    vv, vh = ds.s1_vv_db.values, ds.s1_vh_db.values
    cnt = ds.s1_count.values
    vv2, vh2, cnt2, bad_v, bad_h = mask_s1_db(vv, vh, cnt)
    with np.errstate(invalid="ignore"):
        lo_v = np.isfinite(vv) & (vv < S1_DB_FLOOR["vv"])
        lo_h = np.isfinite(vh) & (vh < S1_DB_FLOOR["vh"])
        fill_v = np.isfinite(vv) & (vv < -49.0)
    m_before = np.isfinite(vv).reshape(len(vv), -1).any(axis=1)
    m_after = np.isfinite(vv2).reshape(len(vv), -1).any(axis=1)
    months = pd.to_datetime(ds.month.values)
    lost = months[m_before & ~m_after]
    row = {"n_finite_vv": int(np.isfinite(vv).sum()), "n_finite_vh": int(np.isfinite(vh).sum()),
           "n_vv_below_floor": int(lo_v.sum()), "n_vh_below_floor": int(lo_h.sum()),
           "n_vv_below_minus49": int(fill_v.sum()), "n_vv_above_ceil": int((bad_v & ~lo_v).sum()),
           "n_vh_above_ceil": int((bad_h & ~lo_h).sum()),
           "months_with_data_before": int(m_before.sum()), "months_with_data_after": int(m_after.sum()),
           "months_lost": len(lost), "first_lost": str(lost.min())[:7] if len(lost) else "",
           "last_lost": str(lost.max())[:7] if len(lost) else ""}
    return row, vv2, vh2, cnt2


def run(repair: bool = False, roots: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for root_name in roots or ROOTS:
        root = paths.DATA / "chips" / root_name
        if not root.exists():
            continue
        for p in sorted(root.glob("*.zarr")):
            sid = p.name[:-5]
            ds = read_site(sid, root).load()
            if "s1_vv_db" not in ds:
                continue
            row, vv2, vh2, cnt2 = scan_store(ds)
            row = {"root": root_name, "site_id": sid, **row, "repaired": False}
            if repair and (row["n_vv_below_floor"] or row["n_vh_below_floor"] or row["n_vv_above_ceil"]
                           or row["n_vh_above_ceil"]):
                ds["s1_vv_db"].values[:] = vv2
                ds["s1_vh_db"].values[:] = vh2
                ds["s1_count"].values[:] = cnt2
                ds.attrs["s1_validity_mask"] = json.dumps({
                    "assumption": "A42", "floor_db": S1_DB_FLOOR, "ceiling_db": S1_DB_CEIL,
                    "masked_vv_pixels_below_floor": row["n_vv_below_floor"],
                    "masked_vh_pixels_below_floor": row["n_vh_below_floor"],
                    "masked_vv_pixels_above_ceiling": row["n_vv_above_ceil"],
                    "masked_vh_pixels_above_ceiling": row["n_vh_above_ceil"],
                    "method": "in-place masking of cached values to NaN, count 0; no refetch, no interpolation"})
                write_site(ds, sid, root)
                row["repaired"] = True
            rows.append(row)
    df = pd.DataFrame(rows)
    return df


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("root")
    s = g.agg(stores=("site_id", "size"), stores_affected=("n_vv_below_floor", lambda x: int((x > 0).sum())),
              n_finite_vv=("n_finite_vv", "sum"), n_vv_below_floor=("n_vv_below_floor", "sum"),
              n_vh_below_floor=("n_vh_below_floor", "sum"), n_vv_below_minus49=("n_vv_below_minus49", "sum"),
              n_vv_above_ceil=("n_vv_above_ceil", "sum"), n_vh_above_ceil=("n_vh_above_ceil", "sum"),
              months_lost=("months_lost", "sum")).reset_index()
    s.insert(0, "site_id", "TOTAL")
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repair", action="store_true")
    a = ap.parse_args()
    d = run(a.repair)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = pd.concat([d, summarise(d)], ignore_index=True)
    out.to_csv(OUT, index=False)
    print(summarise(d).to_string())
