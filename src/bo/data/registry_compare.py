"""Comparison of registry totals with published statistics, one explained row per figure.

Reference values are quoted from ``docs/research/bnetza_storage_stats.md`` (fact numbers in the
``source`` column); edit them only together with that file. Our values are observed (registry).

Like with like:

* Stock and pipeline figures are rebuilt at the reference date from commissioning, shutdown and
  registration dates, counting only units registered by that date (the registry has no status
  history, so later deletions and status changes cannot be undone).
* Additions are counted by commissioning year, and only units registered by the reference's data
  date, because late registrations are what the references could not yet see.
* Medium voltage and above uses the voltage level of the grid connection point; units without one
  (all planned units, which carry no location ID) are a stated coverage limit.

Each row carries ``comparable`` (yes, partly, no), ``explanation_class`` (reference date,
definition, gross versus net, size class, coverage, source weakness, unexplained) and a text with
the numbers behind it. Agreement is never claimed when the references disagree with each other.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bo.data import registry_series as rs

REFERENCE_FILE = "docs/research/bnetza_storage_stats.md"
MIN_DATE = pd.Timestamp("1900-01-01")

REFS = {
    "bess_in_operation_gross_gw": (2.4, "GW", "2025-10-15", "gross power, battery > 999 kW, in operation", "fact 9 (BNetzA Speicher page)", "primary"),
    "bess_in_operation_usable_gwh": (3.2, "GWh", "2025-10-15", "usable capacity, battery > 999 kW, in operation", "fact 9 (BNetzA Speicher page)", "primary"),
    "bess_planned_gross_gw": (5.0, "GW", "2025-10-15", "gross power, battery > 999 kW, planned", "fact 9 (BNetzA Speicher page)", "primary"),
    "bess_planned_usable_gwh": (10.4, "GWh", "2025-10-15", "usable capacity, battery > 999 kW, planned", "fact 9 (BNetzA Speicher page)", "primary"),
    "bess_mv_and_above_units": (1292, "units", "not stated (article 2026-08-20)", "storage at medium voltage and above, in operation", "fact 10 (SMARD)", "primary"),
    "bess_mv_and_above_net_gw": (3.6, "GW", "not stated (article 2026-08-20)", "net power, storage at medium voltage and above", "fact 10 (SMARD)", "primary"),
    "bess_added_2025_units": (83, "units", "2025 (data 2026-01-06)", "new large storage (> 1 MW), Battery-Charts via pv magazine", "fact 15", "secondary"),
    "bess_added_2025_mw": (667, "MW", "2025 (data 2026-01-06)", "new large storage (> 1 MW), Battery-Charts", "fact 15", "secondary"),
    "bess_added_2025_mwh": (1244, "MWh", "2025 (data 2026-01-06)", "new large storage (> 1 MW), Battery-Charts", "fact 15", "secondary"),
    "bess_added_2025_mwh_energycharts": (1700, "MWh", "2025 (export 2026-10-13)", "large storage added, usable capacity, Energy-Charts", "fact 16", "secondary, source not opened"),
    "bess_added_2026_jan_sep_mwh": (3800, "MWh", "2026-01 to 2026-09", "large storage added, usable capacity, Energy-Charts", "fact 16", "secondary, source not opened"),
    "bess_added_2026_jan_sep_mw": (1800, "MW", "2026-01 to 2026-09", "large storage added, Energy-Charts", "fact 16", "secondary, source not opened"),
    "pv_ground_added_2025_mw": (8200, "MW", "2025", "ground-mounted PV additions, ALL sizes", "fact 13 (trade press citing BNetzA)", "secondary"),
    "pv_ground_added_2026_jan_aug_mw": (6270, "MW", "2026-01 to 2026-08", "ground-mounted PV additions, ALL sizes, preliminary", "fact 14 (trade press citing BNetzA)", "secondary"),
}
REF_DATE = pd.Timestamp("2025-10-15")
BC_DATA_DATE = pd.Timestamp("2026-01-06")  # Battery-Charts data date (fact 15)
EC_EXPORT_DATE = pd.Timestamp("2026-10-13")  # Energy-Charts export date (fact 16)

VOLTAGE_RANK = [  # order of the catalogue values; matched by lower-case start of the text
    ("umspannebene mittelspannung/niederspannung", 1),
    ("umspannebene hochspannung/mittelspannung", 3),
    ("umspannebene höchstspannung/hochspannung", 5),
    ("niederspannung", 0),
    ("mittelspannung", 2),
    ("hochspannung", 4),
    ("höchstspannung", 6),
]
MV_MIN_RANK = 2  # Mittelspannung and above; the Umspannebene MS/NS value (rank 1) is ambiguous and excluded


def voltage_rank(text) -> float:
    """Highest voltage rank in a (possibly ';' joined) voltage level text; NaN when empty."""
    if text is None or (isinstance(text, float) and np.isnan(text)) or str(text).strip() == "":
        return np.nan
    ranks = []
    for part in str(text).split(";"):
        low = part.strip().lower()
        ranks.extend(r for key, r in VOLTAGE_RANK if low.startswith(key))
    if not ranks:
        return np.nan
    # a connection recorded at both a low and a higher level cannot be classed: ambiguous (rank 1)
    return 1 if min(ranks) <= 1 and max(ranks) >= MV_MIN_RANK else max(ranks)


def registered_by(u: pd.DataFrame, date) -> pd.Series:
    """Registered on or before ``date`` (a missing registration date counts as registered)."""
    return u["reg_registration_date"].fillna(MIN_DATE) <= pd.Timestamp(date)


def _sel(u, technology, mask=None):
    m = (u["technology"] == technology)
    return u[m if mask is None else m & mask]


def _stock(u, date, reg_by=None) -> pd.DataFrame:
    m = rs.operational_at(u, date)
    if reg_by is not None:
        m &= registered_by(u, reg_by)
    return _sel(u, "battery", m)


def _planned_at(u, date) -> pd.DataFrame:
    """Batteries registered by ``date`` and not commissioned by then (planned at that date)."""
    d = pd.Timestamp(date)
    notyet = (u["reg_commissioning_date"] > d) | (
        u["reg_commissioning_date"].isna() & (u["reg_status"] == rs.STATUS_PLANNED))
    return _sel(u, "battery", notyet & registered_by(u, d))


def _added(u, technology, start, end, reg_by=None) -> pd.DataFrame:
    m = (u["reg_op_excluded_reason"] == "") & (u["reg_op_start"] >= pd.Timestamp(start)) & (
        u["reg_op_start"] <= pd.Timestamp(end))
    if reg_by is not None:
        m &= registered_by(u, reg_by)
    return _sel(u, technology, m)


def _kw(df, col="gross_kw"):
    return float(df[col].sum())


def _kwh_share(df) -> float:
    return float(df["usable_kwh_alloc"].notna().mean()) if len(df) else np.nan


def mv_scope(u: pd.DataFrame, export_date) -> dict:
    """Operating batteries by voltage coverage at the export date."""
    ops = _sel(u, "battery", rs.operational_at(u, export_date))
    rank = ops["voltage_level"].map(voltage_rank)
    mv = ops[rank >= MV_MIN_RANK]
    return {"ops": ops, "mv": mv, "n_ops": len(ops), "n_known": int(rank.notna().sum()),
            "n_ambiguous": int((rank == 1).sum()), "n_unknown": int(rank.isna().sum())}


def grid_coverage(units: pd.DataFrame) -> pd.DataFrame:
    """Units with a location ID and with a voltage level, by technology and status."""
    g = units.assign(
        has_location=units["location_id"].astype(str).str.len() > 0,
        has_voltage=units["voltage_level"].notna() if "voltage_level" in units else False,
        has_operator=units["grid_operator_id"].notna() if "grid_operator_id" in units else False,
    )
    return (
        g.groupby(["technology", "reg_status"], dropna=False)
        .agg(units=("unit_id", "size"), with_location_id=("has_location", "sum"),
             with_voltage_level=("has_voltage", "sum"), with_grid_operator_id=("has_operator", "sum"),
             gross_mw=("gross_kw", lambda s: s.sum() / 1000.0))
        .reset_index()
        .assign(share_with_voltage=lambda d: d["with_voltage_level"] / d["units"])
    )


def _pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x:.0%}"


def _allsize_added(pv_all: pd.DataFrame, catalogue: dict, start, end, reg_by) -> tuple[int, float, float]:
    """Ground-mounted PV of ALL sizes commissioned in [start, end], operating statuses, registered by reg_by.

    Returns (units, net MW, units whose net power is missing and fall back to gross).
    """
    a = pv_all.copy()
    status = a["EinheitBetriebsstatus"].map(lambda v: catalogue.get(str(v).strip(), str(v).strip()))
    com = pd.to_datetime(a["Inbetriebnahmedatum"].astype("string").str[:10], format="%Y-%m-%d", errors="coerce")
    reg = pd.to_datetime(a["Registrierungsdatum"].astype("string").str[:10], format="%Y-%m-%d", errors="coerce")
    m = status.isin(rs.OPERATIONAL_STATUSES) & (com >= pd.Timestamp(start)) & (com <= pd.Timestamp(end)) & (
        reg.fillna(MIN_DATE) <= pd.Timestamp(reg_by)) & ~a["EinheitMastrNummer"].duplicated()
    net = pd.to_numeric(a["Nettonennleistung"].astype("string").str.replace(",", "."), errors="coerce")
    gross = pd.to_numeric(a["Bruttoleistung"].astype("string").str.replace(",", "."), errors="coerce")
    kw = net.fillna(gross)[m]
    return int(m.sum()), float(kw.sum() / 1000.0), int(net[m].isna().sum())


def compare_with_statistics(
    units: pd.DataFrame, export_date, is_partial: bool, grid_join_available: bool,
    catalogue: dict | None = None, pv_allsize: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per reference figure and per variant, each with an explanation (see module doc)."""
    u = rs.operation_intervals(units) if "reg_op_excluded_reason" not in units else units
    export_date = pd.Timestamp(export_date)
    rows: list[dict] = []

    def add(metric, ours, variant, comparable, klass, text, ref_key=None, tol=None):
        key = ref_key or metric
        ref = REFS.get(key)
        value = ref[0] if ref else np.nan
        ratio = ours / value if ref and value and pd.notna(ours) else np.nan
        within = (
            f" The reference is rounded to {tol}, so a difference below {tol / 2:g} is not distinguishable from agreement."
            if tol is not None and ref and pd.notna(ours) and abs(ours - value) <= tol / 2 else ""
        )
        status = ("pending_full_export" if is_partial else
                  "not_comparable" if comparable == "no" else
                  "not_computable" if pd.isna(ours) else "computed")
        rows.append({
            "metric": metric, "value": value, "unit": ref[1] if ref else "", "stichtag": ref[2] if ref else "",
            "basis": ref[3] if ref else "", "source": ref[4] if ref else "", "grade": ref[5] if ref else "",
            "reference_file": REFERENCE_FILE, "ours": ours, "ours_variant": variant,
            "ratio_ours_to_reference": ratio, "comparable": comparable, "explanation_class": klass,
            "explanation": text + within, "status": status, "quantity_type": "observed",
        })

    # ---- in operation at the reference date -------------------------------------------------
    s_reg = _stock(u, REF_DATE, REF_DATE)
    s_all = _stock(u, REF_DATE)
    late = s_all[~registered_by(s_all, REF_DATE)]
    gross = _kw(s_reg) / 1e6
    add("bess_in_operation_gross_gw", gross,
        "operating on 2025-10-15 and registered by 2025-10-15", "yes", "reference date",
        f"Rebuilt at the reference date from commissioning, shutdown and registration dates; same size rule (gross, "
        f">999 kW). {len(late)} units ({_kw(late) / 1e6:.3f} GW) registered after the reference date are left out. "
        "Status changes and deletions after that date cannot be undone, so a residual remains unexplained.", tol=0.1)
    add("bess_in_operation_gross_gw", _kw(s_all) / 1e6, "same, including units registered later (backfill)",
        "partly", "reference date",
        f"Sensitivity: today's registry content dated back. Differs from the row above by the {len(late)} late "
        "registrations, which the reference could not contain.", tol=0.1)
    add("bess_in_operation_usable_gwh", s_reg["usable_kwh_alloc"].sum() / 1e6,
        "operating on 2025-10-15 and registered by 2025-10-15", "yes", "reference date; coverage",
        "As above for usable capacity. " + (
            "All of these units carry a plant capacity. " if _kwh_share(s_reg) >= 1.0 else
            f"Only {_pct(_kwh_share(s_reg))} of these units carry a plant capacity, so ours is a lower bound. ")
        + "Plant kWh is split across linked units by gross power.", tol=0.1)

    # ---- planned at the reference date --------------------------------------------------------
    pl = _planned_at(u, REF_DATE)
    pl_now = _sel(u, "battery", u["reg_status"] == rs.STATUS_PLANNED)
    add("bess_planned_gross_gw", _kw(pl) / 1e6,
        "registered by 2025-10-15 and not commissioned by then (reconstructed)", "partly", "reference date; definition",
        f"Reconstructed: {len(pl)} units registered by the reference date whose commissioning date is after it or whose "
        "status is still In Planung without one. Status history is not in the export, units deleted or "
        "re-registered since are missing, and BNetzA's planned class may use the status as entered then; "
        "the remaining gap is unexplained. The quarterly snapshot of 2025-10-01 would settle it (see below).")
    add("bess_planned_usable_gwh", pl["usable_kwh_alloc"].sum() / 1e6,
        "registered by 2025-10-15 and not commissioned by then (reconstructed)", "partly", "reference date; coverage",
        f"As above for usable capacity; {_pct(_kwh_share(pl))} of these units have a plant capacity.")
    add("bess_planned_gross_gw", _kw(pl_now) / 1e6, "status In Planung at the export date",
        "no", "reference date",
        f"Not comparable: {len(pl_now)} units planned on {export_date.date()}, thirteen months after the reference "
        "date. Shown only to document why the raw ratio is misleading.")
    add("bess_planned_usable_gwh", pl_now["usable_kwh_alloc"].sum() / 1e6, "status In Planung at the export date",
        "no", "reference date", "Not comparable, same reason as the gross row.")

    # ---- medium voltage and above ----------------------------------------------------------------
    mvs = mv_scope(u, export_date)
    if grid_join_available:
        txt = (
            f"Scope: ours is batteries from 1 MW only, operating at the export date, with the voltage level from the "
            f"grid connection point (Mittelspannung and above; the Umspannebene Mittel-/Niederspannung value and texts joining a low "
            f"and a higher level, such as Mittelspannung;Niederspannung, are excluded as ambiguous, {mvs['n_ambiguous']} units). Voltage level is known for {mvs['n_known']} of "
            f"{mvs['n_ops']} operating units ({_pct(mvs['n_known'] / mvs['n_ops'] if mvs['n_ops'] else np.nan)}); the "
            f"other {mvs['n_unknown']} cannot be classed, and planned units are never joined (no location ID). "
            "The reference covers storage of any technology and probably any size at these levels and has no "
            "stated date, so a lower count is expected. Compare the upper-bound row.")
        ours_n, ours_gw = float(len(mvs["mv"])), _kw(mvs["mv"], "net_kw") / 1e6
    else:
        txt = "Voltage level unavailable (grid join not possible in this run)."
        ours_n = ours_gw = np.nan
    add("bess_mv_and_above_units", ours_n, "operating batteries >= 1 MW with voltage level Mittelspannung or above",
        "partly", "size class; coverage; definition", txt)
    add("bess_mv_and_above_net_gw", ours_gw, "same, net power", "partly", "size class; coverage; definition",
        "As the units row; net power as in the reference.")
    add("bess_mv_and_above_units", float(mvs["n_ops"]),
        "upper bound: ALL operating batteries >= 1 MW, voltage known or not", "partly", "size class",
        f"If even every operating battery from 1 MW ({mvs['n_ops']}) is below the reference "
        f"({REFS['bess_mv_and_above_units'][0]:,}), the gap is definitional (technology and units below 1 MW), "
        "not a join problem.")
    add("bess_mv_and_above_net_gw", _kw(mvs["ops"], "net_kw") / 1e6,
        "upper bound: all operating batteries >= 1 MW, net power", "partly", "size class",
        (f"Upper bound for the net power row. It is {'above' if _kw(mvs['ops'], 'net_kw') / 1e6 > REFS['bess_mv_and_above_net_gw'][0] else 'below'} "
         "the reference, so unlike the units row it does not show a scope gap by itself: the GW comparison stays "
         "unexplained beyond scope (reference date unknown, technology and size mix of the reference unknown)."),
        ref_key="bess_mv_and_above_net_gw")

    # ---- additions 2025 ------------------------------------------------------------------------------
    spread = (REFS["bess_added_2025_mwh_energycharts"][0] / REFS["bess_added_2025_mwh"][0] - 1)
    a_bc = _added(u, "battery", "2025-01-01", "2025-12-31", BC_DATA_DATE)
    a_all = _added(u, "battery", "2025-01-01", "2025-12-31")
    n_late = len(a_all) - len(a_bc)
    refnote = (
        f" The two references disagree with each other by {spread:.0%} on MWh; Battery-Charts (opened page, fact 15) "
        "is the more reliable, Energy-Charts was seen only in a search summary (open question 3 in the reference "
        "file); another trade-press article gives 61 units, 520 MW, 767 MWh for 2025 and was seen only in a search "
        "summary (reference file line 47). No agreement is claimed from "
        "closeness to either. Registration date of the reference counting rule is unknown; we count by commissioning date.")
    add("bess_added_2025_units", float(len(a_bc)), "commissioned 2025, registered by 2026-01-06",
        "partly", "reference date; definition; source weakness",
        f"{n_late} of {len(a_all)} units commissioned in 2025 were registered after the Battery-Charts data date and "
        "are left out. Size class '> 1 MW' vs ours gross >= 1 MW." + refnote)
    add("bess_added_2025_mw", _kw(a_bc) / 1e3, "commissioned 2025, registered by 2026-01-06 (gross)",
        "partly", "reference date; gross versus net; source weakness",
        "Power basis of the reference is not stated; ours is gross." + refnote)
    add("bess_added_2025_mwh", a_bc["usable_kwh_alloc"].sum() / 1e3, "commissioned 2025, registered by 2026-01-06",
        "partly", "reference date; coverage; source weakness",
        f"Usable capacity known for {_pct(_kwh_share(a_bc))} of these units." + refnote)
    a_ec = _added(u, "battery", "2025-01-01", "2025-12-31", EC_EXPORT_DATE)
    add("bess_added_2025_mwh_energycharts", a_ec["usable_kwh_alloc"].sum() / 1e3,
        "commissioned 2025, registered by 2026-10-13", "partly", "source weakness; definition",
        "Reference rests on a source that was not opened; its size class and counting rule are unknown." + refnote)
    add("bess_added_2025_mwh", a_all["usable_kwh_alloc"].sum() / 1e3,
        "commissioned 2025, all registrations to the export date", "no", "reference date",
        "Sensitivity only: includes registrations after the reference data date.", ref_key="bess_added_2025_mwh")

    # ---- additions 2026 --------------------------------------------------------------------------------
    a26 = _added(u, "battery", "2026-01-01", "2026-09-30", EC_EXPORT_DATE)
    t26 = ("Reference seen only in a search summary; size class and whether it counts commissioning or "
           "registration are unknown. Ours counts commissioning dates, registered by 2026-10-13 (the Energy-Charts export "
           f"date); our own export is {export_date.date()}.")
    add("bess_added_2026_jan_sep_mwh", a26["usable_kwh_alloc"].sum() / 1e3, "commissioned 2026-01 to 2026-09",
        "partly", "source weakness; definition", t26)
    add("bess_added_2026_jan_sep_mw", _kw(a26) / 1e3, "commissioned 2026-01 to 2026-09 (gross)",
        "partly", "source weakness; gross versus net", t26)

    # ---- ground-mounted PV ------------------------------------------------------------------------------
    p25 = _added(u, "ground_pv", "2025-01-01", "2025-12-31")
    p26 = _added(u, "ground_pv", "2026-01-01", "2026-08-31")
    tp = ("Not comparable: the reference covers ground-mounted PV of ALL sizes, ours only units from 1 MWp, so ours is "
          "lower by construction and the ratio says nothing about completeness. Power basis of the reference is not "
          "stated (ours net). Trade press, preliminary, with a stated 15 % allowance for late registrations.")
    add("pv_ground_added_2025_mw", _kw(p25, "net_kw") / 1e3, "units >= 1 MWp, commissioned 2025 (net)",
        "no", "size class", tp)
    add("pv_ground_added_2026_jan_aug_mw", _kw(p26, "net_kw") / 1e3, "units >= 1 MWp, commissioned 2026-01 to 2026-08 (net)",
        "no", "size class", tp)
    if pv_allsize is not None and catalogue is not None:
        for key, start, end, by, what in (
            ("pv_ground_added_2025_mw", "2025-01-01", "2025-12-31", "2026-01-08",
             ("registered by 2026-01-08 (date of the BNetzA press release on 2025, fact 12; the trade-press data date "
              "is not stated)")),
            ("pv_ground_added_2026_jan_aug_mw", "2026-01-01", "2026-08-31", "2026-09-14",
             "registered by 2026-09-14 (data date of the reference, fact 14)"),
        ):
            n, mw, n_nonet = _allsize_added(pv_allsize, catalogue, start, end, by)
            ref = REFS[key][0]
            add(key, mw, f"ALL sizes ground-mounted, commissioned {start[:7]} to {end[:7]}, {what.split(' (')[0]} (net)",
                "partly", "gross versus net; definition; source weakness",
                f"Like for like on size: all ground-mounted units of any size from the same export ({n:,} units), "
                f"{what}. The reference is preliminary trade press with a stated 15 % allowance for late "
                f"registrations, so a ratio of about {1 / 1.15:.2f} to 1.0 is not distinguishable from agreement. "
                f"Power basis of the reference is not stated (ours net, gross where net is missing: {n_nonet} units). "
                f"Ours is {mw / ref:.2f} of the reference; the remainder is unexplained.", ref_key=key)

    return pd.DataFrame(rows)
