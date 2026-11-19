"""DOP chips for the round-1 labelling queue (Phase 3, task 3.5).

Reads ``data/processed/labels/queue_round1.parquet`` but writes only chip facts: no queue
stratum, no registry field. Pilot sites already have a v1 chip (matched through
``pilot_sites_v1.site_key``) and are reused, not refetched. Rows without a ``site_id`` (negatives
in the current queue file) are keyed by ``queue_id``.

Output ``data/processed/labels/dop_chips_queue_round1.parquet`` has the columns of
``dop_chips_v1.parquet`` (the file ``bo.labelling.chipview`` reads), indexed by ``site_id``.
Bavarian yearly history (flight years 2017 to 2025) goes to
``dop_chips_queue_round1_bayern_history.parquet``; a year is fetched only when the info layer
reports a flight there (empty years return a blank image).

Run: ``uv run python -m bo.imagery.dop_queue [--history]``
"""

from __future__ import annotations

import argparse
from datetime import date as _date

import pandas as pd

from bo import paths
from bo.imagery import dop, dop_pilot

QUEUE = paths.PROCESSED / "labels" / "queue_round1.parquet"
OUT = paths.PROCESSED / "labels" / "dop_chips_queue_round1.parquet"
OUT_HIST = paths.PROCESSED / "labels" / "dop_chips_queue_round1_bayern_history.parquet"
COVERAGE = paths.RESULTS / "labels" / "dop_queue_round1_coverage.csv"
HIST_YEARS = tuple(range(2017, 2026))


def chip_key(row) -> str:
    sid = row["site_id"]
    return str(sid) if isinstance(sid, str) and sid else str(row["queue_id"])


def build_index(queue: pd.DataFrame) -> pd.DataFrame:
    q = queue.assign(key=queue.apply(chip_key, axis=1))
    v1 = pd.read_parquet(paths.PROCESSED / "pilot" / "dop_chips_v1.parquet")
    pilot = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    key_to_q = dict(zip(pilot.site_key, pilot.pilot_id, strict=True))
    v1i = v1.set_index("site_id")
    reuse = q[q.key.map(key_to_q).isin(v1i.index)]
    parts = []
    r = v1i.loc[reuse.key.map(key_to_q)].reset_index(drop=True)
    r["site_id"] = reuse.key.values
    r["group"] = "queue"
    r["reused_from_v1"] = True
    parts.append(r)
    todo = q[~q.key.isin(reuse.key)]
    fetched = dop_pilot.run(
        pd.DataFrame({"pilot_id": todo.key.values, "lat": todo.lat.values, "lon": todo.lon.values,
                      "bundesland": todo.bundesland.values}), group="queue")
    fetched["reused_from_v1"] = False
    parts.append(fetched)
    return pd.concat(parts, ignore_index=True)


def bayern_history(queue: pd.DataFrame, years=HIST_YEARS) -> pd.DataFrame:
    rows = []
    for r in queue[queue.bundesland == "Bayern"].to_dict("records"):
        key = chip_key(r)
        for yr in years:
            src = dop.bayern_history_source(yr)
            x, y = dop.to_projected(r["lat"], r["lon"], src.epsg)
            info = dop.lookup_flight_date(src, x, y)
            rec = {"site_id": key, "year": yr, "chip_ok": False, "date_type": info["date_type"],
                   "flight_date": info["flight_date"], "chip_path": None, "licence": src.licence,
                   "attribution": src.attribution}
            if info["date_known"]:
                chip = dop.fetch_chip(r["lat"], r["lon"], "Bayern", source=src, with_date=False)
                tif = dop.save_chip(chip, f"{key}_{yr}", paths.CHIPS / "dop" / "hist")
                rec.update(chip_ok=True, chip_path=str(tif.relative_to(paths.REPO_ROOT)),
                           source_url=chip.meta["source_url"])
            rows.append(rec)
    return pd.DataFrame(rows)


def coverage(idx: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Per stratum and state: chip counts by date type, no chip. No coordinates. MV is dropped."""
    q = queue.assign(site_id=queue.apply(chip_key, axis=1))[["site_id", "stratum", "bundesland"]]
    m = q.merge(idx[["site_id", "chip_ok", "date_type"]], on="site_id", how="left")
    m["chip_ok"] = m.chip_ok.fillna(False).astype(bool)
    m = dop.drop_restricted(m, "bundesland")
    keys = ["stratum", "bundesland"]
    out = m.groupby(keys).size().rename("n_queue_rows").reset_index()
    for col, typ in [("n_day", "day"), ("n_year_edition", "year_edition"),
                     ("n_production_only", "production_only"), ("n_date_none", "none")]:
        c = m[m.chip_ok & (m.date_type == typ)].groupby(keys).size()
        out[col] = [int(c.get((a, b), 0)) for a, b in zip(out.stratum, out.bundesland, strict=True)]
    nc = m[~m.chip_ok].groupby(keys).size()
    out["n_no_chip"] = [int(nc.get((a, b), 0)) for a, b in zip(out.stratum, out.bundesland, strict=True)]
    out["quantity_type"] = "observed"
    out["note"] = "Mecklenburg-Vorpommern rows omitted (internal-use DOP)"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", action="store_true")
    a = ap.parse_args()
    queue = pd.read_parquet(QUEUE)
    idx = build_index(queue)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(OUT)
    COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    cov = coverage(idx, queue)
    cov.to_csv(COVERAGE, index=False)
    print(cov.groupby("stratum")[["n_queue_rows", "n_day", "n_year_edition", "n_production_only",
                                  "n_date_none", "n_no_chip"]].sum())
    if a.history:
        h = bayern_history(queue)
        h.to_parquet(OUT_HIST)
        print(h.groupby("year").chip_ok.sum(), _date.today())


if __name__ == "__main__":
    main()
