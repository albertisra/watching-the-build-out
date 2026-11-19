"""Extract DOP chips for a site table and report coverage (Phase 2, Track B).

Input: a parquet with an id column (``pilot_id`` or ``neg_id``), ``lat``, ``lon`` and
``bundesland``. Registry fields are neither read nor copied into chip metadata.

Run (chips and index; one request per second, cached responses never re-requested)::

    uv run python -m bo.imagery.dop_pilot --sites data/processed/pilot/pilot_sites_v1.parquet \
        --negatives data/processed/pilot/negatives_v1.parquet --tag v1

Evaluation against the registry commissioning date is a separate step (``evaluate``) that
reads the chip index and the site table; its result is not stored in the chip metadata.
"""

from __future__ import annotations

import argparse

import pandas as pd

from bo import paths
from bo.imagery import dop

PILOT = paths.PROCESSED / "pilot" / "pilot_sites_v0.parquet"
COVERAGE_DIR = paths.RESULTS / "imagery"


def _id_col(df: pd.DataFrame) -> str:
    return "pilot_id" if "pilot_id" in df.columns else "neg_id"


def run(sites: pd.DataFrame, size_m: float = dop.DEFAULT_SIZE_M, group: str = "site") -> pd.DataFrame:
    idc = _id_col(sites)
    rows = []
    for r in sites.to_dict("records"):
        sid, state = r[idc], r["bundesland"]
        rec = {"site_id": sid, "group": group, "state": state, "chip_path": None,
               "chip_ok": False, "date_known": False, "date_type": "none", "flight_date": None,
               "flight_year": None, "production_date": None, "reason": None}
        if state not in dop.SOURCES:
            rec["reason"] = dop.NO_SOURCE_REASON.get(state, "no open DOP source surveyed")
            rows.append(rec)
            continue
        try:
            chip = dop.fetch_chip(r["lat"], r["lon"], state, size_m)
            tif = dop.save_chip(chip, sid)
            m = chip.meta
            rec.update(chip_path=str(tif.relative_to(paths.REPO_ROOT)), chip_ok=True,
                       date_known=m["date_known"], date_type=m["date_type"],
                       flight_date=m["flight_date"], flight_year=m["flight_year"],
                       production_date=m["production_date"], epsg=m["epsg"], res_m=m["res_m"],
                       licence=m["licence"], source_url=m["source_url"],
                       date_source=m["date_source"], reason=m.get("flag") or None)
        except Exception as e:  # noqa: BLE001  # keep going; the failure is recorded, not hidden
            rec["reason"] = f"error: {type(e).__name__}: {str(e)[:200]}"
        rows.append(rec)
    return pd.DataFrame(rows)


def coverage(idx: pd.DataFrame) -> pd.DataFrame:
    """Per group and state. The four date-type columns are exclusive and sum to n_open_chip."""
    keys = ["group", "state"]
    idx = dop.drop_restricted(idx)  # never publish anything from use-restricted DOP
    ok = idx[idx.chip_ok]
    out = idx.groupby(keys).agg(n_sites=("site_id", "size"), n_open_chip=("chip_ok", "sum"),
                                flight_date_min=("flight_date", "min"),
                                flight_date_max=("flight_date", "max")).reset_index()
    for col, typ in [("n_day", "day"), ("n_year_edition", "year_edition"),
                     ("n_production_only", "production_only"), ("n_date_none", "none")]:
        c = ok[ok.date_type == typ].groupby(keys).size()
        out[col] = [int(c.get((g, s), 0)) for g, s in zip(out.group, out.state, strict=True)]
    out["n_no_chip"] = out.n_sites - out.n_open_chip.astype(int)
    out["quantity_type"] = "observed"
    return out


def evaluate(idx: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    """Per state: dated chips flown before / on-or-after the registry commissioning date.

    Descriptive only (registry dates are observed; flight dates are observed). Runs outside
    chip extraction so no registry field enters chip metadata.
    """
    m = dop.drop_restricted(idx)[lambda d: d.group == "site"].merge(
        sites[["pilot_id", "reg_commissioning_date"]], left_on="site_id", right_on="pilot_id")
    m = m[(m.date_type == "day") & m.reg_commissioning_date.notna()]
    fd, rc = pd.to_datetime(m.flight_date), pd.to_datetime(m.reg_commissioning_date)
    m = m.assign(before=fd < rc, after=fd >= rc)
    out = m.groupby("state").agg(n_dated_with_commissioning=("site_id", "size"),
                                 n_flown_before_commissioning=("before", "sum"),
                                 n_flown_on_or_after=("after", "sum")).reset_index()
    tot = out.drop(columns="state").sum().to_frame().T.assign(state="ALL")
    return pd.concat([out, tot], ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default=str(PILOT))
    ap.add_argument("--negatives", default=None)
    ap.add_argument("--tag", default="v0")
    a = ap.parse_args()
    sites = pd.read_parquet(a.sites)
    parts = [run(sites, group="site")]
    if a.negatives:
        parts.append(run(pd.read_parquet(a.negatives), group="negative"))
    idx = pd.concat(parts, ignore_index=True)
    out = paths.PROCESSED / "pilot" / f"dop_chips_{a.tag}.parquet"
    idx.to_parquet(out)
    cov = coverage(idx)
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    cov.to_csv(COVERAGE_DIR / f"dop_pilot_{a.tag}_coverage.csv", index=False)
    print(cov.to_string(index=False))
    if "reg_commissioning_date" in sites.columns:
        ev = evaluate(idx, sites)
        ev.to_csv(COVERAGE_DIR / f"dop_pilot_{a.tag}_flight_vs_commissioning.csv", index=False)
        print(ev.to_string(index=False))


if __name__ == "__main__":
    main()
