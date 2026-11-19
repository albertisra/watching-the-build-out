"""Compare a Sentinel Hub year with the existing Planetary Computer chip of the same site."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bo import paths

from .quota import Stage
from .sentinelhub import post_process, s2_body, split_s2_year
from .store import read_site


def compare(site_id: str, year: int, root=None) -> pd.DataFrame:
    pc = read_site(site_id, root or paths.CHIPS / "v0").load()
    from affine import Affine

    tr = Affine(*pc.attrs["transform"])
    from .geo import ChipGrid

    g = ChipGrid(int(pc.attrs["crs_epsg"]), tr, int(pc.attrs["chip_size_px"]), float(pc.attrs["resolution_m"]))
    with Stage("sh_pc_check", "cdse_sentinelhub", note=f"{site_id} {year}"):
        arr, _, _ = post_process(s2_body(g, year))
    r = split_s2_year(arr)
    bands = list(pc.band.values)
    rows = []
    for mo in range(12):
        m = np.datetime64(f"{year}-{mo + 1:02d}", "M")
        if m not in pc.month.values.astype("datetime64[M]"):
            continue
        i = int(np.nonzero(pc.month.values.astype("datetime64[M]") == m)[0][0])
        row = {"site_id": site_id, "month": f"{year}-{mo + 1:02d}",
               "pc_mean_clear_count": float(pc.s2_clear_count.values[i].mean()),
               "sh_mean_clear_count": float(r["count"][mo].mean())}
        for b in bands:
            bi = bands.index(b)
            a, s = pc.s2_refl.values[i, bi], r["refl"][mo, ["B02", "B03", "B04", "B08", "B11", "B12"].index(b)]
            ok = np.isfinite(a) & np.isfinite(s)
            row[f"{b}_mean_abs_diff"] = float(np.abs(a - s)[ok].mean()) if ok.any() else np.nan
            row[f"{b}_mean_pc"] = float(np.nanmean(a)) if np.isfinite(a).any() else np.nan
            row[f"{b}_mean_sh"] = float(np.nanmean(s)) if np.isfinite(s).any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
