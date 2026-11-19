"""Rates of the residual-cloud/snow flag per group and store collection (review finding I4)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bo import paths

from .qc import flag_bright
from .store import read_site


def collect(root: Path, label: str, group_of) -> pd.DataFrame:
    rows = []
    for p in sorted(root.glob("*.zarr")):
        ds = read_site(p.stem, root).load()
        if "s2_refl" not in ds:
            continue
        bands = [str(b) for b in ds.band.values]
        has = ds.s2_clear_count.values.reshape(len(ds.month), -1).mean(axis=1) > 0
        fl = flag_bright(ds.s2_refl.values, ds.s2_clear_count.values, bands)
        rows.append({"collection": label, "group": group_of(p.stem), "site_id": p.stem,
                     "months_with_clear_obs": int(has.sum()), "months_flagged_bright": int((fl & has).sum())})
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["collection", "group"]).agg(
        sites=("site_id", "nunique"), months_with_clear_obs=("months_with_clear_obs", "sum"),
        months_flagged_bright=("months_flagged_bright", "sum")).reset_index()
    g["flag_rate"] = g.months_flagged_bright / g.months_with_clear_obs
    return g


def group_v0(sid: str) -> str:
    if sid.startswith("P"):
        return "pilot_positive"
    n = int(sid[1:])
    return "hard_negative" if n < 50 else "random_negative"


def group_v1(sid: str) -> str:
    if sid.startswith("Q"):
        return "pilot_positive"
    n = int(sid[1:])
    return "hard_negative" if n < 50 else "random_negative"


if __name__ == "__main__":
    parts = [collect(paths.CHIPS / "v0", "planetary_computer_v0_2018_2026", group_v0),
             collect(paths.CHIPS / "demo150", "planetary_computer_demo150_2025Q3", group_v0)]
    if (paths.CHIPS / "sh_v1").exists():
        parts.append(collect(paths.CHIPS / "sh_v1", "sentinelhub_v1_sanity10", group_v1))
    out = summarise(pd.concat(parts, ignore_index=True))
    out.round(4).to_csv(paths.RESULTS / "imagery" / "qc_flag_rates.csv", index=False)
    print(out.round(4).to_string())
