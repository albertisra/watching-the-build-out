"""Compare an Earth Engine chip store with the Sentinel Hub chip store of the same site (style of sh_vs_pc_check)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .store import read_site

BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]


def compare(site_id: str, ee_root: Path, sh_root: Path, year: int) -> pd.DataFrame:
    a = read_site(site_id, ee_root).load()
    b = read_site(site_id, sh_root).load()
    ma, mb = a.month.values.astype("datetime64[M]"), b.month.values.astype("datetime64[M]")
    rows = []
    for mo in range(12):
        m = np.datetime64(f"{year}-{mo + 1:02d}", "M")
        if m not in ma or m not in mb:
            continue
        i, j = int(np.nonzero(ma == m)[0][0]), int(np.nonzero(mb == m)[0][0])
        row = {"site_id": site_id, "month": f"{year}-{mo + 1:02d}",
               "ee_mean_clear_count": float(a.s2_clear_count.values[i].mean()),
               "sh_mean_clear_count": float(b.s2_clear_count.values[j].mean()),
               "ee_mean_clear_count_alt": float(a.s2_clear_count_alt.values[i].mean()),
               "sh_mean_clear_count_alt": float(b.s2_clear_count_alt.values[j].mean())}
        for band in BANDS:
            x = a.s2_refl.values[i, list(a.band.values).index(band)]
            y = b.s2_refl.values[j, list(b.band.values).index(band)]
            ok = np.isfinite(x) & np.isfinite(y)
            row[f"{band}_mean_abs_diff"] = float(np.abs(x - y)[ok].mean()) if ok.any() else np.nan
            row[f"{band}_mean_ee"] = float(np.nanmean(x)) if np.isfinite(x).any() else np.nan
            row[f"{band}_mean_sh"] = float(np.nanmean(y)) if np.isfinite(y).any() else np.nan
        for pol in ("vv", "vh"):
            x, y = a[f"s1_{pol}_db"].values[i], b[f"s1_{pol}_db"].values[j]
            ok = np.isfinite(x) & np.isfinite(y)
            row[f"s1_{pol}_mean_diff_db_ee_minus_sh"] = float((x - y)[ok].mean()) if ok.any() else np.nan
        row["ee_s1_scenes"], row["sh_s1_scenes"] = int(a.s1_n_scenes.values[i]), int(b.s1_n_scenes.values[j])
        rows.append(row)
    return pd.DataFrame(rows)
