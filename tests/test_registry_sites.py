"""Grouping rule and co-location flags on a small synthetic unit table."""

import numpy as np
import pandas as pd
import pytest

from bo.data import registry_sites as rsi

DEG_M = 1 / 111_000.0  # about one metre in degrees of latitude


def _units(rows):
    base = {
        "technology": "battery", "location_id": "", "coord_state": "ok", "gross_kw": 1000.0,
        "net_kw": 1000.0, "power_kw": 1000.0, "usable_kwh_alloc": np.nan, "reg_status": "In Betrieb",
        "bundesland": "Bayern", "landkreis": "X", "grid_operator_id": None, "voltage_level": None,
        "reg_registration_date": pd.Timestamp("2022-01-01"),
        "reg_commissioning_date": pd.Timestamp("2022-06-01"),
        "reg_planned_commissioning_date": pd.NaT,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_shared_location_id_groups_units_within_link_distance():
    lat0 = 50.0
    u = _units([
        {"unit_id": "SEE1", "location_id": "SEL1", "lat": lat0, "lon": 10.0},
        {"unit_id": "SEE2", "location_id": "SEL1", "lat": lat0 + 1500 * DEG_M, "lon": 10.0},
        {"unit_id": "SEE3", "location_id": "SEL2", "lat": lat0 + 1500 * DEG_M, "lon": 10.0 + 0.5},
    ])
    s = rsi.assign_sites(u, 300)
    assert s[0] == s[1] != s[2]  # 1.5 km apart but one location ID
    assert s[0] == "BESS-SEE1"
    tight = rsi.assign_sites(u, 300, location_link_max_m=1000)
    assert tight[0] != tight[1]


def test_location_id_does_not_link_units_far_apart_but_links_coordless_units():
    u = _units([
        {"unit_id": "SEE1", "location_id": "SEL1", "lat": 50.0, "lon": 10.0},
        {"unit_id": "SEE2", "location_id": "SEL1", "lat": 50.5, "lon": 10.5},  # about 60 km away
        {"unit_id": "SEE3", "location_id": "SEL1", "lat": np.nan, "lon": np.nan, "coord_state": "missing"},
    ])
    units, _ = rsi.build_sites(u, 300)
    s = units["site_id"]
    assert s[0] != s[1]
    assert s[2] == s[0]  # no coordinates: attached to the first unit of the location
    assert units["flag_location_split_by_distance"].all()


def test_distance_merge_threshold_and_chaining():
    # A-B 200 m, B-C 200 m, C-D 1 km: A, B, C chain into one site at 300 m, D is separate.
    lat0 = 50.0
    u = _units([
        {"unit_id": "SEE1", "lat": lat0, "lon": 10.0},
        {"unit_id": "SEE2", "lat": lat0 + 200 * DEG_M, "lon": 10.0},
        {"unit_id": "SEE3", "lat": lat0 + 400 * DEG_M, "lon": 10.0},
        {"unit_id": "SEE4", "lat": lat0 + 1400 * DEG_M, "lon": 10.0},
    ])
    s = rsi.assign_sites(u, 300)
    assert s[0] == s[1] == s[2] != s[3]
    s150 = rsi.assign_sites(u, 150)
    assert len(set(s150)) == 4  # nothing closer than 200 m


def test_technologies_are_grouped_separately_but_flagged_colocated():
    lat0 = 50.0
    u = _units([
        {"unit_id": "SEE1", "lat": lat0, "lon": 10.0},
        {"unit_id": "SEE2", "technology": "ground_pv", "lat": lat0 + 100 * DEG_M, "lon": 10.0},
        {"unit_id": "SEE3", "technology": "ground_pv", "lat": lat0 + 5000 * DEG_M, "lon": 10.0},
    ])
    units, sites = rsi.build_sites(u, 300)
    assert units["site_id"].nunique() == 3  # no cross-technology merge
    bess = sites[sites["technology"] == "battery"].iloc[0]
    assert bess["colocated_pv"] and not bess["shares_location_id_other_tech"]
    assert bess["nearest_other_tech_site_m"] == pytest.approx(100, rel=0.02)
    assert bess["colocated_site_ids"] == "PV-SEE2"
    pv = sites.set_index("site_id")
    assert pv.loc["PV-SEE2", "colocated_bess"]
    assert not pv.loc["PV-SEE3", "colocated_bess"]


def test_colocation_by_shared_location_id_without_coordinates():
    u = _units([
        {"unit_id": "SEE1", "location_id": "SEL9", "lat": np.nan, "lon": np.nan, "coord_state": "missing"},
        {"unit_id": "SEE2", "technology": "ground_pv", "location_id": "SEL9", "lat": 50.0, "lon": 10.0},
    ])
    _, sites = rsi.build_sites(u, 300)
    b = sites[sites["technology"] == "battery"].iloc[0]
    assert not b["colocated_pv"]  # a shared location ID alone never sets the distance flag
    assert b["shares_location_id_other_tech"]
    assert b["coord_state"] == "missing" and np.isnan(b["lat"])


def test_site_aggregates_and_coordinate_handling():
    lat0 = 50.0
    u = _units([
        {"unit_id": "SEE1", "lat": lat0, "lon": 10.0, "power_kw": 3000.0, "gross_kw": 3000.0},
        {"unit_id": "SEE2", "lat": lat0 + 100 * DEG_M, "lon": 10.0, "power_kw": 1000.0,
         "gross_kw": 1000.0, "usable_kwh_alloc": 2000.0},
        {"unit_id": "SEE3", "lat": 50.0, "lon": 10.0, "coord_state": "outside", "location_id": ""},
    ])
    u.loc[2, ["lat", "lon"]] = np.nan
    _, sites = rsi.build_sites(u, 300)
    merged = sites[sites["n_units"] == 2].iloc[0]
    assert merged["gross_kw"] == 4000.0
    assert merged["lat"] == pytest.approx(lat0 + 25 * DEG_M, abs=1e-6)  # power-weighted (3:1)
    assert merged["site_extent_m"] == pytest.approx(100, rel=0.02)
    assert merged["usable_kwh"] == 2000.0
    lone = sites[sites["n_units"] == 1].iloc[0]
    assert lone["coord_state"] == "outside" and lone["n_units_with_coords"] == 0


def test_swapped_units_are_used_after_correction():
    u = _units([{"unit_id": "SEE1", "coord_state": "swapped", "lat": 50.0, "lon": 10.0},
                {"unit_id": "SEE2", "coord_state": "ok", "lat": 50.0, "lon": 10.0005}])
    assert rsi.assign_sites(u, 300).nunique() == 1


def test_registry_columns_helper_covers_dates_and_status():
    from bo.data.registry import registry_columns

    _, sites = rsi.build_sites(_units([{"unit_id": "SEE1", "lat": 50.0, "lon": 10.0}]), 300)
    regcols = registry_columns(sites)
    for c in ("reg_status", "reg_registration_date_first", "reg_commissioning_date_first"):
        assert c in regcols
    assert not any("date" in c and c not in regcols for c in sites.columns)


def test_colocation_distance_is_configurable_and_only_counts_pv_sites():
    lat0 = 50.0
    u = _units([
        {"unit_id": "SEE1", "lat": lat0, "lon": 10.0},
        {"unit_id": "SEE2", "technology": "ground_pv", "lat": lat0 + 800 * DEG_M, "lon": 10.0},
    ])
    near = rsi.build_sites(u, 300, colocation_distance_m=1000)[1]
    far = rsi.build_sites(u, 300)[1]
    assert near[near["technology"] == "battery"]["colocated_pv"].iloc[0]
    assert not far[far["technology"] == "battery"]["colocated_pv"].iloc[0]
    assert far["nearest_other_tech_site_m"].tolist() == pytest.approx([800, 800], rel=0.01)


def test_declared_link_is_a_separate_column():
    u = _units([
        {"unit_id": "SEE1", "lat": 50.0, "lon": 10.0, "storage_pv_unit_link": "SEE9"},
        {"unit_id": "SEE2", "technology": "ground_pv", "lat": 51.0, "lon": 10.0},
    ])
    s = rsi.build_sites(u, 300)[1].set_index("site_id")
    assert s.loc["BESS-SEE1", "declared_storage_pv_link"] and not s.loc["BESS-SEE1", "colocated_pv"]


def test_coarse_unit_does_not_move_site_with_precise_units():
    u = _units([
        {"unit_id": "A", "lat": 50.0, "lon": 10.0, "coord_precision_class": "dp4plus", "coord_unc_m": 1.0},
        {"unit_id": "B", "lat": 50.0 + 100 * DEG_M, "lon": 10.0, "coord_precision_class": "dp1", "coord_unc_m": 5000.0},
        {"unit_id": "C", "lat": 51.0, "lon": 11.0, "coord_precision_class": "dp1", "coord_unc_m": 5000.0},
    ])
    _, s = rsi.build_sites(u, 300)
    mixed = s[s["unit_ids"].str.contains("A")].iloc[0]
    assert mixed["lat"] == pytest.approx(50.0)
    assert mixed["coord_unc_m"] == 1.0 and mixed["coord_precision_class"] == "dp4plus"
    assert bool(mixed["coord_coarse_units_excluded"])
    only_coarse = s[s["unit_ids"] == "C"].iloc[0]
    assert only_coarse["lat"] == pytest.approx(51.0) and only_coarse["coord_precision_class"] == "dp1"
    assert not bool(only_coarse["coord_coarse_units_excluded"])


def test_registry_columns_deny_site_proxies():
    from bo.data.registry import registry_columns
    from bo.features.allowlist import FEATURE_COLUMNS

    cols = ["site_extent_m", "colocated_pv", "colocated_bess", "colocated_site_ids", "nearest_other_tech_site_m",
            "voltage_level", "grid_operator_id", "coord_coarse_units_excluded", "s2_ndvi_mean"]
    df = pd.DataFrame(columns=cols)
    assert registry_columns(df) == cols[:-1]
    assert not set(registry_columns(pd.DataFrame(columns=list(FEATURE_COLUMNS)))) & set(FEATURE_COLUMNS)
