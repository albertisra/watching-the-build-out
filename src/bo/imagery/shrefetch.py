"""Refetch the Sentinel-1 months that the first Sentinel Hub build lost to a wrong relative-orbit formula.

The first build used offset 73 for S1B and excluded S1D, so S1B scenes (September 2016 to December 2021) and S1D
scenes (from 2026-04) were missing from every stored series. This job requests only those windows with the
corrected formula (``s1orbit``), keeps the stored relative orbit and direction, and REPLACES the monthly
medians, counts and item lists of those months in the existing stores. Months outside the windows are untouched.
Every request is written to the quota log at once; the job stops before the November cap and resumes later
(stores carry the attribute ``s1_refetch_done`` with the windows already replaced).
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from bo import paths

from . import shcost
from .geo import ChipGrid
from .quota import GLOBAL
from .sentinelhub import post_process, s1_body, split_s1_year
from .shchips import _month_items
from .store import read_site, write_site

# (year, first month, last month): S1B era from September 2016 to December 2021, S1D era from April 2026
WINDOWS = [(2016, 9, 12)] + [(y, 1, 12) for y in range(2017, 2022)] + [(2026, 4, 10)]
STAGE = "sh_s1_refetch_req"
NOV_CAP_PU = 9500.0
NOV_CAP_REQ = 9500.0


def window_key(w, tag: str = "") -> str:
    return f"{w[0]}-{w[1]:02d}..{w[0]}-{w[2]:02d}{tag}"


def estimate(plan: pd.DataFrame, site_ids) -> pd.DataFrame:
    """PU per site and window from the cost model (S1 PU per acquisition scaled by the share of months)."""
    rows = []
    p = plan[plan.site_id.isin(site_ids)]
    for w in WINDOWS:
        share = (w[2] - w[1] + 1) / 12
        q = p[(p.year == w[0]) & (p.s1_dates > 0)]
        rows.append({"window": window_key(w), "requests": len(q),
                     "pu": float((q.s1_dates * shcost.S1_PU_PER_DATE * share).sum())})
    return pd.DataFrame(rows)


def refetch_site(site_id: str, root: Path, log_stage: str = STAGE, counters=GLOBAL, windows=None, tag: str = "") -> int:
    ds = read_site(site_id, root).load()
    done = set(json.loads(ds.attrs.get("s1_refetch_done", "[]")))
    grid = ChipGrid(int(ds.attrs["crs_epsg"]), __import__("affine").Affine(*ds.attrs["transform"]),
                    int(ds.attrs["chip_size_px"]), float(ds.attrs["resolution_m"]))
    orbit, direction = int(ds.attrs["s1_relative_orbit"]), ds.attrs["s1_pass_direction"]
    months = pd.DatetimeIndex(ds.month.values)
    items = json.loads(ds.attrs["s1_items_by_month"])
    n = 0
    for w in (windows or WINDOWS):
        if window_key(w, tag) in done:
            continue
        y, m0, m1 = w
        if not ((months.year == y).any()):
            continue
        tf, tt = f"{y}-{m0:02d}-01", f"{y}-{m1:02d}-{pd.Timestamp(y, m1, 1).days_in_month:02d}"
        arr, ud, _ = post_process(s1_body(grid, y, direction, orbit, time_from=tf, time_to=tt), counters,
                                  log_stage=log_stage, log_note=f"{site_id} S1 refetch {tf}..{tt}")
        n += 1
        r = split_s1_year(arr)
        by_m, _, cnt = _month_items(ud, y)
        for mo in range(m0, m1 + 1):
            idx = np.nonzero((months.year == y) & (months.month == mo))[0]
            if len(idx) == 0:
                continue
            i = int(idx[0])
            ds["s1_vv_db"].values[i] = r["db"][mo - 1, 0]
            ds["s1_vh_db"].values[i] = r["db"][mo - 1, 1]
            ds["s1_count"].values[i] = r["count"][mo - 1]
            ds["s1_n_scenes"].values[i] = cnt[mo - 1]
            key = f"{y}-{mo:02d}"
            items.pop(key, None)
            if key in by_m:
                items[key] = by_m[key]
        done.add(window_key(w, tag))
        ds.attrs["s1_items_by_month"] = json.dumps(items)
        ds.attrs["s1_refetch_done"] = json.dumps(sorted(done))
        ds.attrs["s1_orbit_formula"] = ("s1orbit.py: offsets S1A 73, S1B 27, S1C 172 (99 from abs orbit 8260), "
                                        "S1D 42; refetched windows replaced")
        write_site(ds, site_id, root)  # after every window: a stop loses at most one request
    return n


def run(stores: list[tuple[str, Path]], pu_cap: float, req_cap: float, workers: int = 8,
        margin_pu: float = 250.0, windows=None, tag: str = "", stage: str = STAGE) -> dict:
    """Refetch for (site_id, root) pairs until the cap (PU and requests of THIS month in the log) is reached."""
    used_pu, used_req = shcost.used_this_month()
    lock = threading.Lock()
    state = {"stopped": False}

    def current():
        u, r = shcost.used_this_month()
        return u, r

    def one(item):
        sid, root = item
        with lock:
            u, r = current()
            if state["stopped"] or u + margin_pu > pu_cap or r + 100 > req_cap:
                state["stopped"] = True
                return sid, "CAP_STOP"
        try:
            refetch_site(sid, root, stage, windows=windows, tag=tag)
            return sid, None
        except Exception as e:  # noqa: BLE001 - report and continue
            return sid, repr(e)[:200]

    out = {"done": [], "stopped": [], "failed": [], "start_pu": used_pu, "start_req": used_req}
    with ThreadPoolExecutor(workers) as ex:
        for sid, err in ex.map(one, stores):
            (out["stopped"] if err == "CAP_STOP" else out["failed"] if err else out["done"]).append(
                sid if not err or err == "CAP_STOP" else (sid, err))
            print(sid, err or "ok", flush=True)
    return out


def all_stores() -> list[tuple[str, Path]]:
    pairs = []
    for root in (paths.CHIPS / "sh_v1", paths.CHIPS / "sh_v1_s1"):
        pairs += [(p.stem, root) for p in sorted(root.glob("*.zarr"))]
    return pairs


if __name__ == "__main__":
    import sys

    stores = all_stores()
    plan = pd.read_parquet(paths.PROCESSED / "pilot" / "sh_cost_counts.parquet")
    est = estimate(plan, [s for s, _ in stores])
    est.to_csv(paths.RESULTS / "imagery" / "sentinelhub_s1_refetch_estimate.csv", index=False)
    u, r = shcost.used_this_month()
    print(est.to_string(), "\ntotal", est.pu.sum(), est.requests.sum(), "used", u, r, flush=True)
    if "--run" in sys.argv:
        print(run(stores, NOV_CAP_PU, NOV_CAP_REQ))


# review B3: S1C boundary corrected from absolute orbit 8000 to 8260; only June 2026 passes (2026-06-08 to 2026-06-25) change
B3_WINDOWS = [(2026, 6, 6)]
B3_TAG = "#s1c-boundary-8260"
