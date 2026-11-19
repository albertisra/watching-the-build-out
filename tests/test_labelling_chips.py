"""Chip resolution and rendering for the labelling view (synthetic stores, no real chips)."""

import numpy as np
import pytest
import xarray as xr

from bo.imagery import store
from bo.labelling import chipview


def synth(path_root, site, source, with_s2, n=14):
    months = np.array([f"2024-{m:02d}-01" for m in range(1, 13)] + ["2025-01-01", "2025-02-01"], "datetime64[ns]")[:n]
    d = {}
    coords = {"month": months, "y": np.arange(64), "x": np.arange(64)}
    if with_s2:
        coords["band"] = ["B02", "B03", "B04", "B08"]
        refl = np.random.default_rng(0).uniform(0.02, 0.3, (n, 4, 64, 64)).astype("float32")
        refl[3] = np.nan  # a missing month
        d["s2_refl"] = (("month", "band", "y", "x"), refl)
        cnt = np.full((n, 64, 64), 2.0, "float32")
        cnt[3] = 0
        d["s2_clear_count"] = (("month", "y", "x"), cnt)
    vv = np.random.default_rng(1).uniform(-20, -5, (n, 64, 64)).astype("float32")
    vv[5] = np.nan
    d["s1_vv_db"] = (("month", "y", "x"), vv)
    d["s1_vh_db"] = (("month", "y", "x"), vv - 6)
    ds = xr.Dataset(d, coords=coords, attrs={"source": source, "resolution_m": 10, "code_version": "t"})
    store.write_site(ds, site, path_root)


def test_resolve_prefers_one_platform(tmp_path):
    synth(tmp_path / "sh_v1_s1", "A", "sentinelhub", False)
    synth(tmp_path / "v0", "A", "planetary_computer", True)
    plat, _, names = chipview.resolve_roots("A", tmp_path)
    assert plat == "planetary_computer" and names == ["v0"]  # S2 available there, S1-only on Sentinel Hub
    synth(tmp_path / "sh_v1", "A", "sentinelhub", True)
    plat, _, names = chipview.resolve_roots("A", tmp_path)
    assert plat == "sentinelhub" and names == ["sh_v1"]
    with pytest.raises(FileNotFoundError):
        chipview.resolve_roots("ZZ", tmp_path)


def test_s1_only_store_and_empty_frames(tmp_path):
    synth(tmp_path / "sh_v1_s1", "B", "sentinelhub", False)
    p, plat, _ = chipview.load_site("B", tmp_path)
    assert plat == "sentinelhub" and not p.has_s2 and p.s1_ok.sum() == p.n - 1
    im = chipview.render_strip(p, 5, 9)
    assert im.width > 900
    assert chipview.render_large(p, "vv", 5).size == (320, 320)  # missing month: empty frame, no error
    assert chipview.s1_plot(p, 2)[:4] == b"\x89PNG"


def test_missing_s2_month_is_empty_not_interpolated(tmp_path):
    synth(tmp_path / "v0", "C", "planetary_computer", True)
    p, _, _ = chipview.load_site("C", tmp_path)
    assert not p.s2_ok[3] and p.s2_ok[2] and p.s2_count[3] == 0
    a = np.asarray(chipview.render_large(p, "tc", 3))
    assert a.std() < 60  # flat empty frame with text only, not an image of neighbouring months


def test_window_start_clamps():
    assert chipview.window_start(0, 100, 9) == 0
    assert chipview.window_start(99, 100, 9) == 91
    assert chipview.window_start(50, 100, 9) == 46
