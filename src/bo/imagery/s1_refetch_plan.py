"""Identify Sentinel-1 site-months whose cached monthly median may have mixed fill values (review N3, assumption A42).

The cached stores were repaired in place by masking (no original values remain), so contamination is inferred from
the mask footprint: a month is *suspect* when it has a scene (``s1_n_scenes > 0``) but VV is NaN on some or all chip
pixels. Chips fully covered by every scene have no such month, so a partial mask is the signature of border or fill
pixels (a conservative superset: partial swath coverage is also flagged). Only stores listed in
``s1_fill_value_scan.csv`` with VV pixels below the floor are examined.
Usage: ``uv run python -m bo.imagery.s1_refetch_plan``
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bo import paths

from .store import read_site

SCAN = paths.RESULTS / "imagery" / "s1_fill_value_scan.csv"
OUT = paths.RESULTS / "imagery" / "s1_refetch_site_months.csv"


def suspect_months(ds) -> pd.DataFrame:
    vv = ds.s1_vv_db.values
    fin = np.isfinite(vv).reshape(len(vv), -1).mean(axis=1)
    ns = ds.s1_n_scenes.values if "s1_n_scenes" in ds else np.zeros(len(vv))
    sus = (ns > 0) & (fin < 1.0)
    m = pd.DatetimeIndex(ds.month.values)
    return pd.DataFrame({"month": m[sus].strftime("%Y-%m"), "finite_share": fin[sus].round(4),
                         "n_scenes": ns[sus].astype(int)})


def run() -> pd.DataFrame:
    scan = pd.read_csv(SCAN)
    scan = scan[scan.site_id != "TOTAL"]
    scan = scan[scan.n_vv_below_floor > 0]  # the 45 + 67 + 5 stores of the review
    rows = []
    for r in scan.itertuples():
        ds = read_site(r.site_id, paths.CHIPS / r.root).load()
        d = suspect_months(ds)
        d.insert(0, "site_id", r.site_id)
        d.insert(0, "root", r.root)
        d["orbit"] = int(ds.attrs.get("s1_relative_orbit", -1))
        d["direction"] = ds.attrs.get("s1_pass_direction", "")
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


if __name__ == "__main__":
    df = run()
    df.to_csv(OUT, index=False)
    print(df.groupby("root").agg(stores=("site_id", "nunique"), site_months=("month", "size"),
                                 scenes=("n_scenes", "sum")))
