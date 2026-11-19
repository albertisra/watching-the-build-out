"""Monthly operational capacity from registry units, and the comparison with official figures.

Observed quantities only (registry). The registry keeps no status history (``docs/research/mastr.md``),
so the series is a reconstruction from date fields of the *current* snapshot:

* A unit counts as operational at date D if its status is In Betrieb, Vorübergehend stillgelegt
  or Endgültig stillgelegt, ``reg_commissioning_date <= D``, and it was not shut down before D.
* Units "In Planung" are never operational, even if they carry a commissioning date.
* Units without a usable commissioning date (missing, placeholder) are excluded and reported.
* Final shutdown ends operation at ``reg_shutdown_final_date``. A temporary shutdown opens a gap
  from ``reg_shutdown_temp_begin_date`` until ``reg_resumption_date`` (open-ended while status is
  Vorübergehend stillgelegt). Missing shutdown dates for those statuses are imputed with the
  last update date and flagged (``reg_op_end_imputed``).
* The value of a month is the stock at the end of the month, capped at the export date.

Units whose shutdown date is not after the commissioning date are never counted.
"""

from __future__ import annotations

import pandas as pd

STATUS_OPERATING = "In Betrieb"
STATUS_PLANNED = "In Planung"
STATUS_TEMP = "Vorübergehend stillgelegt"
STATUS_FINAL = "Endgültig stillgelegt"
OPERATIONAL_STATUSES = (STATUS_OPERATING, STATUS_TEMP, STATUS_FINAL)
UNKNOWN_STATE = "unbekannt"


def operation_intervals(units: pd.DataFrame) -> pd.DataFrame:
    """Add ``reg_op_start``, ``reg_op_end``, ``reg_gap_begin``, ``reg_gap_end``,
    ``reg_op_end_imputed`` and ``reg_op_excluded_reason`` (empty when the unit is usable)."""
    u = units.copy()
    st = u["reg_status"]
    start = u["reg_commissioning_date"]
    final = u["reg_shutdown_final_date"]
    tbeg = u["reg_shutdown_temp_begin_date"]
    tend = u["reg_resumption_date"]
    last = u["reg_last_update"].dt.normalize()

    op_end = pd.Series(pd.NaT, index=u.index, dtype="datetime64[ns]")
    gap_b = pd.Series(pd.NaT, index=u.index, dtype="datetime64[ns]")
    gap_e = pd.Series(pd.NaT, index=u.index, dtype="datetime64[ns]")
    imputed = pd.Series(False, index=u.index)

    m = st == STATUS_FINAL
    op_end[m] = final[m].fillna(last[m])
    imputed[m] = final[m].isna()
    m = st == STATUS_TEMP
    gap_b[m] = tbeg[m].fillna(last[m])
    imputed[m] = tbeg[m].isna()
    resumed = m & tend.notna() & (tend > gap_b)
    gap_e[resumed] = tend[resumed]  # open-ended otherwise
    m = (st == STATUS_OPERATING) & tbeg.notna() & tend.notna() & (tend > tbeg)
    gap_b[m], gap_e[m] = tbeg[m], tend[m]
    # a final end date on a unit not marked final still ends operation (status lag)
    m = (st != STATUS_FINAL) & final.notna()
    op_end[m] = final[m]

    reason = pd.Series("", index=u.index)
    reason[~st.isin(OPERATIONAL_STATUSES)] = "status_not_operational"
    reason[st.isin(OPERATIONAL_STATUSES) & start.isna()] = "no_usable_commissioning_date"
    reason[(reason == "") & op_end.notna() & (op_end <= start)] = "shutdown_not_after_commissioning"
    reason[(reason == "") & gap_b.notna() & (gap_b < start)] = "gap_before_commissioning"
    u["reg_op_start"], u["reg_op_end"] = start, op_end
    u["reg_gap_begin"], u["reg_gap_end"] = gap_b, gap_e
    u["reg_op_end_imputed"] = imputed
    u["reg_op_excluded_reason"] = reason
    return u


def operational_at(units: pd.DataFrame, when: pd.Timestamp) -> pd.Series:
    """Boolean mask of units operational on ``when`` (needs ``operation_intervals`` columns)."""
    when = pd.Timestamp(when)
    ok = units["reg_op_excluded_reason"] == ""
    on = units["reg_op_start"] <= when
    ended = units["reg_op_end"].notna() & (units["reg_op_end"] <= when)
    in_gap = (
        units["reg_gap_begin"].notna()
        & (units["reg_gap_begin"] <= when)
        & (units["reg_gap_end"].isna() | (when < units["reg_gap_end"]))
    )
    return ok & on & ~ended & ~in_gap


def capacity_at(units: pd.DataFrame, when, technology: str | None = None) -> dict[str, float]:
    """Stock at one date: units, gross and net MW, usable MWh (storage, units with kWh known)."""
    mask = operational_at(units, when)
    if technology:
        mask &= units["technology"] == technology
    s = units[mask]
    return {
        "units": int(mask.sum()),
        "gross_mw": float(s["gross_kw"].sum() / 1000.0),
        "net_mw": float(s["net_kw"].sum() / 1000.0),
        "usable_mwh": float(s["usable_kwh_alloc"].sum() / 1000.0),
        "units_kwh_known": int(s["usable_kwh_alloc"].notna().sum()),
    }


def _events(units: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Signed capacity events (+ at start and gap end, - at end and gap begin)."""
    u = units[units["reg_op_excluded_reason"] == ""]
    base = u[["technology", "bundesland"] + cols].copy()
    base["bundesland"] = base["bundesland"].fillna(UNKNOWN_STATE)
    pieces = []
    for col, sign in (
        ("reg_op_start", 1),
        ("reg_op_end", -1),
        ("reg_gap_begin", -1),
        ("reg_gap_end", 1),
    ):
        d = u[col]
        part = base[d.notna()].copy()
        part["date"] = d[d.notna()]
        for c in cols:
            part[c] = sign * part[c]
        part["n"] = sign
        part["is_start"] = col == "reg_op_start"
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True)


def monthly_capacity(units: pd.DataFrame, export_date) -> pd.DataFrame:
    """Month-end stock and monthly additions by technology and federal state.

    Columns: ``month`` (YYYY-MM), ``technology``, ``bundesland``, ``units``, ``gross_mw``,
    ``net_mw``, ``usable_mwh``, ``units_kwh_known``, ``added_units``, ``added_gross_mw``,
    ``added_net_mw``, ``added_usable_mwh`` (new commissioning dates in the month), plus
    ``is_partial_month`` for the export month.
    """
    export_date = pd.Timestamp(export_date)
    u = operation_intervals(units) if "reg_op_excluded_reason" not in units else units
    u = u.assign(
        _kwh=u["usable_kwh_alloc"].fillna(0.0) / 1000.0,
        _kwh_known=u["usable_kwh_alloc"].notna().astype(int),
        _gross=u["gross_kw"].fillna(0.0) / 1000.0,
        _net=u["net_kw"].fillna(0.0) / 1000.0,
    )
    cols = ["_gross", "_net", "_kwh", "_kwh_known"]
    ev = _events(u, cols)
    ev = ev[ev["date"] <= export_date]
    if ev.empty:
        return pd.DataFrame(
            columns=["month", "technology", "bundesland", "units", "gross_mw", "net_mw", "usable_mwh"]
        )
    ev["month"] = ev["date"].dt.to_period("M")
    first = ev["month"].min()
    months = pd.period_range(first, pd.Period(export_date, "M"), freq="M")
    keys = ev[["technology", "bundesland"]].drop_duplicates()
    grid = keys.merge(pd.DataFrame({"month": months}), how="cross")
    delta = ev.groupby(["technology", "bundesland", "month"])[cols + ["n"]].sum().reset_index()
    adds = (
        ev[ev["is_start"]]
        .groupby(["technology", "bundesland", "month"])[cols + ["n"]]
        .sum()
        .rename(columns={c: "add" + c for c in cols + ["n"]})
        .reset_index()
    )
    out = grid.merge(delta, how="left", on=["technology", "bundesland", "month"]).merge(
        adds, how="left", on=["technology", "bundesland", "month"]
    )
    out = out.fillna(0.0).sort_values(["technology", "bundesland", "month"])
    stock = out.groupby(["technology", "bundesland"])[cols + ["n"]].cumsum()
    res = out[["month", "technology", "bundesland"]].copy()
    res["units"] = stock["n"].round().astype(int)
    res["gross_mw"] = stock["_gross"]
    res["net_mw"] = stock["_net"]
    res["usable_mwh"] = stock["_kwh"]
    res["units_kwh_known"] = stock["_kwh_known"].round().astype(int)
    res["added_units"] = out["addn"].round().astype(int)
    res["added_gross_mw"] = out["add_gross"]
    res["added_net_mw"] = out["add_net"]
    res["added_usable_mwh"] = out["add_kwh"]
    not_storage = res["technology"] != "battery"
    for c in ("usable_mwh", "added_usable_mwh"):
        res[c] = res[c].astype(float).mask(not_storage)  # usable energy is a storage quantity
    res["units_kwh_known"] = res["units_kwh_known"].mask(not_storage)
    res["is_partial_month"] = res["month"] == pd.Period(export_date, "M")
    res["month"] = res["month"].astype(str)
    # float noise from cumulative sums
    for c in ("gross_mw", "net_mw", "usable_mwh", "added_usable_mwh"):
        res[c] = res[c].round(6).clip(lower=0.0)
    return res.reset_index(drop=True)


def national_totals(monthly: pd.DataFrame) -> pd.DataFrame:
    """Sum the state series to technology totals per month."""
    keep = ["units", "gross_mw", "net_mw", "usable_mwh", "units_kwh_known", "added_units",
            "added_gross_mw", "added_net_mw", "added_usable_mwh"]
    g = monthly.groupby(["month", "technology"])
    out = g[keep].sum(min_count=1).reset_index()
    out["is_partial_month"] = g["is_partial_month"].first().to_numpy()
    return out


def exclusion_summary(units: pd.DataFrame) -> pd.DataFrame:
    """Units and capacity left out of the series, by technology and reason."""
    u = units[units["reg_op_excluded_reason"] != ""]
    return (
        u.groupby(["technology", "reg_op_excluded_reason"])
        .agg(units=("unit_id", "size"), gross_mw=("gross_kw", lambda s: s.sum() / 1000.0))
        .reset_index()
    )
