"""Earth Engine backend with mocked calls: request construction, orbit selection, platform guard, clean-up."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from bo.imagery import eechips as E
from bo.imagery import eecost, store
from bo.imagery.geo import chip_grid


def test_pixels_request_uses_the_chip_grid_and_numpy_format():
    g = chip_grid(11.67, 48.03)
    req = E.pixels_request("EXPR", g)
    assert req["fileFormat"] == "NUMPY_NDARRAY" and req["expression"] == "EXPR"
    t = req["grid"]["affineTransform"]
    assert (t["scaleX"], t["scaleY"]) == (10.0, -10.0)
    assert t["translateX"] == g.transform.c and t["translateY"] == g.transform.f
    assert req["grid"]["dimensions"] == {"width": 64, "height": 64}
    assert req["grid"]["crsCode"] == f"EPSG:{g.epsg}"


def test_fetch_array_stacks_named_bands_and_decodes_nodata(monkeypatch):
    g = chip_grid(11.0, 48.0, size=4)
    arr = np.zeros((4, 4), dtype=[("a", "f4"), ("b", "f4")])
    arr["a"], arr["b"] = 1.0, E.NODATA
    seen = {}
    monkeypatch.setattr(E.ee.data, "computePixels", lambda req: seen.update(req=req) or arr)
    out = E.fetch_array("img", g)
    assert out.shape == (2, 4, 4) and seen["req"]["grid"]["dimensions"]["width"] == 4
    a = np.concatenate([out, out]).reshape(1, 4, 4, 4)  # fake: 1 month, 4 band slots
    r = E.split_s2(np.concatenate([np.full((6, 4, 4), E.NODATA), np.ones((3, 4, 4)) * 2] * 12).astype(np.float32))
    assert np.isnan(r["refl"]).all() and (r["count"] == 2).all() and a.shape[0] == 1
    s1 = E.split_s1(np.concatenate([np.full((2, 4, 4), E.NODATA), np.full((1, 4, 4), 3.0)] * 12).astype(np.float32))
    assert np.isnan(s1["db"]).all() and (s1["count"] == 3).all()


def test_orbit_selection_from_catalogue_metadata_is_one_orbit_and_deterministic():
    ms = lambda d: int(pd.Timestamp(d).timestamp() * 1000)
    rows = [{"relativeOrbitNumber_start": 66, "orbitProperties_pass": "DESCENDING", "system:time_start": ms(f"2024-01-{i:02d}")}
            for i in range(1, 6)]
    rows += [{"relativeOrbitNumber_start": 168, "orbitProperties_pass": "DESCENDING", "system:time_start": ms(f"2024-01-{i:02d}")}
             for i in range(1, 4)]
    recs = E.orbit_records(rows)
    from bo.imagery.s1 import select_orbit

    ch = select_orbit(recs)
    assert (ch.relative_orbit, ch.direction, ch.n_dates) == (66, "descending", 5)


def test_choose_orbit_reads_catalogue_columns(monkeypatch):
    class FakeCol:
        def filterDate(self, *a):
            return self

        def reduceColumns(self, reducer, props):
            assert props == ["relativeOrbitNumber_start", "orbitProperties_pass", "system:time_start"]
            return SimpleNamespace(get=lambda k: SimpleNamespace(getInfo=lambda: [
                [95, "ASCENDING", 1_700_000_000_000], [95, "ASCENDING", 1_700_086_400_000]]))

    monkeypatch.setattr(E, "s1_collection", lambda geom, contains=True: FakeCol())
    monkeypatch.setattr(E.ee.Reducer, "toList", lambda n: None)
    ch = E.choose_orbit(None, "2023-01-01", "2024-01-01")
    assert (ch.relative_orbit, ch.direction) == (95, "ascending")


def test_earthengine_stores_cannot_be_mixed_with_other_platforms(tmp_path):
    def mk(src, var):
        return xr.Dataset({var: (("month",), np.zeros(1))}, coords={"month": pd.to_datetime(["2024-01"])}, attrs={"source": src})

    store.write_site(mk("earthengine", "s2_clear_count"), "A", tmp_path / "ee")
    store.write_site(mk("sentinelhub", "s1_count"), "A", tmp_path / "sh")
    store.write_site(mk("earthengine", "s1_count"), "A", tmp_path / "ee1")
    with pytest.raises(store.PlatformMixError):
        store.read_series("A", [tmp_path / "ee", tmp_path / "sh"])
    assert {"s2_clear_count", "s1_count"} <= set(store.read_series("A", [tmp_path / "ee", tmp_path / "ee1"]).data_vars)


def test_cleanup_assets_deletes_only_prefixed_probe_assets(monkeypatch):
    monkeypatch.setattr(eecost, "project_id", lambda: "proj")
    listing = {"assets": [{"id": "projects/proj/assets/bo_probe/Q010_s2_2023_ab"},
                          {"id": "projects/proj/assets/bo_probe/keep_me"}]}
    deleted = []
    gone = eecost.cleanup_assets("Q0", delete=deleted.append, lister=lambda req: listing)
    assert gone == deleted == ["projects/proj/assets/bo_probe/Q010_s2_2023_ab"]


def test_project_id_is_scrubbed_from_messages(monkeypatch):
    monkeypatch.setattr(E, "project_id", lambda: "secret-proj")
    assert "secret-proj" not in E.scrub("Asset projects/secret-proj/assets missing")


def test_wait_eecu_reads_batch_usage(monkeypatch):
    states = iter([[{"state": "RUNNING"}], [{"state": "COMPLETED", "batch_eecu_usage_seconds": 12.5}]])
    monkeypatch.setattr(eecost.ee.data, "getTaskStatus", lambda i: next(states))
    monkeypatch.setattr(eecost.time, "sleep", lambda s: None)
    r = eecost.wait_eecu(SimpleNamespace(id="t"), poll_s=0)
    assert r["state"] == "COMPLETED" and r["eecu"] == 12.5


def test_chipview_prefers_earthengine_root_and_never_mixes(tmp_path):
    from bo.labelling import chipview

    ds = xr.Dataset({"s2_clear_count": (("month",), np.zeros(1))}, coords={"month": pd.to_datetime(["2024-01"])},
                    attrs={"source": "earthengine"})
    store.write_site(ds, "L1-0001", tmp_path / "ee_r1")
    store.write_site(ds.assign_attrs(source="sentinelhub"), "L1-0001", tmp_path / "sh_v1")
    plat, roots, names = chipview.resolve_roots("L1-0001", tmp_path)
    assert plat == "earthengine" and names == ["ee_r1"] and len(roots) == 1


def test_queue_orbit_reuse_and_budget_counting(tmp_path):
    from bo.imagery import eequeue as Q

    log = tmp_path / "q.csv"
    from bo.imagery.quota import append_ee_row

    # the log needs the standard header first
    pd.DataFrame(columns=__import__("bo.imagery.quota", fromlist=["FIELDS"]).FIELDS).to_csv(log, index=False)
    append_ee_row("x", 30.0, "ESTIMATE", log)
    append_ee_row("x", 12.5, "measured", log)
    assert Q.eecu_used_this_month(log) == pytest.approx(42.5)
    assert Q.EECU_PER_REQUEST["s2"] == pytest.approx(48.855) and Q.CAP_EECU_HOURS == 100.0


def test_queue_build_stops_cleanly_at_the_cap(monkeypatch, tmp_path):
    from bo.imagery import eequeue as Q

    Q.STOP.clear()
    monkeypatch.setattr(Q.E, "init", lambda: None)
    monkeypatch.setattr(Q, "existing_orbits", lambda q: {})
    used = {"v": 0.0}
    monkeypatch.setattr(Q, "eecu_used_this_month", lambda *a, **k: used["v"])

    def fake_build(qid, lon, lat, orbit, root, cap_s):
        used["v"] += 40.0
        (root / f"{qid}.zarr").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Q, "build_one", fake_build)
    monkeypatch.setattr(Q, "site_path", lambda qid, root: root / f"{qid}.zarr")
    q = pd.DataFrame({"queue_id": [f"L{i}" for i in range(6)], "lon": 10.0, "lat": 50.0})
    out = Q.run(q, tmp_path, workers=1, cap_hours=100 / 3600)  # cap 100 EECU-s: three sites fit
    assert len(out["done"]) == 3 and len(out["stopped"]) == 3
    Q.STOP.clear()
    out2 = Q.run(q, tmp_path, workers=1, cap_hours=1000 / 3600)  # resumable: stored chips skipped
    assert len(out2["skipped"]) == 3 and len(out2["done"]) == 3


def test_s1_fill_values_and_floor_are_masked_not_interpolated():
    from bo.imagery.s1 import S1_DB_CEIL, S1_DB_FLOOR, mask_s1_db

    vv = np.array([-49.97, -30.01, -29.9, -10.0, S1_DB_CEIL + 0.1, S1_DB_CEIL, np.nan], dtype=np.float32)
    vh = np.array([-49.97, -35.01, -34.9, -18.0, 5.0, 26.0, -20.0], dtype=np.float32)
    cnt = np.full(7, 3, np.uint16)
    v2, h2, c2, bv, bh = mask_s1_db(vv, vh, cnt)
    assert S1_DB_FLOOR == {"vv": -30.0, "vh": -35.0}
    assert np.isnan(v2[:2]).all() and np.isnan(v2[4]) and np.isnan(v2[6])
    assert list(v2[[2, 3, 5]]) == [np.float32(-29.9), -10.0, S1_DB_CEIL]  # kept unchanged, no interpolation
    assert np.isnan(h2[[0, 1, 5]]).all() and h2[2] == np.float32(-34.9)
    assert list(c2) == [0, 0, 3, 3, 0, 3, 3]  # count follows VV
    assert bv.sum() == 3 and bh.sum() == 3


def test_split_s1_masks_fill_value_pixels_and_zeroes_count():
    a = np.zeros((36, 2, 2), np.float32)
    a[0], a[1], a[2] = -49.97, -49.97, 2  # month 1: VV and VH fill
    a[3], a[4], a[5] = -10.0, -18.0, 2  # month 2: valid
    r = E.split_s1(a)
    assert np.isnan(r["db"][0]).all() and (r["count"][0] == 0).all()
    assert (r["db"][1, 0] == -10.0).all() and (r["count"][1] == 2).all()


def test_s1_validity_mask_is_applied_per_day_before_median_and_count():
    import inspect

    src = inspect.getsource(E.s1_month_image)
    assert src.index("s1_validity_mask") < src.index("days.median()")
    assert src.index("s1_validity_mask") < src.index('select("VV").mask()')
    assert "S1_DB_FLOOR" in inspect.getsource(E.s1_validity_mask)


def test_s1_refetch_windows_group_suspect_months_by_site_year():
    from bo.imagery.s1_refetch import windows_by_site

    plan = pd.DataFrame({"root": "ee_r1", "site_id": "A", "month": ["2020-03", "2020-07", "2021-01"]})
    assert windows_by_site(plan) == {("ee_r1", "A"): [(2020, 3, 7), (2021, 1, 1)]}


def test_s1_suspect_months_flags_partial_vv_footprint():
    from bo.imagery.s1_refetch_plan import suspect_months

    vv = np.full((3, 2, 2), -12.0, np.float32)
    vv[1, 0, 0] = np.nan  # partial footprint with a scene
    vv[2] = np.nan  # no scene: not suspect
    ds = xr.Dataset({"s1_vv_db": (("month", "y", "x"), vv), "s1_n_scenes": ("month", np.array([2, 1, 0]))},
                    coords={"month": pd.date_range("2020-01-01", periods=3, freq="MS")})
    assert list(suspect_months(ds).month) == ["2020-02"]
