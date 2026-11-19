"""Unit tests on synthetic arrays for the imagery package (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine
from rasterio.enums import Resampling

from bo.imagery import config as C
from bo.imagery import io as bio
from bo.imagery.composite import masked_median, month_index
from bo.imagery.geo import chip_grid, transformer, utm_epsg
from bo.imagery.masking import clear_mask
from bo.imagery.reflectance import dn_to_reflectance, needs_offset, parse_baseline
from bo.imagery.s1 import select_orbit, speckle_filter, to_db


# ---------------------------------------------------------------- cloud masking
def test_clear_mask_default_rule_is_456():
    scl = np.arange(12, dtype=np.uint8).reshape(3, 4)
    m = clear_mask(scl)
    assert set(scl[m].tolist()) == {4, 5, 6}


@pytest.mark.parametrize("bad", [0, 1, 3, 8, 9, 10, 11])
def test_cloud_shadow_snow_never_clear_under_any_rule(bad):
    scl = np.full((2, 2), bad, np.uint8)
    for rule in C.CLEAR_RULES:
        assert not clear_mask(scl, rule).any()


def test_alternative_rule_keeps_unclassified_and_cast_shadow():
    scl = np.array([[2, 7], [4, 9]], np.uint8)
    assert clear_mask(scl, "scl_456").tolist() == [[False, False], [True, False]]
    assert clear_mask(scl, "scl_blacklist").tolist() == [[True, True], [True, False]]


# ---------------------------------------------------------------- reflectance offset
def test_baseline_parsing_and_cutoff():
    assert parse_baseline("05.10") == (5, 10)
    assert not needs_offset("03.00") and not needs_offset("02.12")
    assert needs_offset("04.00") and needs_offset("05.11")
    with pytest.raises(ValueError):
        parse_baseline(None)
    with pytest.raises(ValueError):
        parse_baseline("abc")


def test_offset_removes_the_step_at_baseline_04():
    surface = 0.25  # same ground reflectance
    old = dn_to_reflectance(np.array([[surface * 10000]]), "03.00")
    new = dn_to_reflectance(np.array([[surface * 10000 + 1000]]), "05.10")
    assert old[0, 0] == pytest.approx(0.25) and new[0, 0] == pytest.approx(0.25)


def test_dn_zero_is_nan_and_floor_is_zero_and_no_double_offset():
    dn = np.array([0, 500, 1000, 3000], np.uint16)
    r = dn_to_reflectance(dn, "05.10")
    assert np.isnan(r[0]) and r[1] == 0.0 and r[2] == 0.0 and r[3] == pytest.approx(0.2)
    harm = dn_to_reflectance(np.array([2000], np.uint16), "05.10", harmonised_input=True)
    assert harm[0] == pytest.approx(0.2)


# ---------------------------------------------------------------- coordinates
def test_utm_zone_for_germany():
    assert utm_epsg(11.67, 48.03) == 32632
    assert utm_epsg(14.4, 51.2) == 32633
    assert utm_epsg(6.5, 51.0) == 32632


def test_chip_grid_alignment_and_centre():
    lon, lat = 11.669333, 48.030372
    g = chip_grid(lon, lat)
    assert g.shape == (64, 64) and g.res == 10.0
    assert g.transform.c % 10 == 0 and g.transform.f % 10 == 0
    row, col = g.lonlat_to_pixel(lon, lat)
    assert abs(row - 32) <= 0.5 and abs(col - 32) <= 0.5  # centre within half a pixel


def test_pixel_lonlat_roundtrip():
    g = chip_grid(13.4, 52.5, size=32)
    lon, lat = g.pixel_center_lonlat(5, 7)
    row, col = g.lonlat_to_pixel(lon, lat)
    assert row == pytest.approx(5.5, abs=1e-6) and col == pytest.approx(7.5, abs=1e-6)


def test_configurable_chip_size():
    assert chip_grid(10.0, 50.0, size=128).shape == (128, 128)
    assert chip_grid(10.0, 50.0, size=32).bounds[2] - chip_grid(10.0, 50.0, size=32).bounds[0] == 320


# ---------------------------------------------------------------- chip extraction
def _write_tif(path, arr, epsg, transform, dtype="uint16", nodata=None):
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype=dtype,
        crs=f"EPSG:{epsg}", transform=transform, nodata=nodata,
    ) as dst:
        dst.write(arr.astype(dtype), 1)


def test_chip_extraction_geolocates_a_known_pixel(tmp_path):
    """A marked pixel at a known UTM coordinate must land at the same lon/lat in the chip."""
    g = chip_grid(11.67, 48.03)
    # source raster: 10 m, origin offset from the chip grid by 1230 m / 870 m, bigger than chip
    ox, oy = g.transform.c - 1230.0, g.transform.f + 870.0
    tr = Affine(10, 0, ox, 0, -10, oy)
    arr = np.zeros((300, 300), np.uint16)
    # mark the source pixel that contains the chip pixel (row 20, col 40)
    x, y = g.pixel_center_xy(20, 40)
    col, row = ~tr @ (x, y)
    arr[int(row), int(col)] = 777
    f = tmp_path / "a.tif"
    _write_tif(f, arr, g.epsg, tr)
    out = bio.read_on_grid(str(f), g, Resampling.nearest, sign=False)
    assert out.shape == (64, 64)
    assert out[20, 40] == 777 and (out == 777).sum() == 1


def test_south_up_raster_is_read_north_up(tmp_path):
    """Some Sentinel-1 RTC scenes have a positive y pixel size; the chip must still be north-up."""
    g = chip_grid(11.67, 48.03)
    bottom = g.transform.f - 64 * 10 - 500.0
    tr = Affine(10, 0, g.transform.c - 500.0, 0, 10, bottom)  # origin at the south-west corner
    arr = np.zeros((200, 200), np.uint16)
    x, y = g.pixel_center_xy(5, 50)  # a point near the north of the chip
    col, row = ~tr @ (x, y)
    arr[int(row), int(col)] = 321
    _write_tif(tmp_path / "f.tif", arr, g.epsg, tr)
    out = bio.read_on_grid(str(tmp_path / "f.tif"), g, Resampling.nearest, sign=False)
    assert out[5, 50] == 321 and (out == 321).sum() == 1


def test_20m_layer_is_replicated_onto_10m_grid(tmp_path):
    g = chip_grid(11.67, 48.03)
    tr = Affine(20, 0, g.transform.c - 600, 0, -20, g.transform.f + 600)
    arr = np.zeros((100, 100), np.uint8)
    arr[40, 40] = 9
    _write_tif(tmp_path / "s.tif", arr, g.epsg, tr, "uint8")
    out = bio.read_on_grid(str(tmp_path / "s.tif"), g, Resampling.nearest, sign=False)
    assert (out == 9).sum() == 4  # one 20 m pixel covers 2 x 2 chip pixels


def test_chip_outside_raster_is_filled_with_nodata(tmp_path):
    g = chip_grid(11.67, 48.03)
    tr = Affine(10, 0, g.transform.c + 320, 0, -10, g.transform.f)  # raster covers right half
    arr = np.full((64, 64), 5, np.uint16)
    _write_tif(tmp_path / "h.tif", arr, g.epsg, tr)
    out = bio.read_on_grid(str(tmp_path / "h.tif"), g, Resampling.nearest, sign=False)
    assert (out[:, :32] == 0).all() and (out[:, 32:] == 5).all()


def test_cross_zone_read_keeps_geolocation(tmp_path):
    """Raster in UTM 33N, chip grid in UTM 32N: the marked point keeps its lon/lat."""
    lon, lat = 12.0, 51.0  # zone 32 (6 to 12) boundary region, grid in 32632
    g = chip_grid(lon - 0.01, lat, epsg=32632)
    t = transformer(4326, 32633)
    x0, y0 = t.transform(lon - 0.01, lat)
    tr = Affine(10, 0, np.round(x0 / 10) * 10 - 1000, 0, -10, np.round(y0 / 10) * 10 + 1000)
    arr = np.zeros((200, 200), np.uint16)
    mx, my = t.transform(lon - 0.01 + 0.0015, lat + 0.0008)
    col, row = ~tr @ (mx, my)
    arr[int(row) - 1 : int(row) + 2, int(col) - 1 : int(col) + 2] = 1000  # 3x3 blob
    _write_tif(tmp_path / "z.tif", arr, 32633, tr, nodata=0)
    out = bio.read_on_grid(str(tmp_path / "z.tif"), g, Resampling.nearest, sign=False)
    rr, cc = np.nonzero(out)
    assert len(rr) > 0
    lo, la = g.pixel_center_lonlat(round(rr.mean()), round(cc.mean()))
    assert abs(lo - (lon - 0.01 + 0.0015)) < 3e-4 and abs(la - (lat + 0.0008)) < 3e-4


# ---------------------------------------------------------------- compositing
def test_masked_median_and_counts():
    vals = np.array([[[1.0]], [[3.0]], [[100.0]], [[7.0]]], np.float32)  # (N,1,1)
    valid = np.array([[[True]], [[True]], [[False]], [[True]]])
    med, cnt = masked_median(vals, valid)
    assert med[0, 0] == 3.0 and cnt[0, 0] == 3


def test_masked_median_with_band_axis_and_empty_pixels():
    vals = np.arange(2 * 2 * 2 * 2, dtype=np.float32).reshape(2, 2, 2, 2)  # (N,B,H,W)
    valid = np.zeros((2, 2, 2), bool)
    valid[0, 0, 0] = True
    valid[1, 0, 0] = True
    med, cnt = masked_median(vals, valid)
    assert med.shape == (2, 2, 2) and cnt.tolist() == [[2, 0], [0, 0]]
    assert med[0, 0, 0] == pytest.approx((vals[0, 0, 0, 0] + vals[1, 0, 0, 0]) / 2)
    assert np.isnan(med[:, 1, 1]).all() and np.isnan(med[:, 0, 1]).all()


def test_masked_median_no_observations_is_nan_count_zero():
    med, cnt = masked_median(np.zeros((0, 3, 4, 4), np.float32), np.zeros((0, 4, 4), bool))
    assert np.isnan(med).all() and (cnt == 0).all()


def test_month_index_covers_every_month_and_missing_is_not_filled():
    from bo.imagery.config import ChipConfig
    from bo.imagery.s2pipe import S2Obs, composite_months

    g = chip_grid(11.67, 48.03, size=4)
    cfg = ChipConfig(size=4, bands=("B04", "B08"))
    months = month_index("2024-01-01", "2024-04-30")
    assert len(months) == 4

    def obs(day, val, clear_frac):
        clear = np.zeros((4, 4), bool)
        clear.flat[: int(16 * clear_frac)] = True
        refl = np.where(clear[None], val, np.nan).astype(np.float32).repeat(2, axis=0)
        return S2Obs("k" + day, pd.Timestamp(day), ["i" + day], {"i" + day: "05.10"},
                     np.zeros(12), clear, clear, refl if clear.any() else None)

    o = [obs("2024-01-05", 0.1, 1), obs("2024-01-15", 0.3, 1), obs("2024-01-25", 0.9, 0.5),
         obs("2024-03-10", 0.2, 0)]  # Feb: no observations; March: all cloudy
    refl, cnt, _, npass, nused, items = composite_months(o, months, g, cfg)
    assert cnt[0, 0, 0] == 3 and cnt[0, 3, 3] == 2
    assert refl[0, 0, 0, 0] == pytest.approx(0.3) and refl[0, 0, 3, 3] == pytest.approx(0.2)
    assert np.isnan(refl[1]).all() and (cnt[1] == 0).all()  # February stays missing
    assert np.isnan(refl[2]).all() and (cnt[2] == 0).all() and npass[2] == 1 and nused[2] == 0
    assert npass[0] == 3 and "2024-02" not in items


# ---------------------------------------------------------------- Sentinel-1
def test_select_orbit_uses_only_covering_scenes_and_is_deterministic():
    d = pd.Timestamp
    recs = (
        [{"relative_orbit": 44, "direction": "ascending", "date": d(2024, 1, i + 1), "covers": True}
         for i in range(5)]
        + [{"relative_orbit": 95, "direction": "descending", "date": d(2024, 1, i + 1),
            "covers": False} for i in range(9)]
        + [{"relative_orbit": 168, "direction": "descending", "date": d(2024, 1, i + 1),
            "covers": True} for i in range(5)]
    )
    ch = select_orbit(recs)
    assert (ch.relative_orbit, ch.direction, ch.n_dates) == (44, "ascending", 5)  # tie: lower orbit
    assert select_orbit([]) is None
    assert select_orbit([{**recs[0], "covers": False}]) is None


def test_select_orbit_counts_distinct_dates_not_slices():
    d = pd.Timestamp
    recs = [{"relative_orbit": 1, "direction": "ascending", "date": d(2024, 1, 1), "covers": True}] * 6
    recs += [{"relative_orbit": 2, "direction": "ascending", "date": d(2024, 1, i + 1), "covers": True}
             for i in range(2)]
    assert select_orbit(recs).relative_orbit == 2


def test_to_db_and_nodata():
    lin = np.array([1.0, 0.1, 0.0, -32768.0, np.nan, -1.0], np.float32)
    db = to_db(lin)
    assert db[0] == pytest.approx(0.0) and db[1] == pytest.approx(-10.0)
    assert np.isnan(db[2:]).all()


def test_speckle_filter_reduces_variance_and_keeps_nan():
    rng = np.random.default_rng(1)
    a = rng.gamma(4.4, 1 / 4.4, (40, 40)).astype(np.float32)
    a[5, 5] = np.nan
    assert speckle_filter(a, None) is a
    for m in ("boxcar3", "lee5"):
        f = speckle_filter(a, m)
        assert np.isnan(f[5, 5]) and np.nanstd(f) < np.nanstd(a)
    with pytest.raises(ValueError):
        speckle_filter(a, "nope")


def test_build_s1_never_mixes_orbits_with_mocked_network(monkeypatch):
    from bo.imagery import s1pipe
    from bo.imagery.config import ChipConfig

    g = chip_grid(11.67, 48.03, size=4)
    from shapely.geometry import box, mapping

    geom = mapping(box(11.0, 47.5, 12.5, 48.5))

    def mk(i, orbit, direc, day):
        return SimpleNamespace(
            id=f"it{i}", datetime=pd.Timestamp(day, tz="UTC"), geometry=geom,
            properties={"sat:relative_orbit": orbit, "sat:orbit_state": direc},
            assets={"vv": None, "vh": None})

    items = [mk(i, 44, "ascending", f"2024-01-{i + 1:02d}") for i in range(4)]
    items += [mk(10 + i, 95, "descending", f"2024-01-{i + 1:02d}") for i in range(2)]
    items += [mk(20, 44, "ascending", "2024-02-03"), mk(21, 44, "ascending", "2024-02-03")]
    monkeypatch.setattr(s1pipe, "search_s1", lambda *a, **k: items)
    seen = []

    def fake_read(item, grid, cfg, counters):
        seen.append(item.id)
        v = np.full((4, 4), -10.0, np.float32)
        return {"vv": v, "vh": v - 7}

    monkeypatch.setattr(s1pipe, "read_scene", fake_read)
    out = s1pipe.build_s1(g, "2024-01-01", "2024-03-31", ChipConfig(size=4), workers=1)
    assert out["relative_orbit"] == 44 and out["direction"] == "ascending"
    assert not any(s.startswith("it1") and s != "it1" and int(s[2:]) in (10, 11) for s in seen)
    assert out["n_scenes"].tolist() == [4, 1, 0]  # same-day slices counted once, March missing
    assert np.isnan(out["vv_db"][2]).all() and (out["count"][2] == 0).all()
    assert out["vv_db"][0, 0, 0] == pytest.approx(-10.0) and out["count"][0, 0, 0] == 4


# ---------------------------------------------------------------- items, store
def test_dedupe_items_keeps_highest_baseline_per_tile_and_datatake():
    def it(i, bl, tile="32UPU", dt="GS2A_1"):
        return SimpleNamespace(id=i, datetime=pd.Timestamp("2022-06-30", tz="UTC"),
                               properties={"s2:processing_baseline": bl, "s2:mgrs_tile": tile,
                                           "s2:datatake_id": dt})

    from bo.imagery.s2pipe import dedupe_items, group_passes

    items = [it("a", "04.00"), it("b", "05.10"), it("c", "05.10", tile="32UQU")]
    kept = dedupe_items(items)
    assert sorted(i.id for i in kept) == ["b", "c"]
    assert len(group_passes(kept)) == 1  # two tiles of one data take form one pass


def test_store_roundtrip_with_metadata(tmp_path):
    from bo.imagery.config import ChipConfig
    from bo.imagery.store import build_dataset, read_site, write_site

    g = chip_grid(11.67, 48.03, size=4)
    cfg = ChipConfig(size=4, bands=("B04", "B08"))
    months = month_index("2024-01-01", "2024-03-31")
    s2 = {"months": months, "refl": np.full((3, 2, 4, 4), np.nan, np.float32),
          "count": np.zeros((3, 4, 4), np.uint16), "count_alt": np.zeros((3, 4, 4), np.uint16),
          "n_passes": np.zeros(3, np.int16), "n_used": np.zeros(3, np.int16),
          "items_by_month": "{}", "baselines": "{}"}
    s2["refl"][0] = 0.2
    ds = build_dataset("P999", g, cfg, s2, None, "2024-01-01", "2024-03-31")
    write_site(ds, "P999", tmp_path)
    back = read_site("P999", tmp_path)
    assert back.attrs["site_id"] == "P999" and back.attrs["crs_epsg"] == 32632
    assert back.attrs["transform"] == list(g.transform)[:6]
    assert "code_version" in back.attrs and "s2_processing_baseline_by_item" in back.attrs
    assert float(back.s2_refl[0, 0, 0, 0]) == pytest.approx(0.2)
    assert np.isnan(back.s2_refl[1].values).all() and int(back.s2_clear_count[1].sum()) == 0


def test_load_sites_drops_registry_fields(tmp_path):
    from bo.imagery.sites import load_sites

    df = pd.DataFrame({"pilot_id": ["P1", "P2"], "lat": [48.0, 52.0], "lon": [11.0, 13.0],
                       "status": ["x", "y"], "power_kw": [1.0, 2.0], "commissioned": ["a", "b"],
                       "reg_status": ["x", "y"], "reg_commissioning_date": ["a", "b"]})
    df.to_parquet(tmp_path / "s.parquet")
    out = load_sites(tmp_path / "s.parquet")
    assert list(out.columns) == ["site_id", "lat", "lon"]


def test_read_obs_applies_scl_rule_offset_and_skips_bands_when_all_cloudy(monkeypatch):
    from bo.imagery import s2pipe
    from bo.imagery.config import ChipConfig

    g = chip_grid(11.67, 48.03, size=4)
    cfg = ChipConfig(size=4, bands=("B04", "B08"))
    calls = []

    def make_item(name, baseline, scl_val, dn_val):
        def fake(href, grid, resampling, fill, counters):
            calls.append(href)
            if href.endswith("SCL"):
                a = np.full((4, 4), scl_val, np.uint8)
                a[0, 0] = 9  # one cloudy pixel
                return a
            a = np.full((4, 4), dn_val, np.uint16)
            a[1, 1] = 0  # no data in one pixel
            return a

        it = SimpleNamespace(
            id=name, datetime=pd.Timestamp("2024-05-03T10:00:00Z"),
            properties={"s2:processing_baseline": baseline, "s2:mgrs_tile": "32UPU",
                        "s2:datatake_id": "dt1", "platform": "sentinel-2a"},
            assets={k: SimpleNamespace(href=f"{name}/{k}") for k in ("SCL", "B04", "B08")})
        return it, fake

    it, fake = make_item("new", "05.10", 4, 3000)
    monkeypatch.setattr(s2pipe, "read_on_grid", fake)
    obs = s2pipe.read_obs([it], g, cfg, s2pipe.GLOBAL)
    assert obs.refl is not None
    assert obs.refl[0, 2, 2] == pytest.approx(0.2)  # (3000 - 1000) / 10000
    assert np.isnan(obs.refl[0, 0, 0]) and not obs.clear[0, 0]  # cloud
    assert np.isnan(obs.refl[0, 1, 1]) and not obs.clear[1, 1]  # DN 0 is no data
    assert obs.clear.sum() == 14 and obs.baselines == {"new": "05.10"}

    calls.clear()
    it2, fake2 = make_item("cloudy", "05.10", 9, 3000)
    monkeypatch.setattr(s2pipe, "read_on_grid", fake2)
    obs2 = s2pipe.read_obs([it2], g, cfg, s2pipe.GLOBAL)
    assert obs2.refl is None and not obs2.clear.any()
    assert calls == ["cloudy/SCL"]  # no band bytes spent on a fully cloudy chip
