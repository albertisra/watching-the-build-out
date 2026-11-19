"""Earth Engine chips for the round-1 labelling queue (410 sites), resumable, with a running EECU estimate.

Stores are keyed by ``queue_id`` (``data/chips/ee_r1/<queue_id>.zarr``). No registry field and no queue stratum is
written into a store (no ``other_registered_sites_in_chip`` either); the stratum appears only in the aggregate summary.
S2 from 2017-01 and S1 from 2015-01, both to 2026-10. S1 orbit: reuse the relative orbit of an existing Sentinel Hub or
Planetary Computer S1 store of the same coordinates; otherwise the orbit with most acquisition days over 2015 to 2026,
ties to the lower orbit number (assumption A41).

Budget: every request writes an ESTIMATE row to ``quota_log.csv`` (batch-equivalent EECU-seconds x 3, from the measured
per-site-year means in ``ee_cost_estimate.csv``); the run stops cleanly when the month's Earth Engine total reaches the cap.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from bo import paths

from . import eechips as E
from .quota import QUOTA_LOG, append_ee_row
from .store import read_site, site_path

ROOT = paths.CHIPS / "ee_r1"
STAGE = "ee_queue_r1_req"
EECU_PER_REQUEST = {"s2": 16.285 * 3, "s1": 3.0 * 3}  # measured batch mean x 3 (EECU-seconds)
CAP_EECU_HOURS = 100.0
START, END = "2015-01-01", "2026-10-31"
YEARS_S2 = list(range(2017, 2027))
YEARS_S1 = list(range(2015, 2027))
STOP = threading.Event()


def eecu_used_this_month(log: Path | None = None, month: str | None = None) -> float:
    q = pd.read_csv(log or QUOTA_LOG)
    q = q[q.platform == "earthengine"]
    month = month or pd.Timestamp.now("UTC").strftime("%Y-%m")
    q = q[q.timestamp_utc.str.startswith(month)]
    # per-request estimates and measurements count; stage rows of the cost probe are measurements
    return float(pd.to_numeric(q.eecu_seconds, errors="coerce").fillna(0).sum())


# Reference S1 stores: Sentinel Hub (v1) and Planetary Computer (v0) pilots. v0 was missing until 2026-11-19 (orbit
# mismatch for L1-0030 and L1-0063, `results/imagery/ee_vs_sh_orbit_check.csv`).
REF_TABLES = (("pilot_sites_v1.parquet", "pilot_id"), ("negatives_v1.parquet", "neg_id"),
              ("pilot_sites_v0.parquet", "pilot_id"), ("negatives_v0.parquet", "neg_id"))
REF_ROOTS = ("sh_v1", "sh_v1_s1", "v0")


def existing_orbits(queue: pd.DataFrame) -> dict[str, tuple[int, str]]:
    """queue_id -> (relative orbit, direction) of an existing Sentinel Hub / Planetary Computer S1 store at the same coordinates."""
    ref = []
    for f, idc in REF_TABLES:
        t = pd.read_parquet(paths.PROCESSED / "pilot" / f)
        ref.append(t[[idc, "lat", "lon"]].rename(columns={idc: "ref_id"}))
    ref = pd.concat(ref, ignore_index=True)
    out = {}
    for r in queue.itertuples():
        m = ref[(abs(ref.lat - r.lat) < 1e-6) & (abs(ref.lon - r.lon) < 1e-6)]
        if m.empty:
            continue
        rid = m.ref_id.iloc[0]
        for root in REF_ROOTS:
            if site_path(rid, paths.CHIPS / root).exists():
                a = read_site(rid, paths.CHIPS / root).attrs
                if "s1_relative_orbit" in a:
                    out[r.queue_id] = (int(a["s1_relative_orbit"]), str(a["s1_pass_direction"]))
                    break
    return out


def build_one(queue_id: str, lon: float, lat: float, orbit, root: Path, cap_s: float) -> str | None:
    def on_request(kind, year):
        append_ee_row(STAGE, EECU_PER_REQUEST[kind], f"ESTIMATE batch x3, {queue_id} {kind} {year}")
        if eecu_used_this_month() >= cap_s:
            STOP.set()
            raise RuntimeError("EECU_CAP")

    try:
        E.build_site_ee(queue_id, lon, lat, START, END, YEARS_S2, YEARS_S1, root, orbit=orbit, context=False,
                        on_request=on_request)
        return None
    except Exception as e:  # noqa: BLE001 - one failing site must not stop the batch
        return E.scrub(repr(e))[:200]


def run(queue: pd.DataFrame, root: Path = ROOT, workers: int = 6, cap_hours: float = CAP_EECU_HOURS) -> dict:
    E.init()
    cap_s = cap_hours * 3600
    orbits = existing_orbits(queue)
    out = {"done": [], "skipped": [], "failed": [], "stopped": []}

    def one(r):
        if site_path(r.queue_id, root).exists():
            return r.queue_id, "SKIP"
        if STOP.is_set() or eecu_used_this_month() >= cap_s:
            STOP.set()
            return r.queue_id, "CAP_STOP"
        err = build_one(r.queue_id, r.lon, r.lat, orbits.get(r.queue_id), root, cap_s)
        return r.queue_id, err

    with ThreadPoolExecutor(workers) as ex:
        for qid, err in ex.map(one, list(queue.itertuples())):
            key = {"SKIP": "skipped", "CAP_STOP": "stopped", None: "done"}.get(err, "failed")
            out[key].append(qid if key != "failed" else (qid, err))
            print(qid, err or "ok", flush=True)
    return out


def summary(queue: pd.DataFrame, root: Path = ROOT) -> pd.DataFrame:
    """Per stratum: sites done, months with S2 clear data, months with zero S1 (aggregates only)."""
    rows = []
    for r in queue.itertuples():
        if not site_path(r.queue_id, root).exists():
            rows.append({"stratum": r.stratum, "done": 0})
            continue
        ds = read_site(r.queue_id, root).load()
        s2 = ds.s2_clear_count.values.reshape(len(ds.month), -1).mean(axis=1) > 0
        s1 = ds.s1_n_scenes.values > 0 if "s1_n_scenes" in ds else np.zeros(len(ds.month), bool)
        t = pd.DatetimeIndex(ds.month.values)
        in_s2 = t >= "2017-01-01"
        rows.append({"stratum": r.stratum, "done": 1, "s2_months_axis": int(in_s2.sum()),
                     "s2_months_with_clear": int((s2 & in_s2).sum()), "s1_months_axis": len(t),
                     "s1_months_zero": int((~s1).sum()),
                     "bright_flag_months": int(ds.s2_flag_bright.values.sum()) if "s2_flag_bright" in ds else 0})
    d = pd.DataFrame(rows)
    g = d.groupby("stratum").agg(sites_in_queue=("done", "size"), sites_done=("done", "sum"),
                                 s2_months_axis=("s2_months_axis", "sum"), s2_months_with_clear=("s2_months_with_clear", "sum"),
                                 s1_months_axis=("s1_months_axis", "sum"), s1_months_zero=("s1_months_zero", "sum"),
                                 bright_flag_months=("bright_flag_months", "sum")).reset_index()
    g["s2_clear_share"] = g.s2_months_with_clear / g.s2_months_axis
    g["s1_zero_share"] = g.s1_months_zero / g.s1_months_axis
    return g


BANNED = ("positive_battery", "positive_pv", "hard_negative", "random_negative", "pilot", "reg_", "BESS-", "PV-SEE", "SEE9",
          "stratum", "commission", "power_kw", "status", "other_registered_sites_in_chip")


def leak_check(root: Path = ROOT) -> pd.DataFrame:
    """Scan every store's attributes and variable names for registry fields or queue strata."""
    rows = []
    for p in sorted(root.glob("*.zarr")):
        ds = read_site(p.stem, root)
        text = " ".join([*map(str, ds.attrs.keys()), *map(str, ds.attrs.values()), *map(str, ds.data_vars)])
        hits = [b for b in BANNED if b in text]
        rows.append({"store": p.stem, "hits": ",".join(hits), "clean": not hits,
                     "platform": ds.attrs.get("source"), "has_coordinates_attr": "lat" in ds.attrs or "lon" in ds.attrs})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    q = pd.read_parquet(paths.PROCESSED / "labels" / "queue_round1.parquet")
    res = run(q)
    print({k: len(v) for k, v in res.items()}, flush=True)
    print([x for x in res["failed"]][:20])
    summary(q).round(4).to_csv(paths.RESULTS / "imagery" / "ee_queue_round1_chip_summary.csv", index=False)
    lc = leak_check()
    print("leak check clean:", int(lc.clean.sum()), "of", len(lc), flush=True)
