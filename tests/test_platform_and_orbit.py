"""One platform per series (review I2) and one relative orbit per series (review B3)."""

import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from bo.imagery import provenance, store
from bo.imagery.s1orbit import relative_orbit


def tiny(source, var, month="2024-01"):
    ds = xr.Dataset({var: (("month",), np.zeros(1))}, coords={"month": pd.to_datetime([month])},
                    attrs={"source": source} if source else {})
    return ds


def test_mixing_platforms_is_refused(tmp_path):
    store.write_site(tiny("sentinelhub", "s1_count"), "A", tmp_path / "sh")
    store.write_site(tiny("planetary_computer", "s2_clear_count"), "A", tmp_path / "pc")
    store.write_site(tiny(None, "s2_other"), "A", tmp_path / "old")  # old store without the attribute
    with pytest.raises(store.PlatformMixError):
        store.read_series("A", [tmp_path / "sh", tmp_path / "pc"])
    with pytest.raises(store.PlatformMixError):
        store.read_series("A", [tmp_path / "sh", tmp_path / "old"])  # missing attribute means Planetary Computer
    ok = store.read_series("A", [tmp_path / "pc", tmp_path / "old"])
    assert {"s2_clear_count", "s2_other"} <= set(ok.data_vars)


def test_same_platform_stores_merge_and_overlapping_variables_are_refused(tmp_path):
    store.write_site(tiny("sentinelhub", "s1_count"), "B", tmp_path / "s1")
    store.write_site(tiny("sentinelhub", "s2_clear_count"), "B", tmp_path / "s2")
    assert {"s1_count", "s2_clear_count"} <= set(store.read_series("B", [tmp_path / "s1", tmp_path / "s2"]).data_vars)
    store.write_site(tiny("sentinelhub", "s1_count"), "B", tmp_path / "dup")
    with pytest.raises(ValueError):
        store.read_series("B", [tmp_path / "s1", tmp_path / "dup"])


def test_new_planetary_computer_datasets_carry_the_source_attribute():
    from bo.imagery.config import ChipConfig
    from bo.imagery.geo import chip_grid

    g = chip_grid(11.0, 48.0, size=4)
    s1 = {"months": np.array(["2024-01"], "datetime64[M]"), "vv_db": np.zeros((1, 4, 4), np.float32),
          "vh_db": np.zeros((1, 4, 4), np.float32), "count": np.zeros((1, 4, 4), np.uint16),
          "n_scenes": np.zeros(1, np.int16), "relative_orbit": 1, "direction": "ascending",
          "orbit_candidates": "[]", "items_by_month": "{}", "speckle": "none", "pols": "vv,vh"}
    ds = store.build_dataset("X", g, ChipConfig(size=4), None, s1, "2024-01-01", "2024-01-31")
    assert store.source_of(ds) == "planetary_computer"


def test_orbit_consistency_flags_other_orbit_items(tmp_path):
    ok = "S1A_IW_GRDH_1SDV_20240208T053405_20240208T053430_052463_065842_4F43_COG.SAFE"  # orbit 66
    bad = "S1C_IW_GRDH_1SDV_20260608T053943_20260608T054008_008010_00F000_AAAA_COG.SAFE"  # orbit 139
    ds = tiny("sentinelhub", "s1_count")
    ds.attrs.update(s1_relative_orbit=66, s1_items_by_month=json.dumps({"2024-02": [ok], "2026-06": [bad]}))
    store.write_site(ds, "C", tmp_path)
    r = provenance.orbit_consistency("C", tmp_path)
    assert r["items_on_other_orbit"] == 1 and r["months_with_other_orbit"] == "2026-06" and not r["one_orbit_per_series"]
    ds.attrs["s1_items_by_month"] = json.dumps({"2024-02": [ok]})
    store.write_site(ds, "C", tmp_path)
    assert provenance.orbit_consistency("C", tmp_path)["one_orbit_per_series"]


def test_old_boundary_value_would_have_mixed_orbits():
    # absolute orbit 8010 of S1C belongs to orbit 139; the first version (boundary 8000) gave 37 (offset 99)
    assert relative_orbit("S1C", 8010) == 139
    assert (8010 - 99) % 175 + 1 == 37


def test_clean_store_removes_out_of_axis_months(tmp_path):
    ds = tiny("sentinelhub", "s1_count")
    ds.attrs.update(s1_relative_orbit=66, s1_orbit_rule="x; S1D scenes excluded",
                    s1_items_by_month=json.dumps({"2024-01": ["a"], "2026-11": ["b"]}))
    store.write_site(ds, "D", tmp_path)
    provenance.clean_store("D", tmp_path)
    back = store.read_site("D", tmp_path)
    assert list(json.loads(back.attrs["s1_items_by_month"])) == ["2024-01"]
    assert "excluded" not in back.attrs["s1_orbit_rule"]
