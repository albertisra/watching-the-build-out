"""Logged one-item replacement in the round-1 labelling queue (author decision 2026-11-19).

Replaces queue item ``--old`` (coarse coordinates) by one new positive drawn with the original selection logic
(``bo.data.queue.select_positives``, seed ``bo.paths.SEED``) from the same stratum cell, excluding every site already in
the queue, keeping at least ``MIN_SEP_M`` to every queue site (stricter than the original 1 km positive and 2 km negative
rules, so the new site forms its own 2 km cluster), requiring coordinate precision dp4plus (else dp3) and preferring a
state with an open, unrestricted DOP source (which excludes Mecklenburg-Vorpommern). Other rows and queue ids are not touched. Appends to
``results/labels/queue_round1_replacements.csv``.

Run: ``uv run python -m bo.data.queue_replace --old L1-0012 --new L1-0411 --reason "..."``
"""

from __future__ import annotations

import argparse
import datetime as dt

import numpy as np
import pandas as pd

from bo import paths
from bo.data import queue as Q

LOG = paths.RESULTS / "labels" / "queue_round1_replacements.csv"
MIN_SEP_M = 2_000.0
PRECISION_ORDER = [["dp4plus"], ["dp3"]]


def draw(queue: pd.DataFrame, strata: pd.DataFrame, sites: pd.DataFrame, old: str, seed: int = paths.SEED):
    """Return (pick row, rule text) for the replacement of ``old``."""
    cell = strata.set_index("queue_id").loc[old]
    q_old = queue.set_index("queue_id").loc[old]
    keep_q = queue[queue.queue_id != old]
    taken = set(queue["site_id"].dropna())
    pool = Q.positive_pool(sites, taken, Q.german_states())
    pool = pool[(pool.technology == cell.technology) & (pool.reg_size_class == cell.reg_size_class)
                & (pool.reg_period == cell.reg_period) & (pool.reg_status == cell.reg_status)
                & (~pool.reg_colocated)]
    prec = sites.set_index("site_id")["coord_precision_class"]
    pool["coord_precision_class"] = pool["site_id"].map(prec)
    fixed = Q.to_xy(keep_q["lat"].to_numpy(), keep_q["lon"].to_numpy())
    from bo.timeline.splits import open_dop_states

    open_states = open_dop_states()  # open DOP source, not use-restricted (so MV is out)
    for restrict_state in (True, False):
        for precs in PRECISION_ORDER:
            p = pool[pool.coord_precision_class.isin(precs)]
            if restrict_state:
                p = p[p.bundesland.isin(open_states)]
            if p.empty:
                continue
            rng = np.random.default_rng(seed)
            pick = Q.select_positives(p, 1, rng, fixed, min_sep_m=MIN_SEP_M)
            if len(pick):
                rule = (f"same cell as {old} (stratum {cell.stratum}, {cell.technology}, {cell.reg_size_class}, "
                        f"{cell.reg_period}, {cell.reg_status}, not co-located); select_positives n=1; "
                        f"precision {'/'.join(precs)}; {'open-DOP states only (MV excluded)' if restrict_state else 'any state'}; "
                        f"min separation {MIN_SEP_M:.0f} m to all queue sites; eligible candidates {len(p)}")
                return pick.iloc[0], rule, str(q_old.bundesland)
    raise RuntimeError("cell empty under the rules; take the nearest cell and document it")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    queue = pd.read_parquet(Q.QUEUE)
    strata = pd.read_parquet(Q.STRATA)
    if a.new in set(queue.queue_id):
        raise SystemExit(f"{a.new} already exists in the queue")
    sites = pd.read_parquet(Q.SITES)
    pick, rule, _old_state = draw(queue, strata, sites, a.old)
    print(pick[["site_id", "bundesland", "landkreis", "reg_size_class", "reg_period", "reg_colocated"]].to_dict())
    print(rule)
    if a.dry_run:
        return
    srow = strata[strata.queue_id == a.old].iloc[0].to_dict()
    qn = pd.DataFrame([{**{c: pick.get(c, pd.NA) for c in Q.QUEUE_COLUMNS}, "queue_id": a.new,
                        "stratum": srow["stratum"]}])
    sn = pd.DataFrame([{**srow, "queue_id": a.new, "site_id": pick["site_id"], "reg_colocated": bool(pick["reg_colocated"])}])
    q2 = pd.concat([queue[queue.queue_id != a.old], qn[queue.columns]], ignore_index=True)
    s2 = pd.concat([strata[strata.queue_id != a.old], sn[strata.columns]], ignore_index=True)
    q2.to_parquet(Q.QUEUE, index=False)
    s2.to_parquet(Q.STRATA, index=False)
    log = pd.DataFrame([{"date": dt.date.today().isoformat(), "old_queue_id": a.old, "new_queue_id": a.new,
                         "reason": a.reason, "rule": rule, "seed": paths.SEED}])
    log.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
    print("written", len(q2), len(s2))


if __name__ == "__main__":
    main()
