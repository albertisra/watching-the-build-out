"""``uv run python -m bo.imagery.shcli --ids Q010 ... --root data/chips/sh_v1`` builds chips on Sentinel Hub.

Refuses to run when the estimated cost (plan from ``data/processed/pilot/sh_cost_counts.parquet``) would
take the month past 60 percent of the free quota (see ``shcost.decide``).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from bo import paths

from . import shcost
from .shchips import build_many_sh
from .sites import load_sites


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--root", type=Path, default=paths.CHIPS / "sh_v1")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default="2026-10-31")
    ap.add_argument("--stage", default="sh_chips")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--sensor", choices=["s1", "s2", "both"], default="both")
    ap.add_argument("--skip-roots", type=Path, nargs="*", default=[])
    a = ap.parse_args(argv)
    P = paths.PROCESSED / "pilot"
    sites = pd.concat([load_sites(P / "pilot_sites_v1.parquet"), load_sites(P / "negatives_v1.parquet")],
                      ignore_index=True)
    keys = pd.read_parquet(P / "pilot_sites_v1.parquet")[["pilot_id", "site_key"]].rename(
        columns={"pilot_id": "site_id"})
    sites = sites.merge(keys, on="site_id", how="left")  # own registry site, excluded from the chip context
    if a.ids:
        sites = sites[sites.site_id.isin(a.ids)]
    plan = pd.read_parquet(P / "sh_cost_counts.parquet")
    plan = plan[plan.site_id.isin(sites.site_id)]
    sensors = ("s1", "s2") if a.sensor == "both" else (a.sensor,)
    from .store import site_path

    todo = [i for i in sites.site_id if not any(site_path(i, r).exists() for r in (a.root, *a.skip_roots))]
    sites = sites[sites.site_id.isin(todo)]
    plan = plan[plan.site_id.isin(todo)]
    est = shcost.estimate(plan)
    if a.sensor == "s1":
        est["s2_pu"], est["s2_requests"] = 0.0, 0
    if a.sensor == "s2":
        est["s1_pu"], est["s1_requests"] = 0.0, 0
    used_pu, used_req = shcost.used_this_month()
    d = shcost.decide(est.s2_pu.sum() + est.s1_pu.sum(), int(est.s2_requests.sum() + est.s1_requests.sum()),
                      used_pu, used_req)
    print(d, flush=True)
    if not d["proceed"]:
        print("estimate exceeds the 60 percent allowance: running with a hard stop at the allowance; "
              "re-run later to resume (stored chips are skipped)", flush=True)
    cap_pu = d["limit_pu"] - used_pu
    cap_req = d["limit_requests"] - used_req
    print(build_many_sh(sites, plan, a.start, a.end, a.root, stage=a.stage, sensors=sensors,
                        skip_roots=a.skip_roots, pu_cap=cap_pu, req_cap=cap_req,
                        workers=a.workers, margin_pu=45.0 * a.workers))


if __name__ == "__main__":
    main()
