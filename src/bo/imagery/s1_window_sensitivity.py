"""A42 sensitivity: S1 validity floors shifted by +-5 dB at the affected sites (VV floor -30, VH floor -35 by default).

Per affected site and scenario: usable site-months (``s1_valid_c`` > 0 in the feature build) and the number of BOCPD
change-point starts (``bo.timeline.bocpd``, default config, on the standardised ``s1_vv_c`` series, NaN months kept
missing). Stricter floors (-25 / -30) are applied to the stored, already refetched series. Looser floors (-35 / -40)
need values the stores no longer hold; they are refetched from Earth Engine for the affected ee_r1 windows and kept in
memory only. Sentinel Hub stores have no looser scenario (it would cost further processing units).
Usage: ``uv run python -m bo.imagery.s1_window_sensitivity [--no-loose]``
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from bo import paths
from bo.features.site import site_features
from bo.timeline import bocpd

from . import s1 as S1
from .store import read_site

SHIFTS = {"floors_minus5": -5.0, "default": 0.0, "floors_plus5": 5.0}  # tighter = floor raised by 5 dB (plus5)
OUT = paths.RESULTS / "imagery" / "s1_window_sensitivity.csv"


def _starts(f: pd.DataFrame) -> tuple[int, int]:
    x = f["s1_vv_c"].to_numpy(float)
    ok = np.isfinite(x)
    if ok.sum() < 6:
        return int(ok.sum()), 0
    z = (x - np.nanmean(x)) / (np.nanstd(x) or 1.0)
    cfg = bocpd.BocpdConfig()
    cps = bocpd.changepoints(bocpd.run(z[:, None], cfg), cfg.lag, cfg.tau)
    return int((f["s1_valid_c"] > 0).sum()), len(cps)


def _with_floor(ds, shift: float):
    """Apply a floor shift to the stored series (only raising the floor can act on stored values)."""
    ds = ds.copy(deep=True)
    old = dict(S1.S1_DB_FLOOR)
    try:
        S1.S1_DB_FLOOR["vv"], S1.S1_DB_FLOOR["vh"] = old["vv"] + shift, old["vh"] + shift
        vv, vh, c, _, _ = S1.mask_s1_db(ds.s1_vv_db.values, ds.s1_vh_db.values, ds.s1_count.values)
    finally:
        S1.S1_DB_FLOOR.update(old)
    ds["s1_vv_db"].values[:], ds["s1_vh_db"].values[:], ds["s1_count"].values[:] = vv, vh, c
    return ds


def _loose_ee(ds, site_id, wins):
    """Refetch the affected windows with floors lowered by 5 dB (in memory)."""
    from . import eechips as E
    from .quota import append_ee_row
    from .s1_refetch import grid_of

    old = dict(S1.S1_DB_FLOOR)
    ds = ds.copy(deep=True)
    months = pd.DatetimeIndex(ds.month.values)
    grid = grid_of(ds)
    try:
        E.S1_DB_FLOOR["vv"], E.S1_DB_FLOOR["vh"] = old["vv"] - 5.0, old["vh"] - 5.0  # same dict object as S1
        for y, m0, m1 in wins:
            r = E.split_s1(E.fetch_array(E.s1_year_image(E.chip_geometry(grid), y, int(ds.attrs["s1_relative_orbit"]),
                                                          ds.attrs["s1_pass_direction"]), grid))
            append_ee_row("ee_s1_sensitivity", 9.0, f"ESTIMATE batch x3, {site_id} s1 {y} loose floors")
            for mo in range(m0, m1 + 1):
                idx = np.nonzero((months.year == y) & (months.month == mo))[0]
                if len(idx):
                    i = int(idx[0])
                    ds["s1_vv_db"].values[i], ds["s1_vh_db"].values[i] = r["db"][mo - 1, 0], r["db"][mo - 1, 1]
                    ds["s1_count"].values[i] = r["count"][mo - 1]
    finally:
        S1.S1_DB_FLOOR.update(old)
    return ds


def run(loose: bool = True) -> pd.DataFrame:
    from .s1_refetch import PLAN, windows_by_site

    wins = windows_by_site(pd.read_csv(PLAN))
    if loose:
        from . import eechips as E
        E.init()
    rows = []
    for (root, sid), w in sorted(wins.items()):
        ds0 = read_site(sid, paths.CHIPS / root).load()
        scen = {"floors_vv-25_vh-30": _with_floor(ds0, +5.0), "floors_vv-30_vh-35_default": ds0}
        if loose and root == "ee_r1":
            scen["floors_vv-35_vh-40"] = _loose_ee(ds0, sid, w)
        for name, ds in scen.items():
            n_use, n_cp = _starts(site_features(ds, site_id=sid))
            rows.append({"root": root, "site_id": sid, "scenario": name, "usable_site_months": n_use,
                         "changepoint_starts": n_cp, "label": "detected (S1 change-point count, not a result)"})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-loose", action="store_true")
    d = run(not ap.parse_args().no_loose)
    tot = d.groupby(["root", "scenario"]).agg(site_id=("site_id", "size"), usable_site_months=("usable_site_months", "sum"),
                                              changepoint_starts=("changepoint_starts", "sum")).reset_index()
    tot["site_id"] = "TOTAL_" + tot.site_id.astype(str) + "_sites"
    out = pd.concat([d, tot], ignore_index=True)
    out.to_csv(OUT, index=False)
    print(tot.to_string())
