"""Tests for the round-1 queue DOP index helpers (synthetic data, no network)."""

import pandas as pd

from bo.imagery import dop, dop_queue


def test_chip_key_uses_site_id_else_queue_id():
    assert dop_queue.chip_key({"site_id": "BESS-1", "queue_id": "L1-0001"}) == "BESS-1"
    assert dop_queue.chip_key({"site_id": float("nan"), "queue_id": "L1-0002"}) == "L1-0002"


def test_coverage_exclusive_counts_no_coordinates_and_drops_mv():
    q = pd.DataFrame({
        "queue_id": ["L1-1", "L1-2", "L1-3", "L1-4"], "site_id": ["A", "B", None, "D"],
        "stratum": ["pilot", "pilot", "hard_negative", "pilot"],
        "lat": [1.0] * 4, "lon": [2.0] * 4,
        "bundesland": ["Bayern", "Bayern", "Bayern", "Mecklenburg-Vorpommern"]})
    idx = pd.DataFrame({"site_id": ["A", "L1-3", "D"], "chip_ok": [True, True, True],
                        "date_type": ["day", "none", "day"]})
    c = dop_queue.coverage(idx, q)
    assert not {"lat", "lon"} & set(c.columns)
    assert "Mecklenburg-Vorpommern" not in set(c.bundesland)
    by = c[(c.stratum == "pilot") & (c.bundesland == "Bayern")].iloc[0]
    assert (by.n_queue_rows, by.n_day, by.n_no_chip) == (2, 1, 1)
    assert c.n_queue_rows.sum() == 3
    assert (c.n_queue_rows == c[["n_day", "n_year_edition", "n_production_only", "n_date_none",
                                 "n_no_chip"]].sum(axis=1)).all()


def test_bayern_history_source_layers():
    s = dop.bayern_history_source(2018)
    assert s.layer == "by_dop_2018_h" and s.info_layer == "by_dop_2018_h_info"
    assert s.url.endswith("/histdop/v1/histdop") and s.licence == dop.SOURCES["Bayern"].licence
