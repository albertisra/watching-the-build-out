"""Monthly operational capacity on synthetic units, with each date rule exercised."""

import numpy as np
import pandas as pd
import pytest

from bo.data import registry_compare as rc
from bo.data import registry_series as rs

T = pd.Timestamp
EXPORT = T("2026-11-16")


def _u(**kw):
    base = {
        "unit_id": "SEE0", "technology": "battery", "bundesland": "Bayern", "gross_kw": 1000.0,
        "net_kw": 900.0, "usable_kwh_alloc": 2000.0, "reg_status": "In Betrieb",
        "reg_commissioning_date": T("2024-03-10"), "reg_shutdown_final_date": pd.NaT,
        "reg_shutdown_temp_begin_date": pd.NaT, "reg_resumption_date": pd.NaT,
        "reg_last_update": T("2026-01-01"),
    }
    return {**base, **kw}


def _df(rows):
    df = pd.DataFrame(rows)
    df["unit_id"] = [f"SEE{i}" for i in range(len(df))]
    for c in ("reg_commissioning_date", "reg_shutdown_final_date", "reg_shutdown_temp_begin_date",
              "reg_resumption_date", "reg_last_update"):
        df[c] = pd.to_datetime(df[c])
    return rs.operation_intervals(df)


def _stock(monthly, month, tech="battery", col="gross_mw"):
    s = monthly[(monthly["month"] == month) & (monthly["technology"] == tech)]
    return s[col].sum()


def test_simple_commissioning_counts_from_month_of_commissioning():
    m = rs.monthly_capacity(_df([_u()]), EXPORT)
    assert _stock(m, "2024-02") == 0.0
    assert _stock(m, "2024-03") == pytest.approx(1.0)
    assert _stock(m, "2026-11") == pytest.approx(1.0)
    assert _stock(m, "2024-03", col="usable_mwh") == pytest.approx(2.0)
    row = m[(m["month"] == "2024-03")].iloc[0]
    assert row["added_units"] == 1 and row["added_gross_mw"] == pytest.approx(1.0)
    assert bool(m[m["month"] == "2026-11"]["is_partial_month"].iloc[0])


def test_planned_missing_and_placeholder_dates_are_excluded_and_reported():
    df = _df([
        _u(reg_status="In Planung"),
        _u(reg_commissioning_date=pd.NaT),
        _u(),
    ])
    assert list(df["reg_op_excluded_reason"]) == [
        "status_not_operational", "no_usable_commissioning_date", ""]
    ex = rs.exclusion_summary(df).set_index("reg_op_excluded_reason")
    assert ex.loc["no_usable_commissioning_date", "units"] == 1


def test_final_shutdown_ends_operation_and_missing_date_is_imputed():
    df = _df([
        _u(reg_status="Endgültig stillgelegt", reg_shutdown_final_date=T("2025-06-20")),
        _u(reg_status="Endgültig stillgelegt", reg_last_update=T("2025-09-05")),
    ])
    assert list(df["reg_op_end_imputed"]) == [False, True]
    m = rs.monthly_capacity(df, EXPORT)
    assert _stock(m, "2025-05") == pytest.approx(2.0)
    assert _stock(m, "2025-06") == pytest.approx(1.0)  # first unit ended on 20 June
    assert _stock(m, "2025-09") == pytest.approx(0.0)


def test_temporary_shutdown_gap_and_resumption():
    df = _df([
        _u(reg_shutdown_temp_begin_date=T("2025-01-15"), reg_resumption_date=T("2025-04-02")),
        _u(reg_status="Vorübergehend stillgelegt", reg_shutdown_temp_begin_date=T("2025-08-01")),
    ])
    m = rs.monthly_capacity(df, EXPORT)
    assert _stock(m, "2024-12") == pytest.approx(2.0)
    assert _stock(m, "2025-02") == pytest.approx(1.0)
    assert _stock(m, "2025-04") == pytest.approx(2.0)
    assert _stock(m, "2025-08") == pytest.approx(1.0)
    assert _stock(m, "2026-11") == pytest.approx(1.0)


def test_shutdown_before_commissioning_is_excluded():
    df = _df([_u(reg_status="Endgültig stillgelegt", reg_shutdown_final_date=T("2023-01-01"))])
    assert df["reg_op_excluded_reason"].iloc[0] == "shutdown_not_after_commissioning"


def test_by_state_and_technology_and_national_total():
    df = _df([
        _u(),
        _u(bundesland="Sachsen", gross_kw=3000.0, net_kw=3000.0, usable_kwh_alloc=np.nan),
        _u(technology="ground_pv", gross_kw=5000.0, net_kw=4800.0, usable_kwh_alloc=np.nan,
           reg_commissioning_date=T("2025-02-01")),
        _u(bundesland=None, gross_kw=500.0),
    ])
    m = rs.monthly_capacity(df, EXPORT)
    assert _stock(m, "2026-10") == pytest.approx(4.5)
    assert set(m["bundesland"]) == {"Bayern", "Sachsen", rs.UNKNOWN_STATE}
    nat = rs.national_totals(m)
    got = nat[(nat["month"] == "2026-10") & (nat["technology"] == "ground_pv")]
    assert got["net_mw"].iloc[0] == pytest.approx(4.8)
    # usable MWh only counts units with a known capacity
    sachsen = m[(m["bundesland"] == "Sachsen") & (m["month"] == "2026-10")].iloc[0]
    assert sachsen["usable_mwh"] == 0.0 and sachsen["units_kwh_known"] == 0


def test_series_agrees_with_capacity_at_on_month_ends():
    df = _df([
        _u(),
        _u(reg_commissioning_date=T("2025-07-31")),
        _u(reg_shutdown_temp_begin_date=T("2025-01-15"), reg_resumption_date=T("2025-04-02")),
        _u(reg_status="Endgültig stillgelegt", reg_shutdown_final_date=T("2025-06-20")),
    ])
    m = rs.monthly_capacity(df, EXPORT)
    for month in ["2024-03", "2025-01", "2025-04", "2025-06", "2025-07", "2026-10"]:
        end = pd.Period(month, "M").to_timestamp(how="end").normalize()
        assert _stock(m, month) == pytest.approx(rs.capacity_at(df, end)["gross_mw"]), month


def _cmp_units():
    df = _df([
        _u(reg_commissioning_date=T("2025-03-01"), reg_registration_date=T("2025-03-05")),  # operating, registered
        _u(reg_commissioning_date=T("2025-09-01"), reg_registration_date=T("2026-02-01")),  # registered later
        _u(reg_status="In Planung", reg_commissioning_date=pd.NaT, reg_registration_date=T("2025-01-01"),
           gross_kw=4000.0),
        _u(reg_commissioning_date=T("2026-03-01"), reg_registration_date=T("2025-02-01"), gross_kw=2000.0),
    ])
    df["voltage_level"] = ["Mittelspannung", "Niederspannung", None, None]
    return df


def test_comparison_partial_then_full_with_explanations():
    df = _cmp_units()
    part = rc.compare_with_statistics(df, EXPORT, is_partial=True, grid_join_available=True)
    assert set(part["status"]) == {"pending_full_export"}
    full = rc.compare_with_statistics(df, EXPORT, is_partial=False, grid_join_available=True)
    assert (full["explanation"].str.len() > 20).all() and full["explanation_class"].ne("").all()
    row = full[(full["metric"] == "bess_in_operation_gross_gw") & full["ours_variant"].str.contains("registered by")]
    assert row["ours"].iloc[0] == pytest.approx(0.001)  # the unit registered 2026-02-01 is excluded
    back = full[(full["metric"] == "bess_in_operation_gross_gw") & full["ours_variant"].str.contains("backfill")]
    assert back["ours"].iloc[0] == pytest.approx(0.002)


def test_planned_reconstruction_at_reference_date():
    full = rc.compare_with_statistics(_cmp_units(), EXPORT, is_partial=False, grid_join_available=True)
    rec = full[(full["metric"] == "bess_planned_gross_gw") & full["ours_variant"].str.contains("reconstructed")]
    # In Planung (4 MW) + commissioned 2026-03 but registered 2025-02 (2 MW); the 2026-02 registration is excluded
    assert rec["ours"].iloc[0] == pytest.approx(0.006)
    now = full[(full["metric"] == "bess_planned_gross_gw") & full["comparable"].eq("no")]
    assert now["ours"].iloc[0] == pytest.approx(0.004) and now["status"].iloc[0] == "not_comparable"


def test_mv_scope_excludes_low_voltage_and_reports_coverage():
    full = rc.compare_with_statistics(_cmp_units(), EXPORT, is_partial=False, grid_join_available=True)
    mv = full[(full["metric"] == "bess_mv_and_above_units") & full["ours_variant"].str.contains("voltage level")]
    assert mv["ours"].iloc[0] == 1.0  # Mittelspannung only; Niederspannung and unknown are out
    assert "known for 2 of 3" in mv["explanation"].iloc[0]
    assert rc.voltage_rank("Mittelspannung;Niederspannung (= Hausanschluss)") == 1  # ambiguous, like MS/NS
    assert rc.voltage_rank("Umspannebene Mittelspannung/Niederspannung") == 1
    assert rc.voltage_rank("Umspannebene Hochspannung/Mittelspannung") == 3
    assert np.isnan(rc.voltage_rank(None))
    no_grid = rc.compare_with_statistics(_cmp_units(), EXPORT, is_partial=False, grid_join_available=False)
    assert no_grid[no_grid["ours_variant"].str.contains("voltage level")]["status"].eq("not_computable").all()


def test_additions_state_reference_disagreement_and_registered_by():
    full = rc.compare_with_statistics(_cmp_units(), EXPORT, is_partial=False, grid_join_available=True)
    row = full[(full["metric"] == "bess_added_2025_mwh") & full["ours_variant"].str.contains("2026-01-06")]
    assert "disagree" in row["explanation"].iloc[0] and "No agreement is claimed" in row["explanation"].iloc[0]
    units = full[(full["metric"] == "bess_added_2025_units") & full["ours_variant"].str.contains("2026-01-06")]
    assert units["ours"].iloc[0] == 1.0  # 2025-09-01 unit registered after 2026-01-06 is excluded
    pv = full[full["metric"] == "pv_ground_added_2025_mw"]
    assert pv["comparable"].iloc[0] == "no" and pv["explanation_class"].iloc[0] == "size class"


def test_grid_coverage_by_status():
    df = _cmp_units()
    df["location_id"] = ["SEL1", "SEL2", "", ""]
    cov = rc.grid_coverage(df).set_index("reg_status")
    assert cov.loc["In Planung", "with_location_id"] == 0
    assert cov.loc["In Betrieb", "with_voltage_level"] == 2


def test_pv_allsize_variant_counts_registered_by_date_and_status():
    pv = pd.DataFrame({
        "EinheitMastrNummer": ["P1", "P2", "P3", "P4", "P1"],
        "Bruttoleistung": ["12", "800", "5000", "30", "12"],
        "Nettonennleistung": ["10", "700", "", "25", "10"],
        "EinheitBetriebsstatus": ["35", "35", "35", "31", "35"],
        "Registrierungsdatum": ["2025-05-01", "2026-03-01", "2025-06-01", "2025-06-01", "2025-05-01"],
        "Inbetriebnahmedatum": ["2025-04-01", "2025-04-01", "2025-07-01", "2025-07-01", "2025-04-01"],
    })
    cat = {"35": "In Betrieb", "31": "In Planung"}
    n, mw, nonet = rc._allsize_added(pv, cat, "2025-01-01", "2025-12-31", "2026-01-08")
    assert n == 2 and nonet == 1  # P2 registered later, P4 planned, duplicate P1 dropped
    assert mw == pytest.approx((10 + 5000) / 1000)
    full = rc.compare_with_statistics(_cmp_units(), EXPORT, False, True, cat, pv)
    row = full[full["ours_variant"].str.startswith("ALL sizes") & (full["metric"] == "pv_ground_added_2025_mw")]
    assert len(row) == 1 and row["comparable"].iloc[0] == "partly"
