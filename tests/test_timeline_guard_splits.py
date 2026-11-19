"""Circularity guard, freeze guard, feature adapter and fold assignment. Fake data only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bo.features.allowlist import FEATURE_COLUMNS
from bo.timeline import adapter, leadtime, splits
from bo.timeline.guard import (
    CircularityError,
    FreezeError,
    assert_no_registry_inputs,
    guard_folds,
    require_model_freeze,
    write_model_freeze,
)

FEATS = ["s1_vv_c", "s2_ndpi_c", "s2_b11_c_yoy"]


def _fake_frame():
    rng = np.random.default_rng(0)
    months = pd.date_range("2024-01-01", periods=12, freq="MS")
    rows = []
    for sid in ("A", "B"):
        for m in months:
            if sid == "A" and m.month in (3, 4):
                continue  # missing rows must become NaN months, not be interpolated
            rows.append({"site_id": sid, "month": m, **{f: rng.normal() for f in FEATS}})
    return pd.DataFrame(rows)


def test_allow_list_passes_guard():
    assert_no_registry_inputs(["site_id", "month", *FEATURE_COLUMNS])


@pytest.mark.parametrize("col", ["reg_commissioning_date", "site_reg_date", "status", "power_kw",
                                 "commissioned", "MaStR_id", "capacity_mw", "usable_kwh",
                                 "other_registered_sites_in_chip", "Inbetriebnahmedatum",
                                 "registration_month", "some_unknown_feature"])
def test_guard_refuses(col):
    with pytest.raises(CircularityError):
        assert_no_registry_inputs(pd.DataFrame(columns=["site_id", "month", "s1_vv_c", col]))


def test_freeze_guard(tmp_path):
    fz = tmp_path / "model_freeze.json"
    with pytest.raises(FreezeError):
        require_model_freeze(fz)
    with pytest.raises(FreezeError):
        guard_folds([1, 0], fz)
    guard_folds([1, 2, 3, 4], fz)  # development folds need no freeze
    with pytest.raises(FreezeError):
        leadtime.join_registry_dates(pd.DataFrame({"site_id": ["A"]}),
                                     pd.DataFrame({"site_id": ["A"], "reg_date": ["2024-01-01"]}), fz)
    with pytest.raises(CircularityError):
        write_model_freeze({"config_hash": "x", "features": ["power_kw"], "hyperparameters": {},
                            "date": "2026-11-19"}, fz)
    rec = {"config_hash": "x", "features": FEATS, "hyperparameters": {}, "date": "2026-11-19"}
    write_model_freeze(rec, fz)
    assert json.loads(fz.read_text())["features"] == FEATS
    with pytest.raises(FreezeError):
        write_model_freeze(rec, fz)
    guard_folds([0], fz)
    out = leadtime.join_registry_dates(pd.DataFrame({"site_id": ["A"]}),
                                       pd.DataFrame({"site_id": ["A"], "reg_date": ["2024-01-01"]}), fz)
    assert len(out) == 1


def test_lead_interval():
    lo, hi = leadtime.lead_interval(np.array([10]), np.array([12.4]))
    assert lo[0] == pytest.approx(1.4) and hi[0] == pytest.approx(2.4)
    lo, hi = leadtime.lead_interval(np.array([10]), np.array([12.4]), upper_bound=np.array([2.0]))
    assert hi[0] == pytest.approx(2.0)
    with pytest.raises(ValueError):
        leadtime.lead_interval(np.array([10]), np.array([12.4]), upper_bound=np.array([1.0]))


def test_adapter_builds_gap_free_axis(tmp_path):
    df = _fake_frame()
    out = adapter.to_series(df, FEATS, folds={"A": 1, "B": 2}, freeze_path=tmp_path / "none.json")
    a = next(s for s in out if s.site_id == "A")
    assert len(a.months) == 12 and a.x.shape == (12, 3)
    assert np.isnan(a.x[2]).all() and np.isnan(a.x[3]).all()
    assert not np.isnan(a.x[[0, 1, 4]]).any()


def test_adapter_refuses_registry_column_and_test_fold(tmp_path):
    df = _fake_frame()
    with pytest.raises(CircularityError):
        adapter.to_series(df.assign(reg_commissioning_date="2024-05-01"), FEATS)
    with pytest.raises(FreezeError):
        adapter.to_series(df, FEATS, folds={"A": 0, "B": 2}, freeze_path=tmp_path / "none.json")
    with pytest.raises(ValueError):
        adapter.to_series(df, FEATS, folds={"A": 1})
    with pytest.raises(ValueError):
        adapter.to_series(df, ["s1_vv_c"] * 7)


def test_adapter_standardiser():
    df = _fake_frame()
    st = adapter.fit_standardiser(df, FEATS, {"A": 1, "B": 3})
    out = adapter.to_series(df, FEATS, standardiser=st)
    allx = np.vstack([s.x for s in out])
    np.testing.assert_allclose(np.nanmean(allx, axis=0), 0, atol=1e-12)


def test_standardiser_refuses_test_fold_and_unassigned_sites():
    """Review m6: the fold map is required and fold-0 rows are refused, never filtered silently."""
    df = _fake_frame()
    with pytest.raises(ValueError, match="test fold"):
        adapter.fit_standardiser(df, FEATS, {"A": 0, "B": 2})
    with pytest.raises(ValueError, match="without a fold"):
        adapter.fit_standardiser(df, FEATS, {"A": 1})
    with pytest.raises(TypeError):
        adapter.fit_standardiser(df, FEATS, None)
    # The split table itself is accepted; ids resolve through queue_id or site_id.
    split = pd.DataFrame({"queue_id": ["q1", "A"], "site_id": ["B", None], "cluster_id": [0, 1],
                          "block_id": ["E1N1", "E2N2"], "fold": [2, 4], "role": "development"})
    st = adapter.fit_standardiser(df, FEATS, split)
    assert st.features == tuple(FEATS)
    split.loc[0, "fold"] = 0
    with pytest.raises(ValueError, match="test fold"):
        adapter.fit_standardiser(df, FEATS, split)


def test_fold_map_keys_and_conflicts():
    split = pd.DataFrame({"queue_id": ["q1", "q2"], "site_id": ["S1", None], "fold": [0, 3]})
    assert splits.fold_map(split) == {"q1": 0, "S1": 0, "q2": 3}
    with pytest.raises(ValueError, match="two folds"):
        splits.fold_map(pd.DataFrame({"queue_id": ["q1", "S1"], "site_id": ["S1", None], "fold": [0, 3]}))


# ------------------------------------------------------------------ registry fields reaching the timeline (m7)

# Snapshot of the columns of data/processed/registry/registry_sites.parquet (2026-11-19); the live schema
# is added when the file exists.
REGISTRY_SITE_COLUMNS = (
    "site_id", "technology", "n_units", "n_units_with_coords", "unit_ids", "location_ids", "lat", "lon",
    "coord_state", "site_extent_m", "gross_kw", "net_kw", "power_kw", "usable_kwh", "reg_status",
    "reg_status_set", "bundesland", "landkreis", "grid_operator_id", "voltage_level",
    "reg_registration_date_first", "reg_commissioning_date_first", "reg_commissioning_date_last",
    "reg_planned_commissioning_date_last", "n_locations", "coord_precision_class", "coord_unc_m",
    "reg_flag_late_registration_any", "reg_flag_registered_before_commissioning_any",
    "flag_coord_rounded_any", "flag_power_implausible_any", "flag_duplicate_candidate_any", "colocated_pv",
    "colocated_bess", "colocated_site_ids", "shares_location_id_other_tech", "location_id_partner_site_ids",
    "nearest_other_tech_site_m", "declared_storage_pv_link", "data_partial", "quantity_type", "geometry")
TIMELINE_MODEL_MODULES = ("adapter", "bocpd", "hmm", "events", "npmle")


def _registry_columns() -> list[str]:
    from bo.paths import PROCESSED

    cols = set(REGISTRY_SITE_COLUMNS)
    f = PROCESSED / "registry" / "registry_sites.parquet"
    if f.is_file():
        import pyarrow.parquet as pq

        cols |= set(pq.read_schema(f).names)
    return sorted(cols)


def test_only_registry_technology_reaches_the_timeline():
    """Plan 3.1 / 6.1: technology selects the emission set; no other registry field can reach the timeline."""
    assert adapter.REGISTRY_FIELDS_TO_TIMELINE == ("technology",)
    reg_cols = _registry_columns()
    # (1) No registry column, technology included, passes the model-input guard (site_id is the join key).
    for c in reg_cols:
        if c == "site_id":
            continue
        with pytest.raises(CircularityError):
            assert_no_registry_inputs(["site_id", "month", "s1_vv_c", c])
    # (2) emission_sets is a function of technology alone: scrambling every other column changes nothing.
    rng = np.random.default_rng(3)
    n = 6
    reg = pd.DataFrame({c: rng.normal(size=n) for c in reg_cols})
    reg["site_id"] = [f"S{i}" for i in range(n)]
    reg["technology"] = ["battery", "ground_pv"] * 3
    ref = adapter.emission_sets(reg)
    scrambled = reg.copy()
    for c in reg_cols:
        if c not in ("site_id", "technology"):
            scrambled[c] = rng.permutation(scrambled[c].to_numpy())
    assert adapter.emission_sets(scrambled) == ref
    assert adapter.emission_sets(reg[["site_id", "technology"]]) == ref
    assert set(ref.values()) <= set(adapter.EMISSION_SETS)
    with pytest.raises(ValueError):
        adapter.emission_sets(reg.assign(technology="hydro"))
    # Grouping hands on series objects only; the technology string never enters x.
    series = adapter.to_series(_fake_frame().assign(site_id=lambda d: d["site_id"].map({"A": "S0", "B": "S1"})),
                               FEATS)
    groups = adapter.group_by_emission_set(series, ref)
    assert [s.site_id for s in groups["battery"]] == ["S0"]
    assert [s.site_id for s in groups["ground_pv"]] == ["S1"]
    assert groups["battery"][0].features == tuple(FEATS)


def test_timeline_model_code_names_no_other_registry_field():
    """Static check: model modules import nothing from bo.data and name no registry column but the keys."""
    import ast
    import importlib

    reg_cols = set(_registry_columns())
    permitted = {"site_id", "technology"}
    for mod in TIMELINE_MODEL_MODULES:
        src_file = importlib.import_module(f"bo.timeline.{mod}").__file__
        tree = ast.parse(Path(src_file).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("bo.data"), f"{mod} imports {node.module}"
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith("bo.data") for a in node.names), mod
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                hit = node.value in reg_cols and node.value not in permitted
                assert not hit, f"{mod} names registry column {node.value!r}"
                assert not node.value.startswith(("reg_", "site_reg_")), f"{mod}: {node.value!r}"


# ------------------------------------------------------------------ splits


def _fake_queue():
    rng = np.random.default_rng(1)
    lat = np.r_[rng.uniform(48, 54, 60), [52.0, 52.01]]  # last two within 2 km of each other
    lon = np.r_[rng.uniform(7, 14, 60), [10.0, 10.0]]
    n = len(lat)
    q = pd.DataFrame({"queue_id": [f"q{i}" for i in range(n)], "site_id": [f"s{i}" for i in range(n)],
                      "lat": lat, "lon": lon,
                      "bundesland": rng.choice(["Bayern", "Saarland", "Mecklenburg-Vorpommern"], n)})
    tech = pd.Series(rng.choice(["battery", "ground_pv", None], n), index=q["queue_id"])
    return q, tech


def test_clusters_are_atomic_and_folds_complete():
    q, tech = _fake_queue()
    site = splits.assign(q, tech, seed=7)
    assert set(site["fold"]) <= set(range(5))
    assert site.groupby("cluster_id")["fold"].nunique().max() == 1
    assert site.groupby("block_id")["fold"].nunique().max() == 1
    assert site.loc[site.queue_id == "q60", "cluster_id"].item() == \
        site.loc[site.queue_id == "q61", "cluster_id"].item()
    # Deterministic for a fixed seed.
    assert splits.content_hash(site) == splits.content_hash(splits.assign(q, tech, seed=7))
    assert "lat" not in site.columns and "lon" not in site.columns


def test_balance_uses_all_folds_evenly():
    rng = np.random.default_rng(3)
    counts = pd.DataFrame(rng.integers(0, 4, (100, 4)), columns=list(splits.COUNT_COLS))
    fold = splits.balance_folds(counts, seed=1)
    assert set(fold) == set(range(5))
    tot = counts.groupby(fold).sum()
    target = counts.sum() / 5
    assert ((tot - target).abs() / target).to_numpy().max() < 0.1


def test_single_linkage_chains():
    x = np.array([0.0, 1500.0, 3000.0, 10000.0])
    cl = splits.cluster_sites(x, np.zeros(4))
    assert cl[0] == cl[1] == cl[2] != cl[3]


def test_block_of_is_origin_aligned():
    assert splits.block_of(49_999.0, 50_000.0) == (0, 1)
    assert splits.block_of(-1.0, 0.0) == (-1, 0)


def test_build_refuses_overwrite_without_force(tmp_path):
    q, tech = _fake_queue()
    qp, sp = tmp_path / "q.parquet", tmp_path / "s.parquet"
    q.to_parquet(qp)
    tech.rename("technology").reset_index().to_parquet(sp)
    kw = {"out": tmp_path / "b.parquet", "summary": tmp_path / "s.csv",
          "force_log": tmp_path / "f.csv", "queue_path": qp, "strata_path": sp, "seed": 7}
    summ = splits.build(**kw)
    assert summ.loc[summ.fold == "all", "n_sites"].item() == len(q)
    with pytest.raises(FileExistsError):
        splits.build(**kw)
    with pytest.raises(ValueError):
        splits.build(force=True, **kw)
    splits.build(force=True, reason="test", **kw)
    assert len(pd.read_csv(tmp_path / "f.csv")) == 1
