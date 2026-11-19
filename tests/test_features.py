"""Unit tests for src/bo/features (task 3.2)."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from bo.data.registry import registry_columns
from bo.features import indices, spatial, temporal
from bo.features.allowlist import EXPERIMENTAL, FEATURE_COLUMNS, ID_COLUMNS
from bo.features.site import site_features

BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]


# ---------------------------------------------------------------- indices

def test_ndpi_matches_feng_formula():
    b08, b11, b12 = np.array([0.30]), np.array([0.25]), np.array([0.10])
    assert indices.ndpi(b08, b11, b12)[0] == pytest.approx((0.25 - 0.30) / (0.30 - 0.10))


def test_ndpi_denominator_guard_gives_nan_not_infinity():
    out = indices.ndpi(np.array([0.25, 0.25]), np.array([0.3, 0.3]), np.array([0.25, 0.24]))
    assert np.isnan(out[0]) and np.isnan(out[1])  # |B08 - B12| = 0 and 0.01 < DENOM_EPS


def test_plastic_matches_sentinel_hub_script():
    b02, b03, b08 = 0.10, 0.12, 0.30
    expected = b02 / (1 - (b02 + b03 + b08) / 3)
    assert indices.plastic_ig(np.array([b02]), np.array([b03]), np.array([b08]))[0] == pytest.approx(expected)


def test_normalised_differences_and_ranges():
    assert indices.ndvi(np.array([0.05]), np.array([0.45]))[0] == pytest.approx(0.8)
    assert indices.ndbi(np.array([0.45]), np.array([0.15]))[0] == pytest.approx(-0.5)
    assert indices.mndwi(np.array([0.06]), np.array([0.02]))[0] == pytest.approx(0.5)
    rng = np.random.default_rng(0)
    a, b = rng.uniform(0, 1, 1000), rng.uniform(0, 1, 1000)
    v = indices.norm_diff(a, b)
    assert np.nanmax(np.abs(v)) <= 1


def test_nan_propagates_and_missing_band_gives_nan():
    assert np.isnan(indices.ndvi(np.array([np.nan]), np.array([0.4]))[0])
    refl = np.ones((2, 4, 3, 3)) * 0.2
    out = indices.compute_index("ndpi", refl, ["B02", "B03", "B04", "B08"])
    assert out.shape == (2, 3, 3) and np.isnan(out).all()


def test_index_status_only_verified_formulas_are_verified():
    verified = {k for k, d in indices.INDEX_DEFS.items() if d.status == "verified"}
    assert verified == {"ndpi", "plastic"}
    for k in ("ndvi", "ndbi", "mndwi"):
        assert indices.INDEX_DEFS[k].status == "experimental"


# ---------------------------------------------------------------- spatial

def test_disk_and_ring_are_disjoint_and_centred():
    c, r = spatial.disk_ring_masks(64, 10.0)
    assert not (c & r).any()
    assert c.sum() > 0 and r.sum() > c.sum()
    assert np.array_equal(c, c[::-1, ::-1])  # symmetric about the chip centre
    # 40 m disk on a 10 m grid whose centre falls on a pixel corner: 52 pixel centres within 40 m
    assert c.sum() == 52


def test_masked_median_respects_valid_fraction():
    v = np.ones((2, 4, 4))
    m = np.ones((4, 4), bool)
    v[1, :3, :] = np.nan  # 25 % valid
    med, frac = spatial.masked_median(v, m, 0.5)
    assert med[0] == 1 and np.isnan(med[1]) and frac[1] == pytest.approx(0.25)


def test_local_std_and_gradient():
    flat = np.full((10, 10), 0.3)
    assert np.nanmax(spatial.local_std(flat)) == pytest.approx(0, abs=1e-6)
    ramp = np.tile(np.arange(10, dtype=float) * 0.01, (10, 1))
    g = spatial.grad_mag(ramp)
    assert np.nanmedian(g[2:-2, 2:-2]) == pytest.approx(0.01)
    holed = flat.copy()
    holed[5, 5] = np.nan
    assert np.isnan(spatial.grad_mag(holed)[5, 4])


# ---------------------------------------------------------------- temporal

def _months(n, start="2020-01-01"):
    return pd.date_range(start, periods=n, freq="MS")


def test_yoy_uses_same_month_and_never_interpolates():
    s = pd.Series(np.arange(30, dtype=float), index=_months(30))
    s.iloc[5] = np.nan
    d = temporal.yoy(s)
    assert d.iloc[:12].isna().all()
    assert d.iloc[12] == 12
    assert np.isnan(d.iloc[17])  # its reference month (index 5) is missing


def test_yoy_with_absent_months_in_the_index():
    idx = _months(30).delete([10, 11, 12])  # months absent from the axis, not just NaN
    s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    d = temporal.yoy(s)
    # 2021-02 (index 13 on the full axis) refers to 2020-02 (index 1): values 10 and 1
    assert d.loc[pd.Timestamp("2021-02-01")] == pytest.approx(10 - 1)
    assert np.isnan(d.loc[pd.Timestamp("2021-12-01")])  # 2020-12 absent


def test_trailing_count_and_std():
    s = pd.Series(np.r_[np.ones(6), np.full(6, np.nan), np.ones(12)], index=_months(24))
    assert temporal.trailing_count(s).iloc[11] == 6
    assert np.isfinite(temporal.trailing_std(s).iloc[11])
    assert np.isnan(temporal.trailing_std(s, min_valid=7).iloc[11])


def test_cv_linear_of_constant_db_is_zero():
    s = pd.Series(np.full(24, -10.0), index=_months(24))
    assert temporal.trailing_cv_linear_db(s).iloc[-1] == pytest.approx(0)


# ---------------------------------------------------------------- site features

def synthetic_chip(n=64, t=36, with_s1=True, with_s2=True, change_at=24):
    rng = np.random.default_rng(1)
    months = _months(t, "2021-01-01")
    ds = xr.Dataset(coords={"month": months, "y": np.arange(n), "x": np.arange(n), "band": BANDS})
    ds.attrs.update({"resolution_m": 10.0, "chip_size_px": n, "site_id": "X001"})
    c, _ = spatial.disk_ring_masks(n, 10.0, r_centre=60)
    if with_s2:
        refl = np.empty((t, len(BANDS), n, n))
        veg = np.array([0.03, 0.06, 0.04, 0.40, 0.20, 0.10])
        pv = np.array([0.08, 0.08, 0.08, 0.12, 0.20, 0.10])
        refl[:] = veg[None, :, None, None]
        refl[change_at:, :, c] = pv[None, :, None]
        refl += rng.normal(0, 0.002, refl.shape)
        count = np.full((t, n, n), 5.0)
        refl[3] = np.nan
        count[3] = 0
        ds["s2_refl"] = (("month", "band", "y", "x"), refl)
        ds["s2_clear_count"] = (("month", "y", "x"), count)
        ds["s2_flag_bright"] = (("month",), np.zeros(t, bool))
    if with_s1:
        vv = np.full((t, n, n), -12.0) + rng.normal(0, 0.5, (t, n, n))
        vv[change_at:, c] += 5.0
        ds["s1_vv_db"] = (("month", "y", "x"), vv)
        ds["s1_vh_db"] = (("month", "y", "x"), vv - 7.0)
        ds["s1_n_scenes"] = (("month",), np.full(t, 4))
    return ds


def test_site_features_columns_are_exactly_the_allow_list():
    df = site_features(synthetic_chip())
    assert tuple(df.columns) == ID_COLUMNS + FEATURE_COLUMNS
    assert len(df) == 36


def test_site_features_missing_month_stays_nan_with_zero_count():
    df = site_features(synthetic_chip())
    assert np.isnan(df.loc[3, "s2_ndvi_c"]) and df.loc[3, "s2_valid_c"] == 0
    assert np.isnan(df.loc[15, "s2_ndvi_c_yoy"])  # reference month 3 is missing


def test_site_features_respond_to_a_centre_change():
    df = site_features(synthetic_chip())
    before, after = df.loc[20, "s2_ndvi_ctr"], df.loc[30, "s2_ndvi_ctr"]
    assert before == pytest.approx(0, abs=0.02) and after < -0.5
    assert df.loc[30, "s2_ndvi_c_yoy"] < -0.5
    assert df.loc[30, "s1_vv_c_yoy"] > 3 and df.loc[30, "s1_vv_ctr"] > 3
    assert df.loc[30, "s1_vvvh_c"] == pytest.approx(7.0, abs=0.01)


def test_quality_flag_blanks_s2_features():
    ds = synthetic_chip()
    flag = np.zeros(36, bool)
    flag[10] = True
    ds["s2_flag_bright"] = (("month",), flag)
    df = site_features(ds)
    assert df.loc[10, "s2_qc_flag"] == 1 and np.isnan(df.loc[10, "s2_vnir_c"])


def test_missing_sensor_gives_nan_columns_and_other_chip_sizes_work():
    df = site_features(synthetic_chip(with_s1=False))
    assert df.filter(like="s1_").isna().all().all()
    df = site_features(synthetic_chip(with_s2=False))
    assert df.filter(like="s2_").drop(columns=["s2_qc_flag"]).isna().all().all()
    df = site_features(synthetic_chip(n=48, t=14))
    assert len(df) == 14


def test_features_ignore_registry_attributes():
    ds = synthetic_chip()
    a = site_features(ds)
    ds.attrs.update({"reg_commissioning_date": "2022-01-01", "power_kw": 5000,
                     "other_registered_sites_in_chip": '{"ground_pv": 1}'})
    b = site_features(ds)
    pd.testing.assert_frame_equal(a, b)


# ---------------------------------------------------------------- allow-list guard

def test_allow_list_never_intersects_registry_columns():
    df = pd.DataFrame(columns=list(FEATURE_COLUMNS) + list(ID_COLUMNS))
    assert registry_columns(df) == []
    reg = ["reg_commissioning_date", "reg_status", "power_kw", "n_units", "flag_power_high"]
    mixed = pd.DataFrame(columns=list(FEATURE_COLUMNS) + reg)
    assert sorted(registry_columns(mixed)) == sorted(reg)
    assert not set(registry_columns(mixed)) & set(FEATURE_COLUMNS)


def test_experimental_columns_are_inside_the_allow_list():
    assert set(EXPERIMENTAL) <= set(FEATURE_COLUMNS)
    assert all(c.split("_")[1] in {"ndvi", "ndbi", "mndwi"} for c in EXPERIMENTAL)
