"""Labelling queue: stratification counts, separation rules, seed reproducibility, no leakage.

Synthetic fixtures only; no network, no OSM extract.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bo.data import queue as q


def synthetic_sites(n: int = 600, seed: int = 1) -> pd.DataFrame:
    """Registry-like pool of one technology spread over four states, on a 3 km grid."""
    rng = np.random.default_rng(seed)
    states = ["Bayern", "Brandenburg", "Bremen", "Hessen"]
    rows = []
    for i in range(n):
        row, col = divmod(i, 25)
        rows.append({
            "site_id": f"S{i:04d}",
            "technology": "battery",
            "lat": 48.0 + row * 0.03,
            "lon": 9.0 + col * 0.04,
            "bundesland": states[0] if i % 10 < 6 else states[1 + i % 3],
            "reg_size_class": rng.choice(q.SIZE_LABELS, p=[0.6, 0.25, 0.1, 0.05]),
            "reg_period": rng.choice(q.PERIODS),
            "reg_colocated": bool(rng.random() < 0.2),
        })
    return pd.DataFrame(rows)


def test_allocate_cells_caps_and_sums():
    avail = {("a", "x"): 100, ("a", "y"): 2, ("b", "x"): 100, ("b", "y"): 0}
    w = dict.fromkeys(avail, 0.25)
    quota = q.allocate_cells(avail, 40, w)
    assert sum(quota.values()) == 40
    assert quota[("a", "y")] == 2
    assert quota[("b", "y")] == 0
    assert all(quota[c] <= avail[c] for c in avail)


def test_allocate_cells_short_pool_takes_everything():
    avail = {("a", "x"): 3, ("b", "x"): 4}
    quota = q.allocate_cells(avail, 50, dict.fromkeys(avail, 1.0))
    assert quota == avail


def test_period_of():
    assert q.period_of("In Planung", pd.NaT) == "planned"
    assert q.period_of("In Betrieb", pd.Timestamp("2018-12-31")) == "before_2019"
    assert q.period_of("In Betrieb", pd.Timestamp("2019-01-01")) == "2019_2022"
    assert q.period_of("In Betrieb", pd.Timestamp("2024-06-01")) == "2023_2024"
    assert q.period_of("In Betrieb", pd.Timestamp("2026-02-01")) == "2025_2026"
    assert q.period_of("In Betrieb", pd.NaT) is None
    assert q.period_of("Endgültig stillgelegt", pd.Timestamp("2020-01-01")) is None


def test_select_positives_counts_states_and_separation():
    pool = synthetic_sites()
    pick = q.select_positives(pool, 60, np.random.default_rng(3), np.empty((0, 2)))
    assert len(pick) == 60
    assert pick["site_id"].is_unique
    assert set(pick["bundesland"]) == set(pool["bundesland"])  # every state represented
    # every size class and period with sites is present
    assert set(pick["reg_size_class"]) == set(pool["reg_size_class"])
    assert set(pick["reg_period"]) == set(pool["reg_period"])
    # size classes follow the equal-weight target up to availability: the rare classes get
    # everything they can, the large pool classes are not above 25 percent plus rounding
    share_big = (pick["reg_size_class"] == "1-5 MW").mean()
    assert share_big <= 0.35
    xy = q.to_xy(pick["lat"].to_numpy(), pick["lon"].to_numpy())
    from scipy.spatial import cKDTree
    d, _ = cKDTree(xy).query(xy, k=2)
    assert d[:, 1].min() >= q.POS_MIN_SEP_M


def test_select_positives_respects_fixed_points():
    pool = synthetic_sites(100)
    fixed = q.to_xy(pool[["lat"]].iloc[:5].to_numpy().ravel(), pool[["lon"]].iloc[:5].to_numpy().ravel())
    pick = q.select_positives(pool, 20, np.random.default_rng(3), fixed)
    xy = q.to_xy(pick["lat"].to_numpy(), pick["lon"].to_numpy())
    assert q.min_dist(xy, fixed).min() >= q.POS_MIN_SEP_M


def test_colocated_are_included():
    pool = synthetic_sites()
    pick = q.select_positives(pool, 60, np.random.default_rng(3), np.empty((0, 2)))
    assert pick["reg_colocated"].sum() >= 10  # 25 percent target of 60 is 15, allow slack


def test_positive_selection_reproducible():
    pool = synthetic_sites()
    a = q.select_positives(pool, 40, np.random.default_rng(q.paths.SEED), np.empty((0, 2)))
    b = q.select_positives(pool, 40, np.random.default_rng(q.paths.SEED), np.empty((0, 2)))
    pd.testing.assert_frame_equal(a, b)


def synthetic_osm(n_per: int = 40, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for cat in q.HARD_CATEGORIES:
        for i in range(n_per):
            rows.append({"osm_id": f"{cat}{i}", "osm_category": cat, "area_m2": 1e4,
                         "lat": rng.uniform(47.5, 54.5), "lon": rng.uniform(7.0, 14.0),
                         "bundesland": rng.choice(["A", "B", "C", "D"])})
    return pd.DataFrame(rows)


def test_hard_negative_separation_and_balance():
    cands = synthetic_osm()
    forbid = q.to_xy(np.array([50.0, 51.0]), np.array([9.0, 10.0]))
    hard = q.pick_hard(cands, 30, np.random.default_rng(5), forbid)
    assert len(hard) == 30
    assert hard["osm_category"].value_counts().min() == 6  # equal split over five categories
    xy = q.to_xy(hard["lat"].to_numpy(), hard["lon"].to_numpy())
    assert q.min_dist(xy, forbid).min() >= q.NEG_MIN_DIST_M
    from scipy.spatial import cKDTree
    d, _ = cKDTree(xy).query(xy, k=2)
    assert d[:, 1].min() >= q.NEG_MIN_DIST_M


def test_hard_negatives_drop_candidates_near_forbidden_points():
    cands = pd.DataFrame({"osm_id": ["a", "b"], "osm_category": ["quarry", "quarry"],
                          "area_m2": [1e5, 1e5], "lat": [50.0, 50.2], "lon": [9.0, 9.0],
                          "bundesland": ["A", "A"]})
    forbid = q.to_xy(np.array([50.0]), np.array([9.001]))  # about 70 m from candidate a
    hard = q.pick_hard(cands, 2, np.random.default_rng(1), forbid)
    assert list(hard["osm_id"]) == ["b"]


def test_class_quota_redistributes_shortfall():
    quota = q.class_quota({"cropland": 500, "grassland": 500, "tree_cover": 500, "built_up": 500,
                           "water": 1, "herbaceous_wetland": 0}, q.WORLDCOVER_TARGET, 60)
    assert quota["water"] == 1
    assert quota["herbaceous_wetland"] == 0
    assert sum(quota.values()) == 60


def test_random_negatives_by_class_and_separation():
    rng = np.random.default_rng(7)
    pts = pd.DataFrame({"lat": rng.uniform(48, 54, 3000), "lon": rng.uniform(7, 14, 3000),
                        "worldcover_class": rng.choice(["cropland", "grassland", "built_up"], 3000)})
    forbid = q.to_xy(np.array([50.0]), np.array([10.0]))
    taken = q.to_xy(np.array([52.0]), np.array([9.0]))
    out = q.pick_random(pts, {"cropland": 10, "grassland": 8, "built_up": 6}, rng, forbid, taken)
    assert out["worldcover_class"].value_counts().to_dict() == {"cropland": 10, "grassland": 8,
                                                                "built_up": 6}
    xy = q.to_xy(out["lat"].to_numpy(), out["lon"].to_numpy())
    assert q.min_dist(xy, forbid).min() >= q.NEG_MIN_DIST_M
    assert q.min_dist(xy, taken).min() >= q.NEG_MIN_DIST_M
    from scipy.spatial import cKDTree
    d, _ = cKDTree(xy).query(xy, k=2)
    assert d[:, 1].min() >= q.NEG_MIN_DIST_M


def _assemble(seed: int):
    bat = synthetic_sites(200, 1).iloc[:30].copy()
    pv = synthetic_sites(200, 2).iloc[30:60].copy()
    pv["technology"] = "ground_pv"
    pilot = synthetic_sites(200, 3).iloc[60:70].copy()
    pilot["landkreis"] = "X"
    hard = synthetic_osm(4).iloc[:10].copy()
    rand = pd.DataFrame({"lat": [50.0, 51.0], "lon": [9.0, 10.0], "bundesland": ["A", "B"],
                         "worldcover_class": ["cropland", "built_up"]})
    for d in (bat, pv):
        d["landkreis"] = "K"
        d["reg_status"] = "In Betrieb"
    return q.assemble({"battery": bat, "ground_pv": pv}, pilot, hard, rand, seed)


def test_assemble_is_reproducible_and_mixed():
    (q1, s1), (q2, s2) = _assemble(q.paths.SEED), _assemble(q.paths.SEED)
    pd.testing.assert_frame_equal(q1, q2)
    pd.testing.assert_frame_equal(s1, s2)
    q3, _ = _assemble(q.paths.SEED + 1)
    assert not q1["stratum"].equals(q3["stratum"])
    # shuffled: the first 20 rows are not one stratum
    assert q1["stratum"].iloc[:20].nunique() > 1
    assert q1["queue_id"].is_unique
    assert q1["stratum"].value_counts().to_dict() == {
        "positive_battery": 30, "positive_pv": 30, "pilot": 10, "hard_negative": 10,
        "random_negative": 2}


def test_queue_has_only_allowed_columns_and_no_registry_fields():
    queue, strata = _assemble(q.paths.SEED)
    assert list(queue.columns) == q.QUEUE_COLUMNS
    assert not any(c.startswith("reg_") or "power" in c or "date" in c for c in queue.columns)
    # registry stratification fields sit only in the separate table
    assert {"reg_size_class", "reg_period"} <= set(strata.columns)
    assert set(queue["stratum"]) <= set(q.STRATA_OF_QUEUE)
    # negatives carry no site id; random negatives only a land cover class, hard only an OSM class
    neg = queue[queue["stratum"].isin(["hard_negative", "random_negative"])]
    assert neg["site_id"].isna().all()
    assert queue.loc[queue["stratum"] == "hard_negative", "worldcover_class"].isna().all()
    assert queue.loc[queue["stratum"] == "random_negative", "osm_category"].isna().all()
    assert queue.loc[queue["stratum"].str.startswith("positive"), "osm_category"].isna().all()


def test_summary_has_no_coordinates():
    queue, strata = _assemble(q.paths.SEED)
    s = q.summarise(queue, strata)
    assert set(s.columns) == {"dimension", "value", "n"}
    assert not s["dimension"].isin(["lat", "lon"]).any()
    assert s.loc[s["dimension"] == "total", "n"].iloc[0] == len(queue)


def test_pool_excludes_pilot_and_bad_rows():
    base = {"coord_state": "ok", "flag_coord_rounded_any": False,
            "reg_flag_commissioning_placeholder_any": False,
            "reg_flag_commissioning_before_1990_any": False, "colocated_pv": False,
            "colocated_bess": False, "technology": "battery", "power_kw": 2000.0,
            "reg_status": "In Betrieb", "reg_commissioning_date_first": pd.Timestamp("2022-05-01"),
            "lat": 50.0, "lon": 9.0, "bundesland": "Hessen"}
    rows = []
    for sid, upd in [("ok", {}), ("pilot", {}), ("rounded", {"flag_coord_rounded_any": True}),
                     ("nocoord", {"coord_state": "missing"}),
                     ("stilled", {"reg_status": "Endgültig stillgelegt"}),
                     ("small", {"power_kw": 500.0})]:
        rows.append({**base, "site_id": sid, **upd})
    pool = q.positive_pool(pd.DataFrame(rows), {"pilot"})
    assert list(pool["site_id"]) == ["ok"]


@pytest.mark.parametrize("size", [5 * 1024**3 + 1])
def test_pbf_limit_constant(size):
    assert size > q.PBF_MAX_BYTES
