"""Per-site summaries of a chip store: clear-observation counts and Sentinel-1 densities."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .store import read_site


def site_summary(site_id: str, root: Path | None = None) -> dict:
    ds = read_site(site_id, root).load()
    months = pd.DatetimeIndex(ds.month.values)
    row = {"site_id": site_id, "n_months": len(months)}
    if "s2_clear_count" in ds:
        c = ds.s2_clear_count.values.astype(float)
        mean_c = c.mean(axis=(1, 2))
        ca = ds.s2_clear_count_alt.values.astype(float).mean(axis=(1, 2))
        has = mean_c > 0
        row.update({
            "s2_months_with_clear_obs": int(has.sum()),
            "s2_months_fully_missing": int((~has).sum()),
            "s2_mean_clear_count_per_pixel_month": float(mean_c.mean()),
            "s2_median_clear_count_over_observed_months": float(np.median(mean_c[has])) if has.any() else np.nan,
            "s2_mean_clear_count_alt_rule": float(ca.mean()),
            "s2_mean_passes_per_month": float(ds.s2_n_passes.values.mean()),
            "s2_mean_passes_used_per_month": float(ds.s2_n_passes_used.values.mean()),
        })
    if "s1_count" in ds:
        n = ds.s1_n_scenes.values
        row.update({
            "s1_relative_orbit": int(ds.attrs["s1_relative_orbit"]),
            "s1_direction": ds.attrs["s1_pass_direction"],
            "s1_months_with_obs": int((n > 0).sum()),
            "s1_mean_scenes_per_month": float(n.mean()),
            "s1_min_scenes_in_observed_month": int(n[n > 0].min()) if (n > 0).any() else 0,
        })
    return row


def store_summary(site_ids: list[str], root: Path | None = None) -> pd.DataFrame:
    return pd.DataFrame([site_summary(s, root) for s in site_ids])


def site_year_summary(site_id: str, root: Path | None = None) -> pd.DataFrame:
    """One row per site and year: months covered, months without clear observation, counts, S1 months."""
    ds = read_site(site_id, root).load()
    months = pd.DatetimeIndex(ds.month.values)
    c = ds.s2_clear_count.values.astype(float).mean(axis=(1, 2)) if "s2_clear_count" in ds else None
    n1 = ds.s1_n_scenes.values if "s1_n_scenes" in ds else None
    rows = []
    for y in sorted(set(months.year)):
        sel = np.nonzero(months.year == y)[0]
        r = {"site_id": site_id, "year": int(y), "months_in_axis": len(sel)}
        if c is not None:
            has = c[sel] > 0
            r.update(s2_months_with_clear_obs=int(has.sum()),
                     s2_months_zero_clear_obs=int((~has).sum()),
                     s2_median_clear_count_per_month=float(np.median(c[sel][has])) if has.any() else np.nan)
        if n1 is not None:
            r.update(s1_months_with_obs=int((n1[sel] > 0).sum()),
                     s1_median_scenes_per_observed_month=float(np.median(n1[sel][n1[sel] > 0]))
                     if (n1[sel] > 0).any() else np.nan,
                     s1_relative_orbit=int(ds.attrs["s1_relative_orbit"]))
        rows.append(r)
    return pd.DataFrame(rows)
