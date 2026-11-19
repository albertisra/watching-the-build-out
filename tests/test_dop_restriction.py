"""Nothing derived from use-restricted DOP may reach results/ (review phase-2-r3, R3-B1)."""

import pandas as pd

from bo.imagery import dop, dop_pilot


def test_restricted_states_contains_mv():
    assert "Mecklenburg-Vorpommern" in dop.restricted_states()
    assert "Bayern" not in dop.restricted_states()


def test_coverage_never_reports_restricted_states():
    idx = pd.DataFrame(
        {
            "group": ["site", "site", "negative"],
            "state": ["Bayern", "Mecklenburg-Vorpommern", "Mecklenburg-Vorpommern"],
            "site_id": ["Q000", "Q001", "N000"],
            "chip_ok": [True, True, True],
            "flight_date": ["2025-05-01", "2025-06-01", "2025-06-02"],
            "date_type": ["day", "day", "day"],
        }
    )
    cov = dop_pilot.coverage(idx)
    assert set(cov["state"]) == {"Bayern"}


def test_drop_restricted_keeps_other_rows():
    df = pd.DataFrame({"state": ["Bayern", "Mecklenburg-Vorpommern", "Hessen"], "x": [1, 2, 3]})
    assert list(dop.drop_restricted(df)["state"]) == ["Bayern", "Hessen"]
