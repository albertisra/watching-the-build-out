"""Negatives: exclusion distance, allocation and Overpass parsing without the network."""

import numpy as np
import pandas as pd
import pytest

from bo.imagery import negatives as N


def test_far_enough_uses_metric_distance():
    tree = N.exclusion_tree(np.array([[11.0, 48.0]]))
    xy = np.array([[N.METRIC and 0.0, 0.0]])
    assert xy.shape == (1, 2)
    near = pd.DataFrame({"lon": [11.0 + 0.01], "lat": [48.0]})  # about 740 m
    far = pd.DataFrame({"lon": [11.0 + 0.05], "lat": [48.0]})  # about 3.7 km
    import geopandas as gpd

    def to_xy(df):
        g = gpd.GeoSeries(gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(N.METRIC)
        return np.array([[p.x, p.y] for p in g])

    assert not N.far_enough(to_xy(near), tree)[0]
    assert N.far_enough(to_xy(far), tree)[0]


def test_allocation_sums_and_minimum():
    import geopandas as gpd
    from shapely.geometry import box

    states = gpd.GeoDataFrame(
        {"bundesland": ["A", "B", "C"]},
        geometry=[box(9, 48, 10, 49), box(10, 48, 12, 49), box(12, 48, 13, 49)], crs=4326)
    a = N.allocate_by_state(states, 10, min_each=2)
    assert sum(a.values()) == 10 and min(a.values()) >= 2 and a["B"] >= a["A"]


def test_ways_to_frame_parses_closed_polygons_only():
    sq = [{"lon": 11.0, "lat": 48.0}, {"lon": 11.001, "lat": 48.0}, {"lon": 11.001, "lat": 48.001},
          {"lon": 11.0, "lat": 48.001}, {"lon": 11.0, "lat": 48.0}]
    data = {"elements": [{"type": "way", "id": 1, "geometry": sq},
                         {"type": "way", "id": 2, "geometry": sq[:-1]}]}
    g = N.ways_to_frame(data, "greenhouse")
    assert len(g) == 1 and g.osm_id.iloc[0] == 1
    assert g.area_m2.iloc[0] == pytest.approx(75 * 111 + 0, rel=0.5)  # roughly 0.8 ha


# ---------------------------------------------------------------- scan helpers
def test_scan_candidate_rule_and_components():
    from bo.imagery.scan import ScanConfig, candidate_mask, label_components, ndvi, tile_windows

    cfg = ScanConfig(min_px=4)
    T, H, W = 12, 20, 20
    nd = np.full((T, H, W), 0.7, np.float32)
    b11 = np.full((T, H, W), 0.2, np.float32)
    nd[7:, 5:9, 5:9] = 0.1  # vegetation lost from month 8 on, 4 x 4 block
    nd[7:, 15, 15] = 0.1  # single pixel, below min_px
    nd[:, 0, 0] = np.nan  # never observed
    nd[7:, 12:14, 2:4] = 0.1
    b11[7:, 12:14, 2:4] = 0.05  # SWIR falls: not a candidate under the rule
    m = candidate_mask(nd, b11, cfg)
    assert m[5:9, 5:9].all() and not m[0, 0] and not m[12:14, 2:4].any()
    _lab, keep = label_components(m, cfg)
    assert len(keep) == 1  # the 4 x 4 block only; the single pixel is dropped
    assert ndvi(np.array([0.1]), np.array([0.5]))[0] == pytest.approx(0.6667, abs=1e-3)
    from affine import Affine

    r0, r1, c0, c1 = tile_windows((500_000, 5_000_000, 500_400, 5_000_200),
                                  Affine(10, 0, 499_800, 0, -10, 5_010_000), (500, 500), 2)
    assert (c0, c1) == (10, 30) and (r0, r1) == (490, 500)


def test_scan_merge_joins_strip_fragments_and_drops_tile_duplicates():
    import geopandas as gpd
    from shapely.geometry import box

    from bo.imagery.scan import merge_candidates

    ser = '[0.7, 0.1]'
    rows = [
        {"geometry": box(0, 0, 40, 40), "n_px": 4, "tile": "A", "ndvi_series": ser,
         "b11_series": ser, "clear_px_series": ser},
        {"geometry": box(0, 40, 40, 80), "n_px": 4, "tile": "A", "ndvi_series": ser,
         "b11_series": ser, "clear_px_series": ser},  # touches the first: same candidate
        {"geometry": box(10, 10, 30, 30), "n_px": 2, "tile": "B", "ndvi_series": ser,
         "b11_series": ser, "clear_px_series": ser},  # same site seen from tile B
        {"geometry": box(1000, 1000, 1040, 1040), "n_px": 4, "tile": "A", "ndvi_series": ser,
         "b11_series": ser, "clear_px_series": ser},
    ]
    out = merge_candidates(gpd.GeoDataFrame(rows, geometry="geometry", crs=32632))
    assert sorted(out.n_px.tolist()) == [4, 8]


def test_r3_summary_detects_masked_footprint():
    """A footprint that is cloud on days the ring is clear gets a low ratio and a high flag."""
    from bo.imagery.r3 import RULES, add_rules, site_summary

    rng = np.random.default_rng(0)
    days = pd.date_range("2024-01-01", periods=40).strftime("%Y-%m-%d")
    rows = []
    for which in ("footprint", "ring"):
        for i, d in enumerate(days):
            r = {"site_id": "S1", "geom": which, "date": d, "n_px": 50}
            for k in range(12):
                r[f"scl_{k}"] = 0.0
            for t in (10, 30, 50):
                r[f"cld_le{t}"] = 1.0
            if which == "ring":
                r["scl_4"] = 1.0
            elif i % 2 == 0:
                r["scl_9"] = 1.0  # footprint flagged as cloud half of the days
                r["cld_le10"] = 0.0
            else:
                r["scl_4"] = 1.0
            rows.append(r)
    df = pd.DataFrame(rows)
    assert {"clear_scl456", "clear_alt"} <= set(add_rules(df).columns) and len(RULES) == 5
    s = site_summary(df, min_days=10).iloc[0]
    assert s.ratio_clear_scl456 == pytest.approx(0.5)
    assert s.cloud_fp_given_ring_clear == pytest.approx(0.5)
    assert s.ratio_clear_cld10 == pytest.approx(0.5) and s.ratio_clear_cld30 == pytest.approx(1.0)
    _ = rng


def test_scan_merge_works_on_geographic_input_in_metres():
    import geopandas as gpd
    from shapely.geometry import box

    from bo.imagery.scan import merge_candidates

    ser = "[0.7, 0.1]"
    base = {"tile": "A", "ndvi_series": ser, "b11_series": ser, "clear_px_series": ser}
    # two candidates about 1.5 km apart must stay separate (a degree-sized buffer would merge them)
    rows = [{"geometry": box(8.80, 53.07, 8.8005, 53.0705), "n_px": 5, **base},
            {"geometry": box(8.82, 53.07, 8.8205, 53.0705), "n_px": 6, **base}]
    out = merge_candidates(gpd.GeoDataFrame(rows, geometry="geometry", crs=4326))
    assert len(out) == 2 and out.crs.to_epsg() == 4326
