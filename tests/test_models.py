"""Phase 4 detector machinery on synthetic data only (no labels, no fold 0 of the real split)."""

from __future__ import annotations

import inspect
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from bo.data.registry import registry_columns
from bo.features.allowlist import FEATURE_COLUMNS
from bo.labelling.labels import append_dop_review, append_label
from bo.labelling.schema import empty_events, phase_sequence
from bo.models import design, freeze
from bo.models.assemble import add_windows, design_matrix, usable_month
from bo.models.bootstrap import block_bootstrap
from bo.models.detector import Detector, DetectorConfig, oof_predictions, tune
from bo.models.guards import (
    DENY_PATTERNS,
    LABEL_METADATA_COLUMNS,
    CircularityError,
    LeakageError,
    assert_model_inputs,
    assert_site_in_one_fold,
)
from bo.models.metrics import calibration_table, prf_table, recall
from bo.models.pipeline import develop, evaluate_test, join_inputs
from bo.models.recall_curve import fit_logistic, recall_curve, size_at_recall
from bo.models.splits import SplitsMissingError, attach_folds, load_splits, validate_splits
from bo.models.synthetic import SYN_FEATURES, make_synthetic, synthetic_targets
from bo.models.targets import TARGET_COLUMNS, monthly_targets, primary_labels, site_truth
from bo.models.threshold import kth_largest, select_threshold, site_scores
from bo.models.trackb import (
    attach_dop,
    dop_contradicted,
    open_dop_flags,
    paired_difference,
    track_b_subset,
)
from bo.timeline.guard import assert_no_registry_inputs

# ---------------------------------------------------------------- allow-list and registry deny-list


def test_allow_list_accepts_features_and_windows():
    assert_model_inputs(FEATURE_COLUMNS)
    assert_model_inputs(["s1_vv_c", "s1_vv_c__mean3", "s2_r1108_c__max6", "s1_vh_c__min12"])
    assert_model_inputs(["s1_vv_c", "dop_p_battery"], track="B")


def test_feature_columns_clear_of_registry_and_deny_patterns():
    assert registry_columns(pd.DataFrame(columns=list(FEATURE_COLUMNS))) == []
    assert not [c for c in FEATURE_COLUMNS if any(p in c.lower() for p in DENY_PATTERNS)]


@pytest.mark.parametrize("bad", [
    "reg_commissioning_date", "site_reg_status", "gross_kw", "usable_kwh", "n_units", "flag_power_outlier",
    "commissioning_year", "mastr_nr", "status", "capacity_mw", "Inbetriebnahme", "power_mw",
    "other_registered_sites_in_chip", "lat", "fold", "block_id", "site_id", "month", "mw", "stratum",
])
def test_allow_list_refuses(bad):
    with pytest.raises(CircularityError):
        assert_model_inputs(["s1_vv_c", bad])


@pytest.mark.parametrize("bad", ["s1_vv_c__mean13", "s1_vv_c__median3", "reg_x__mean3", "dop_p_pv__mean3"])
def test_window_names_checked(bad):
    with pytest.raises(CircularityError):
        assert_model_inputs([bad], track="B")


def test_dop_slot_is_track_b_only():
    with pytest.raises(CircularityError):
        assert_model_inputs(["s1_vv_c", "dop_p_battery"], track="A")


def test_design_matrix_refuses_registry_feature():
    df = pd.DataFrame({"site_id": ["a"], "month": [pd.Timestamp("2024-01-01")], "s1_vv_c": [1.0],
                       "gross_kw": [5000.0]})
    with pytest.raises(CircularityError):
        design_matrix(df, ["s1_vv_c", "gross_kw"])
    keys, x = design_matrix(df, ["s1_vv_c"])
    assert list(x.columns) == ["s1_vv_c"] and "gross_kw" in keys.columns


# ---------------------------------------------------------------- trailing windows


def test_windows_trailing_and_not_filled():
    m = pd.date_range("2024-01-01", periods=6, freq="MS")
    df = pd.DataFrame({"site_id": "a", "month": m.delete(2), "s1_vv_c": [1.0, 2.0, 4.0, 100.0, np.nan]})
    out = add_windows(df, ["s1_vv_c"], [2])
    # March is missing: April's 2-month window holds April only; no future value enters any window
    assert out["s1_vv_c__mean2"].tolist()[:4] == [1.0, 1.5, 4.0, 52.0]
    assert out["s1_vv_c__mean2"].iloc[4] == 100.0
    df2 = df.copy()
    df2.loc[df2.index[-1], "s1_vv_c"] = 1e6
    assert add_windows(df2, ["s1_vv_c"], [2])["s1_vv_c__mean2"].iloc[:4].tolist() == [1.0, 1.5, 4.0, 52.0]


def test_usable_month():
    df = pd.DataFrame({"s2_qc_flag": [0, 1, 1, np.nan], "s2_valid_c": [0.8, 0.8, 0, np.nan],
                       "s1_valid_c": [0, 0, 0.9, np.nan]})
    assert usable_month(df).tolist() == [True, False, True, False]


# ---------------------------------------------------------------- labels to targets


def _ev(tech, c, s, e, **extra):
    d = {f"{tech}_clear_month": c, f"{tech}_struct_month": s, f"{tech}_complete_month": e}
    d.update({f"{tech}_{k}": v for k, v in extra.items()})
    return d


def test_labels_read_through_labelling(tmp_path):
    kw = {"labeller_id": "author", "directory": tmp_path, "confidence": 3}
    append_label(queue_id="A", site_class="battery", events=_ev("bat", "2024-03", "2024-05", "2024-09"), **kw)
    append_label(queue_id="C", site_class="unsure", **kw)
    append_label(queue_id="A", site_class="none", is_relabel=True, **kw)
    lab = primary_labels(tmp_path, track="A", label_pass="pre_dop")
    assert lab["site_id"].tolist() == ["A"]  # relabel ignored, unsure dropped
    assert lab["site_class"].tolist() == ["battery"] and lab["bat_clear_month"].item() == "2024-03"
    assert lab["label_pass_used"].tolist() == ["pre_dop"]


def _two_pass_store(tmp_path):
    kw = {"labeller_id": "author", "directory": tmp_path}
    lid = append_label(queue_id="A", site_class="battery", confidence=2, registry_date_exposed=True,
                       events={**_ev("bat", "2024-03", "2024-05", "2024-09"), "bat_clear_conf": "1"}, **kw)
    append_label(queue_id="B", site_class="PV", confidence=3, coord_coarse=True,
                 events=_ev("pv", "not_visible", "2024-02", "2024-04"), **kw)
    append_dop_review(pass1_label_id=lid, queue_id="A", site_class="battery+PV", confidence=3,
                      dop_identity="confirms", dop_footprint="differs",
                      events={**_ev("bat", "2024-04", "2024-05", "2024-09"),
                              **_ev("pv", "before_series", "before_series", "before_series")}, **kw)


def test_pass_choice_is_explicit_and_track_a_is_sentinel_only(tmp_path):
    _two_pass_store(tmp_path)
    with pytest.raises(TypeError):
        primary_labels(tmp_path)  # no implicit pass
    with pytest.raises(ValueError, match="Track A"):
        primary_labels(tmp_path, track="A", label_pass="post_dop", missing_post_dop="drop")
    with pytest.raises(ValueError, match="missing_post_dop"):
        primary_labels(tmp_path, track="B", label_pass="post_dop")
    for name in ("track", "label_pass"):
        assert inspect.signature(primary_labels).parameters[name].default is inspect.Parameter.empty
    for name in ("onset", "brackets"):  # the author's mapping choices have no default
        assert inspect.signature(monthly_targets).parameters[name].default is inspect.Parameter.empty

    a = primary_labels(tmp_path, track="A", label_pass="pre_dop").set_index("site_id")
    assert a.loc["A", "site_class"] == "battery" and a.loc["A", "bat_clear_month"] == "2024-03"
    assert a.loc["A", "registry_date_exposed"] and not a.loc["B", "registry_date_exposed"]
    assert a.loc["A", "dop_identity"] == "confirms"  # metadata only; the class above is still pass 1
    b = primary_labels(tmp_path, track="B", label_pass="post_dop", missing_post_dop="use_pre_dop").set_index("site_id")
    assert b.loc["A", "site_class"] == "battery+PV" and b.loc["A", "bat_clear_month"] == "2024-04"
    assert b["label_pass_used"].to_dict() == {"A": "post_dop", "B": "pre_dop"}
    assert b.loc["A", "registry_date_exposed"] and b.loc["A", "confidence"] == 3
    # schema v3: coord_coarse is carried as metadata; per-event confidences follow the pass of the events
    assert a["coord_coarse"].to_dict() == {"A": False, "B": True} == b["coord_coarse"].to_dict()
    assert a.loc["A", "bat_clear_conf"] == "1" and a.loc["A", "bat_struct_conf"] == "2"  # default: item confidence
    assert b.loc["A", "bat_clear_conf"] == "3" and b.loc["A", "pv_clear_conf"] == "3"
    ta = monthly_targets(a.reset_index(), pd.DataFrame({"site_id": ["A", "B"], "month": pd.Timestamp("2024-06-01")}),
                         onset="clear", brackets="point").set_index(["site_id", "technology"])
    assert ta.loc[("A", "battery"), "onset_conf"] == 1 and ta.loc[("B", "pv"), "onset_conf"] == 3
    assert np.isnan(ta.loc[("A", "pv"), "onset_conf"])  # absent technology
    assert ta.loc[("B", "pv"), "coord_coarse"] and not ta.loc[("A", "battery"), "coord_coarse"]
    assert primary_labels(tmp_path, track="B", label_pass="post_dop",
                          missing_post_dop="drop")["site_id"].tolist() == ["A"]
    assert primary_labels(tmp_path, track="B", label_pass="pre_dop")["site_class"].tolist() == ["battery", "PV"]


def _targets(site_class, events=None, colocated="none", onset="clear", brackets="point", periods=12,
             coord_coarse=False):
    lab = pd.DataFrame([{"site_id": "s", "site_class": site_class, "colocated": colocated, **empty_events(),
                         **(events or {}), "confidence": 3, "labeller_id": "x", "registry_date_exposed": True,
                         "coord_coarse": coord_coarse, "label_pass_used": "pre_dop"}])
    keys = pd.DataFrame({"site_id": "s", "month": pd.date_range("2024-01-01", periods=periods, freq="MS")})
    t = monthly_targets(lab, keys, onset=onset, brackets=brackets)
    return {k: g.reset_index(drop=True) for k, g in t.groupby("technology")}


def test_target_mapping_onsets():
    ev = _ev("bat", "2024-03", "2024-05", "2024-09")
    t = _targets("battery", ev)
    assert t["battery"]["y"].tolist() == [0, 0] + [1] * 10
    assert t["battery"]["state"].tolist() == [0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]
    assert t["battery"]["state"].tolist() == phase_sequence(ev, "bat", [f"2024-{m:02d}" for m in range(1, 13)])
    assert t["pv"]["y"].tolist() == [0] * 12 and not t["pv"]["present"].any()
    assert t["battery"]["registry_date_exposed"].all()
    assert _targets("battery", ev, onset="struct")["battery"]["y"].tolist() == [0] * 4 + [1] * 8
    assert _targets("battery", ev, onset="complete")["battery"]["y"].tolist() == [0] * 8 + [1] * 4
    # not_visible clearing: Cl coincides with structures, so clear and struct onsets agree
    nv = _ev("pv", "not_visible", "2024-04", "after_series")
    a, b = (_targets("PV", nv, onset=o)["pv"] for o in ("clear", "struct"))
    assert a["y"].tolist() == b["y"].tolist() == [0] * 3 + [1] * 9 and 1 not in a["state"].tolist()
    assert _targets("PV", nv, onset="complete")["pv"]["y"].sum() == 0
    # series ends
    pre = _targets("PV", _ev("pv", "before_series", "before_series", "before_series"))["pv"]
    assert pre["y"].tolist() == [1] * 12 and set(pre["state"]) == {3}
    assert _targets("PV", _ev("pv", "after_series", "after_series", "after_series"))["pv"]["y"].sum() == 0
    assert _targets("other")["battery"]["y"].sum() == 0


def test_onset_conf_follows_the_event_used():
    ev = {**_ev("pv", "not_visible", "2024-04", "not_visible"), "pv_clear_conf": "1", "pv_struct_conf": "2",
          "pv_complete_conf": "3"}
    conf = {o: _targets("PV", ev, onset=o)["pv"]["onset_conf"] for o in ("clear", "struct", "complete")}
    assert set(conf["clear"]) == {2.0}  # not-visible clearing coincides with structures
    assert set(conf["struct"]) == {2.0} and set(conf["complete"]) == {3.0}
    t = _targets("PV", ev, onset="clear", coord_coarse=True)["pv"]
    assert t["coord_coarse"].all() and list(t.columns) == TARGET_COLUMNS
    assert not _targets("PV", ev)["pv"]["coord_coarse"].any()


def test_label_metadata_is_never_a_model_input():
    meta = [c for c in TARGET_COLUMNS if c not in ("site_id", "month", "technology")]
    assert {"coord_coarse", "onset_conf", "registry_date_exposed"} <= set(LABEL_METADATA_COLUMNS)
    for c in meta + ["bat_clear_conf", "pv_complete_conf"]:
        with pytest.raises(CircularityError):
            assert_model_inputs(["s1_vv_c", c])
        with pytest.raises(CircularityError):
            assert_model_inputs(["s1_vv_c", c], track="B")
        with pytest.raises(CircularityError):
            assert_no_registry_inputs(["s1_vv_c", c])
    with pytest.raises(CircularityError):
        assert_model_inputs(["s1_vv_c", "coord_coarse__mean3"])


def test_target_brackets():
    ev = _ev("bat", "2024-03", "2024-05", "2024-09", clear_earliest="2024-02", clear_latest="2024-06")
    pt = _targets("battery", ev, brackets="point")["battery"]["y"]
    un = _targets("battery", ev, brackets="unknown")["battery"]["y"]
    mid = _targets("battery", ev, brackets="midpoint")["battery"]["y"]
    assert pt.tolist()[:3] == [0, 0, 1]
    # months 2024-02 to 2024-05 lie in [earliest, latest): unknown; from structures (2024-05) on, cleared for sure
    assert un.iloc[0] == 0 and un.iloc[1:4].isna().all() and un.iloc[4:].tolist() == [1] * 8
    assert mid.tolist()[:4] == [0, 0, 0, 1]  # floor((Feb + Jun) / 2) = Apr


def test_colocated_targets_keep_their_own_dates():
    ev = {**_ev("bat", "2024-06", "2024-07", "2024-10"), **_ev("pv", "2024-01", "2024-02", "2024-04")}
    t = _targets("battery", ev, colocated="pv")
    assert t["battery"]["y"].tolist() == [0] * 5 + [1] * 7
    assert t["pv"]["y"].tolist() == [1] * 12 and t["pv"]["present"].all()
    assert t["battery"]["colocated_target"].all() and t["pv"]["colocated_target"].all()
    with pytest.raises(ValueError):  # the co-located technology needs its own events
        _targets("battery", _ev("bat", "2024-06", "2024-07", "2024-10"), colocated="pv")


def test_site_truth_window():
    t = _targets("battery", _ev("bat", "2024-05", "2024-06", "2024-08"))["battery"]
    a, b = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-01")
    assert site_truth(t, a, b)["truth"].item() == 0
    assert site_truth(t, a, pd.Timestamp("2024-06-01"))["truth"].item() == 1


# ---------------------------------------------------------------- folds and leakage


def _splits():
    return pd.DataFrame({"queue_id": ["a", "b", "c", "d"], "block_id": ["B1", "B1", "B2", "B3"],
                         "fold": [1, 1, 2, 0], "cluster_id": ["k1", "k2", "k3", "k4"]})


def test_splits_validation():
    validate_splits(_splits())
    s = _splits()
    s.loc[1, "fold"] = 2
    with pytest.raises(LeakageError):
        validate_splits(s)  # block straddles folds
    s = _splits()
    s.loc[2, "cluster_id"] = "k1"
    with pytest.raises(LeakageError):
        validate_splits(s)  # cluster in two blocks and two folds
    with pytest.raises(LeakageError):
        validate_splits(pd.concat([_splits(), _splits().iloc[[0]]]))  # one site twice
    with pytest.raises(ValueError):
        validate_splits(_splits().assign(fold=[1, 1, 2, 7]))


def test_splits_missing_file(tmp_path):
    with pytest.raises(SplitsMissingError, match="blocks_v1"):
        load_splits(tmp_path / "blocks_v1.parquet")


def test_attach_folds_requires_every_site():
    df = pd.DataFrame({"site_id": ["a", "z"], "month": pd.Timestamp("2024-01-01")})
    with pytest.raises(LeakageError):
        attach_folds(df, _splits())
    assert attach_folds(df.iloc[:1], _splits())["fold"].tolist() == [1]


def test_site_never_in_two_folds():
    with pytest.raises(LeakageError):
        assert_site_in_one_fold(pd.DataFrame({"site_id": ["a", "a"], "fold": [1, 2]}))


@pytest.fixture(scope="module")
def syn():
    features, labels, splits, sizes = make_synthetic(n_blocks=40, sites_per_block=5)
    targets = synthetic_targets(labels, features)
    data = join_inputs(features, targets, splits)
    return data, sizes


def _cfg(tech, **kw):
    return DetectorConfig(tech, SYN_FEATURES, windows=(3,), max_iter=40, **kw)


def test_fit_refuses_test_fold_and_holdout_months(syn):
    data, _ = syn
    dev = data[data["month"] <= design.DEV_END]
    with pytest.raises(LeakageError, match="test fold"):
        Detector(_cfg("battery")).fit(dev)  # still contains fold 0
    dev14 = data[data["fold"] != 0]
    with pytest.raises(LeakageError, match="hold-out"):
        Detector(_cfg("battery")).fit(dev14)  # contains months after DEV_END
    with pytest.raises(LeakageError):
        oof_predictions(data, _cfg("battery"), folds=(0, 1, 2, 3))


def test_fold0_locked_until_freeze(syn, tmp_path):
    data, _ = syn
    cfg = _cfg("battery")
    path = tmp_path / "model_freeze.json"
    with pytest.raises(freeze.FreezeError, match="not frozen"):
        evaluate_test(data, cfg, theta=0.5, freeze_path=path)
    comps = {cfg.component(): {"config": {**cfg.as_dict(), "theta": 0.5},
                               "features": ["s1_vv_c", "s1_vv_c__mean3"],
                               "hyperparameters": cfg.hyperparameters()}}
    freeze.write_freeze(comps, path=path, now="2026-11-19T00:00:00+00:00")
    rec = json.loads(path.read_text())
    assert rec["features"] == ["s1_vv_c"] and set(rec) >= {"config_hash", "hyperparameters", "date"}
    with pytest.raises(freeze.FreezeError, match="exists"):
        freeze.write_freeze(comps, path=path)  # written once (shared timeline guard)
    with pytest.raises(freeze.FreezeError, match="hash"):
        evaluate_test(data, cfg, theta=0.6, freeze_path=path)  # not the frozen threshold
    with pytest.raises(freeze.FreezeError, match="not in the model freeze"):
        freeze.require_freeze("detector_pv_trackA", {}, path)
    freeze.guard_test_fold([1, 2, 3, 4], "anything", {}, path=tmp_path / "absent.json")  # dev folds: no freeze


def test_freeze_refuses_registry_feature(tmp_path):
    comps = {"x": {"config": {}, "features": ["gross_kw"], "hyperparameters": {}}}
    with pytest.raises(CircularityError):
        freeze.write_freeze(comps, path=tmp_path / "f.json")


def test_freeze_hash_is_canonical():
    assert freeze.config_hash({"a": 1, "b": [1, 2]}) == freeze.config_hash({"b": [1, 2], "a": 1})
    assert freeze.config_hash({"a": 1}) != freeze.config_hash({"a": 2})


# ---------------------------------------------------------------- end to end on synthetic data


@pytest.fixture(scope="module")
def dev_result(syn):
    data, _ = syn
    return develop(data, [_cfg("battery"), _cfg("pv")], n_boot=100)


def test_end_to_end_strong_signal_and_noise_class(dev_result, syn):
    _, sizes = syn
    s = dev_result.sites
    assert set(s["fold"]) <= set(design.DEV_FOLDS)
    bat = s[s["technology"] == "battery"]
    assert recall(bat) >= 0.9
    assert roc_auc_score(bat["truth"], bat["score"]) >= 0.95
    pv = s[s["technology"] == "pv"].merge(sizes[["site_id", "site_class"]], on="site_id")
    # Battery sites are PV negatives with a strong VV step, so the PV model learns "VV step means not PV" and
    # ranks them low (real information, not leakage). Against signal-free negatives the PV class is pure noise:
    pv = pv[pv["site_class"] != "battery"]
    assert abs(roc_auc_score(pv["truth"], pv["score"]) - 0.5) < 0.15
    theta = pv.loc[pv["truth"] == 0, "score"].median()
    assert abs((pv.loc[pv["truth"] == 1, "score"] >= theta).mean() - 0.5) < 0.2
    m = dev_result.metrics
    row = m[(m["technology"] == "battery") & (m["metric"] == "recall")].iloc[0]
    assert row["lo"] <= row["estimate"] <= row["hi"] and row["quantity_type"] == "detected"
    o = dev_result.oof.dropna(subset=["y"])
    cal = calibration_table(o.loc[o["technology"] == "battery", "y"], o.loc[o["technology"] == "battery", "p"])
    assert (cal["p_mean"] - cal["y_rate"]).abs().max() < 0.15  # calibrated on held-out folds
    pos = bat[bat["truth"] == 1].merge(sizes, on="site_id")
    _, summ = recall_curve(pos, "mw", n_boot=50)
    assert summ["n"] == len(pos)


def test_tuning_uses_training_folds_only(syn):
    data, _ = syn
    train = data[data["fold"].isin([1, 2]) & (data["month"] <= design.DEV_END)]
    grid = [_cfg("battery", max_leaf_nodes=3), _cfg("battery", max_leaf_nodes=7)]
    best, table = tune(train, grid[0], grid)
    assert best in grid and len(table) == 2 and table["loss"].notna().all()
    with pytest.raises(LeakageError):
        tune(data[data["month"] <= design.DEV_END], grid[0], grid)


# ---------------------------------------------------------------- threshold


def test_kth_largest_and_site_scores():
    assert kth_largest(np.array([0.1, 0.9, np.nan, 0.5]), 2) == 0.5
    assert kth_largest(np.array([0.9]), 2) == float("-inf")
    m = pd.date_range("2025-01-01", periods=4, freq="MS")
    pred = pd.DataFrame({"site_id": "a", "technology": "pv", "month": m, "p": [0.9, 0.95, 0.2, 0.1],
                         "usable": [True, False, True, True]})
    sc = site_scores(pred, m[0], m[-1])
    assert sc["score"].item() == 0.2 and sc["n_usable"].item() == 3


def test_select_threshold():
    y = np.array([1, 1, 1, 0, 0, 0])
    s = np.array([0.9, 0.8, 0.3, 0.7, 0.2, -np.inf])
    r = select_threshold(y, s)
    # theta 0.8: tp2 fp0 fn1 -> F1 0.8; theta 0.3: tp3 fp1 -> 0.857; theta 0.2: tp3 fp2 -> 0.75
    assert r.theta == 0.3 and r.f1 == pytest.approx(6 / 7)
    tie = select_threshold(np.array([1, 0, 0, 1]), np.array([0.9, 0.8, 0.7, 0.6]))
    # theta 0.9 (tp1 fn1) and theta 0.6 (tp2 fp2) both give F1 2/3: ties go to the larger theta
    assert tie.theta == 0.9
    with pytest.raises(ValueError):
        select_threshold(np.array([0, 0]), np.array([0.1, 0.2]))


# ---------------------------------------------------------------- bootstrap and curves


def test_block_bootstrap():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"block_id": np.repeat(np.arange(30), 4), "v": rng.normal(size=120)})
    r1 = block_bootstrap(df, lambda d: d["v"].mean(), n_boot=500, seed=7)
    r2 = block_bootstrap(df, lambda d: d["v"].mean(), n_boot=500, seed=7)
    assert r1 == r2 and r1.lo < r1.estimate < r1.hi
    blk = df.groupby("block_id")["v"].mean()
    se = blk.std(ddof=1) / np.sqrt(len(blk))
    assert (r1.hi - r1.lo) == pytest.approx(2 * 1.96 * se, rel=0.25)
    sizes = []
    block_bootstrap(df, lambda d: sizes.append(len(d)) or 0.0, n_boot=20)
    assert all(n % 4 == 0 for n in sizes)  # whole blocks are resampled
    small = block_bootstrap(df.iloc[:8], lambda d: d["v"].mean(), n_boot=50)
    assert np.isnan(small.lo) and np.isnan(small.hi)


def test_prf_table_counts_and_dop_contradiction():
    df = pd.DataFrame({"truth": [1, 1, 0, 0] * 5, "detected": [1, 0, 1, 0] * 5,
                       "block_id": np.repeat(np.arange(10), 2), "technology": "battery"})
    t = prf_table(df, by=["technology"], n_boot=50)
    assert t.set_index("metric").loc["recall", "estimate"] == 0.5
    df["dop_contradicted"] = [True, False, False, False] * 5
    assert recall(df) == 0.0  # contradicted detections never count as true positives


def test_recall_curve_recovers_known_logistic():
    rng = np.random.default_rng(3)
    mw = 10 ** rng.uniform(0, 2.5, 600)
    b0, b1 = -2.0, 3.0
    p = 1 / (1 + np.exp(-(b0 + b1 * np.log10(mw))))
    df = pd.DataFrame({"mw": mw, "detected": rng.random(600) < p, "block_id": np.arange(600) // 10})
    est0, est1 = fit_logistic(np.log10(mw), df["detected"].to_numpy(float))
    assert est0 == pytest.approx(b0, abs=0.6) and est1 == pytest.approx(b1, abs=0.8)
    curve, s = recall_curve(df, "mw", n_boot=200)
    true_mds = size_at_recall(b0, b1)
    assert s["mds_lo"] <= true_mds <= s["mds_hi"] and s["mds_in_observed_range"]
    assert (curve["lo"] <= curve["hi"]).all()
    assert np.isnan(size_at_recall(1.0, -1.0))


# ---------------------------------------------------------------- Track B slot


def test_attach_dop_never_looks_forward():
    m = pd.date_range("2024-01-01", periods=5, freq="MS")
    f = pd.DataFrame({"site_id": "a", "month": m, "s1_vv_c": 0.0})
    dop = pd.DataFrame({"site_id": ["a", "a"], "flight_month": ["2024-02", "2024-04"],
                        "dop_p_battery": [0.1, 0.9], "dop_p_pv": [0.0, 0.0]})
    out = attach_dop(f, dop)
    assert np.isnan(out["dop_p_battery"].iloc[0])
    assert out["dop_p_battery"].iloc[1:].tolist() == [0.1, 0.1, 0.9, 0.9]
    assert out["dop_months_since_flight"].iloc[2] == 1


def test_paired_difference_and_subset():
    n = 40
    base = pd.DataFrame({"site_id": [f"s{i}" for i in range(n)], "technology": "pv", "truth": 1,
                         "block_id": np.arange(n) // 2, "open_dop": np.arange(n) % 2 == 0})
    a = base.assign(detected=np.arange(n) % 4 == 0)
    b = base.assign(detected=True)
    r = paired_difference(a, b, n_boot=100)
    assert r["difference_b_minus_a"] == pytest.approx(0.75) and r["lo"] <= 0.75 <= r["hi"]
    assert len(track_b_subset(base)) == n // 2
    with pytest.raises(ValueError):
        track_b_subset(base.drop(columns="open_dop"))


def test_dop_contradicted():
    ta = pd.DataFrame({"site_id": ["a", "b", "c"], "technology": "battery", "detected": [True, True, False],
                       "first_detected_month": ["2024-03", "2024-03", None]})
    dop = pd.DataFrame({"site_id": ["a", "b", "b"], "flight_month": ["2024-06", "2024-01", "2024-08"],
                        "dop_p_battery": [0.05, 0.02, 0.95], "dop_p_pv": 0.0})
    assert dop_contradicted(ta, dop).tolist() == [True, False, False]


def test_open_dop_flags_exclude_restricted_state():
    q = pd.DataFrame({"queue_id": ["a", "b", "c"], "bundesland": ["Bayern", "Mecklenburg-Vorpommern", "Saarland"]})
    assert open_dop_flags(q)["open_dop"].tolist() == [True, False, False]


def test_shared_timeline_guard_is_used():
    from bo.timeline import guard

    assert CircularityError is guard.CircularityError and freeze.FreezeError is guard.FreezeError
