import numpy as np
import xarray as xr

from bo.features.site import s2_quality_mask
from bo.imagery import eechips, qc, store_fixes


def _ds(refl, count, **attrs):
    t = refl.shape[0]
    return xr.Dataset(
        {"s2_refl": (("month", "band", "y", "x"), refl), "s2_clear_count": (("month", "y", "x"), count)},
        coords={"month": np.arange(t), "band": ["B02", "B11"]}, attrs={"resolution_m": 10.0, **attrs})


def test_flag_range_centre_median_only():
    refl = np.full((3, 2, 16, 16), 0.1)
    count = np.ones((3, 16, 16), np.uint16)
    refl[0, 1, 3:13, 3:13] = 1.54  # centre bright: flagged
    refl[1, 1, 0, 0] = 5.0  # single corner outlier: not flagged
    refl[2, 1] = 1.5
    count[2] = 0  # nothing clear: not flagged
    assert qc.flag_range(refl, count).tolist() == [True, False, False]
    assert qc.flag_range(np.full((1, 2, 16, 16), 1.0), np.ones((1, 16, 16))).tolist() == [False]  # exactly 1.0 passes


def test_range_flag_masks_features_not_interpolated():
    refl = np.full((2, 2, 16, 16), 0.1)
    refl[0, 0] = 1.2
    ds = qc.add_flags(_ds(refl, np.ones((2, 16, 16), np.uint16)))
    assert ds.s2_flag_range.values.tolist() == [True, False]
    assert s2_quality_mask(ds).tolist() == [True, False]


def test_ee_attrs_fix_and_idempotent():
    ds = xr.Dataset(attrs={"source": "earthengine", "s2_offset_policy": "baseline >= 04.00: DN-1000",
                           "s2_items_by_month": "{}", "s1_items_by_month": "{}"})
    assert store_fixes.fix_ee_attrs(ds)
    assert ds.attrs["s2_offset_policy"] == eechips.EE_OFFSET_POLICY
    assert "not kept" in ds.attrs["s2_items_by_month_note"]
    other = xr.Dataset(attrs={"source": "planetary", "s2_offset_policy": "x"})
    assert not store_fixes.fix_ee_attrs(other) and other.attrs["s2_offset_policy"] == "x"


def test_zero_count_where_vv_nan():
    vv = np.array([[[np.nan, -10.0]]])
    ds = xr.Dataset({"s1_vv_db": (("month", "y", "x"), vv),
                     "s1_count": (("month", "y", "x"), np.array([[[3, 2]]], np.uint16))})
    assert store_fixes.zero_count_where_vv_nan(ds) == 1
    assert ds.s1_count.values.ravel().tolist() == [0, 2]
    assert "s1_count_fix" in ds.attrs
    assert store_fixes.zero_count_where_vv_nan(ds) == 0


def test_existing_orbits_reads_v0(tmp_path, monkeypatch):
    import pandas as pd

    from bo import paths
    from bo.imagery import eequeue

    d = tmp_path / "pilot"
    d.mkdir()
    for f, c in eequeue.REF_TABLES:
        pd.DataFrame({c: ["P1" if "v0" in f and "pilot" in f else f"X{f}"], "lat": [50.0 if "v0" in f and "pilot" in f else 10.0],
                      "lon": [9.0 if "v0" in f and "pilot" in f else 10.0]}).to_parquet(d / f)
    monkeypatch.setattr(paths, "PROCESSED", tmp_path)
    chips = tmp_path / "chips"
    monkeypatch.setattr(paths, "CHIPS", chips)
    from bo.imagery.store import write_site

    ds = xr.Dataset(attrs={"s1_relative_orbit": 139, "s1_pass_direction": "descending"})
    write_site(ds, "P1", chips / "v0")
    q = pd.DataFrame({"queue_id": ["L1-1"], "lat": [50.0], "lon": [9.0]})
    assert "v0" in eequeue.REF_ROOTS
    assert eequeue.existing_orbits(q) == {"L1-1": (139, "descending")}


def test_apply_s1_replaces_series_and_records_provenance():
    shp = (2, 2, 2)
    ds = xr.Dataset({"s1_vv_db": (("m", "y", "x"), np.zeros(shp, np.float32)), "s1_vh_db": (("m", "y", "x"), np.zeros(shp, np.float32)),
                     "s1_count": (("m", "y", "x"), np.ones(shp, np.uint16)), "s1_n_scenes": (("m",), np.ones(2, np.int16))},
                    attrs={"s1_relative_orbit": 44, "s1_pass_direction": "ascending", "s1_refetch_a42": "[]"})
    from bo.imagery.ee_orbit_fix import apply_s1

    apply_s1(ds, np.full(shp, np.nan), np.full(shp, -20.0), np.zeros(shp, np.uint16), np.zeros(2), 168, "descending",
             (44, "ascending"), "P012", "v0")
    assert ds.attrs["s1_relative_orbit"] == 168 and "s1_refetch_a42" not in ds.attrs and "s1_orbit_fix" in ds.attrs
    assert np.isnan(ds.s1_vv_db.values).all() and ds.s1_count.values.sum() == 0
