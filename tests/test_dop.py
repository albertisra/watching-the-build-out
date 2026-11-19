"""Tests for the DOP access layer and the footprint tool (synthetic fixtures, no network)."""

import io
import json
from urllib.parse import parse_qs, urlparse

import geopandas as gpd
import numpy as np
import pytest
from affine import Affine
from PIL import Image
from shapely.geometry import box

from bo.imagery import dop, footprint

# ------------------------------------------------------------------ geometry / CRS

def test_known_point_lands_at_chip_centre():
    # Munich Marienplatz: WGS84 -> EPSG:25832 and back through the chip transform.
    src = dop.SOURCES["Bayern"]
    x, y = dop.to_projected(48.13743, 11.57549, src.epsg)
    assert 690_000 < x < 700_000 and 5_330_000 < y < 5_340_000  # inside UTM 32N, Munich
    bbox, n, tr = dop.chip_grid(x, y, 640.0, 0.2)
    assert n == 3200
    col, row = (~tr) @ (x, y)
    assert abs(col - n / 2) <= 0.5 + 1e-6 and abs(row - n / 2) <= 0.5 + 1e-6
    # transform corners equal the bbox
    assert tr @ (0, 0) == pytest.approx((bbox[0], bbox[3]))
    assert tr @ (n, n) == pytest.approx((bbox[2], bbox[1]))


def test_chip_grid_is_pixel_snapped_and_deterministic():
    b1, _, _ = dop.chip_grid(698995.8, 5323123.6, 640.0, 0.2)
    b2, _, _ = dop.chip_grid(698995.8, 5323123.6, 640.0, 0.2)
    assert b1 == b2
    for v in b1:
        assert abs(v / 0.2 - round(v / 0.2)) < 1e-6


def test_saxony_uses_utm33():
    src = dop.SOURCES["Sachsen"]
    assert src.epsg == 25833
    x, _ = dop.to_projected(51.05, 13.74, src.epsg)  # Dresden
    assert 400_000 < x < 420_000


# ------------------------------------------------------------------ request construction

def test_getmap_params_and_url():
    src = dop.SOURCES["Bayern"]
    bbox, n, _ = dop.chip_grid(698995.8, 5323123.6, 640.0, 0.2)
    q = parse_qs(urlparse(dop.build_url(src.url, dop.getmap_params(src, bbox, n))).query)
    assert q["request"] == ["GetMap"] and q["version"] == ["1.3.0"]
    assert q["crs"] == ["EPSG:25832"] and q["layers"] == ["by_dop20c"]
    assert q["width"] == q["height"] == ["3200"]
    minx, miny, maxx, maxy = (float(v) for v in q["bbox"][0].split(","))
    assert maxx - minx == pytest.approx(640.0) and maxy - miny == pytest.approx(640.0)


def test_getmap_rejects_oversized_request():
    src = dop.SOURCES["Sachsen"]  # MaxWidth 4096
    with pytest.raises(ValueError):
        dop.getmap_params(src, (0, 0, 1, 1), 5000)


def test_nrw_native_10cm_is_requested_at_20cm():
    assert dop.SOURCES["Nordrhein-Westfalen"].native_res_m == 0.1
    assert max(dop.SOURCES["Nordrhein-Westfalen"].native_res_m, dop.DEFAULT_RES_M) == 0.2


def test_getfeatureinfo_params_centre_pixel():
    src = dop.SOURCES["Bayern"]
    p = dop.getfeatureinfo_params(src, 1000.0, 2000.0)
    assert p["i"] == p["j"] == 50 and p["bbox"] == "950.000,1950.000,1050.000,2050.000"
    assert p["query_layers"] == "by_dop20_info"


def test_unknown_state_raises_with_reason():
    with pytest.raises(KeyError, match="Saarland"):
        dop.fetch_chip(49.3, 7.0, "Saarland")


# ------------------------------------------------------------------ flight date parsing

def test_parse_bayern_and_nrw_and_mv_and_ni_and_sn():
    by = "Layer 'x'\n  Feature 30: \n    nummer = '124028'\n    ua = '24.08.2024'\n"
    assert dop.parse_flight_date("BY", by)[0].isoformat() == "2024-08-24"
    nw = "    Bildflugdatum = '27.02.2026'\n    Bodenauflösung = '0.10'\n"
    assert dop.parse_flight_date("NW", nw)[0].isoformat() == "2026-02-27"
    mv = "    Befliegungsjahr = '2025'\n    Befliegungszeitraum = '2025-05-13'\n"
    assert dop.parse_flight_date("MV", mv)[0].isoformat() == "2025-05-13"
    ni = "<ni_dop20_info_feature><BF_DATUM>20250308</BF_DATUM></ni_dop20_info_feature>"
    assert dop.parse_flight_date("NI", ni)[0].isoformat() == "2025-03-08"
    sn = "Sachdatenabfrage - Kartenebene: 'x'| | Gebiet: Bautzen| | Datum: 20.03. +  26.03.2024| | ROHDOP: DOP|"
    assert dop.parse_flight_date("SN", sn)[0].isoformat() == "2024-03-20"


def test_unparseable_date_is_none_not_guessed():
    assert dop.parse_flight_date("BY", "no features were found")[0] is None
    assert dop.parse_flight_date("SH", "anything")[0] is None


def test_st_tile_index_lookup(tmp_path, monkeypatch):
    import zipfile

    d = tmp_path / "idx"
    d.mkdir()
    g = gpd.GeoDataFrame(
        {"NAME": ["t1"], "LOSNR": [1], "BFLOS": ["Test"],
         "BFDATUM": [__import__("pandas").Timestamp("2025-06-14")]},
        geometry=[box(700000, 5700000, 702000, 5702000)], crs="EPSG:25832")
    g.to_file(d / "idx.shp")
    z = tmp_path / "idx.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in d.iterdir():
            zf.write(f, f.name)
    assert dop.st_flight_date(701000, 5701000, z)[0].isoformat() == "2025-06-14"
    assert dop.st_flight_date(1.0, 1.0, z)[0] is None
    assert dop.st_flight_date(1.0, 1.0, tmp_path / "missing.zip")[0] is None


# ------------------------------------------------------------------ cache + throttle

class FakeResp:
    def __init__(self, body, ctype="image/png"):
        self.content = body
        self.headers = {"Content-Type": ctype}

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, body, ctype="image/png"):
        self.calls = []
        self.body, self.ctype = body, ctype

    def get(self, url, **kw):
        self.calls.append(url)
        return FakeResp(self.body, self.ctype)


def _png(color=(10, 120, 30), n=8):
    buf = io.BytesIO()
    Image.new("RGB", (n, n), color).save(buf, "PNG")
    return buf.getvalue()


def test_cached_response_is_never_requested_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(dop, "RAW_DOP", tmp_path)
    monkeypatch.setattr(dop, "THROTTLE_S", 0.0)
    s = FakeSession(_png())
    url = "https://example.org/wms?a=1"
    _, p1, c1 = dop.cached_get("XX", url, ".png", s)
    _, p2, c2 = dop.cached_get("XX", url, ".png", s)
    assert (c1, c2) == (False, True) and p1 == p2 and len(s.calls) == 1
    assert json.loads(p1.with_suffix(".png.json").read_text())["url"] == url


def test_non_image_reply_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(dop, "RAW_DOP", tmp_path)
    monkeypatch.setattr(dop, "THROTTLE_S", 0.0)
    s = FakeSession(b"<ServiceException/>", "text/xml")
    with pytest.raises(RuntimeError):
        dop.cached_get("XX", "https://example.org/x", ".png", s)
    assert not list(tmp_path.rglob("*.png"))


def test_throttle_enforces_one_request_per_second(monkeypatch):
    t = {"now": 100.0, "slept": 0.0}
    monkeypatch.setattr(dop.time, "monotonic", lambda: t["now"])
    monkeypatch.setattr(dop.time, "sleep", lambda s: t.__setitem__("slept", t["slept"] + s))
    monkeypatch.setattr(dop, "_last_request", 99.7)
    dop._throttle()
    assert t["slept"] == pytest.approx(0.7)


def test_fetch_chip_end_to_end_mocked(tmp_path, monkeypatch):
    monkeypatch.setattr(dop, "RAW_DOP", tmp_path / "raw")
    monkeypatch.setattr(dop, "THROTTLE_S", 0.0)

    class S(FakeSession):
        def get(self, url, **kw):
            self.calls.append(url)
            if "GetFeatureInfo" in url:
                return FakeResp(b"    ua = '24.08.2024'\n", "text/plain")
            n = int(parse_qs(urlparse(url).query)["width"][0])
            return FakeResp(_png(n=n), "image/png")

    s = S(b"")
    # 64 m chip keeps the fake image small
    c = dop.fetch_chip(48.03, 11.67, "Bayern", size_m=64.0, session=s)
    assert c.array.shape == (3, 320, 320) and c.meta["flight_date"] == "2024-08-24"
    assert c.meta["date_known"] and "flag" not in c.meta and c.meta["epsg"] == 25832
    n_calls = len(s.calls)
    dop.fetch_chip(48.03, 11.67, "Bayern", size_m=64.0, session=s)
    assert len(s.calls) == n_calls  # fully served from cache
    out = dop.save_chip(c, "T1", tmp_path / "chips")
    import rasterio

    with rasterio.open(out) as r:
        assert r.crs.to_epsg() == 25832 and r.transform == c.transform and r.count == 3


def test_state_without_date_service_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(dop, "RAW_DOP", tmp_path / "raw")
    monkeypatch.setattr(dop, "THROTTLE_S", 0.0)

    class S(FakeSession):
        def get(self, url, **kw):
            self.calls.append(url)
            n = int(parse_qs(urlparse(url).query)["width"][0])
            return FakeResp(_png(n=n))

    c = dop.fetch_chip(54.6, 8.9, "Schleswig-Holstein", size_m=64.0, session=S(b""))
    assert c.meta["flight_date"] is None and c.meta["flag"] == "no_flight_date"


# ------------------------------------------------------------------ footprint tool

def _synthetic_chip(res=0.2, n=1600):
    """320 m chip: green field, a dark-blue 40 x 20 m array, a white 12 x 2.4 m container,
    and a 0.4 m wide dark line (fence-like) that must not be traced."""
    a = np.zeros((3, n, n), np.uint8)
    a[0], a[1], a[2] = 70, 140, 50  # vegetation
    def px(m):
        return round(m / res)
    r0, c0 = n // 2 - px(10), n // 2 - px(20)
    a[:, r0:r0 + px(20), c0:c0 + px(40)] = np.array([35, 40, 70], np.uint8)[:, None, None]
    a[:, n // 2 + px(30):n // 2 + px(30) + px(2.4), n // 2 - px(6):n // 2 + px(6)] = 235
    a[:, n // 2 - px(60):n // 2 - px(60) + 2, n // 2 - px(60):n // 2 + px(60)] = 30  # thin line
    tr = Affine(res, 0, 700000.0, 0, -res, 5320000.0 + n * res)
    return a, tr


def test_polygon_area_planar_metres():
    assert footprint.polygon_area_m2(box(0, 0, 40, 20)) == pytest.approx(800.0)


def test_propose_finds_array_and_container_with_correct_area():
    a, tr = _synthetic_chip()
    g = footprint.propose(a, tr, 25832, "S1", flight_date="2024-08-24")
    assert g.crs.to_epsg() == 25832
    arr = g[g.kind == "panel_array"]
    assert len(arr) == 1
    assert arr.area_m2.iloc[0] == pytest.approx(800.0, rel=0.10)
    con = g[g.kind == "container_row"]
    assert len(con) == 1
    assert con.area_m2.iloc[0] == pytest.approx(12 * 2.4, rel=0.30)
    # the line (fence-like) produces nothing: total polygons are only these two
    assert set(g.kind) <= set(footprint.KINDS)
    assert (g.source == "auto").all() and (g.version == 1).all() and g.is_current.all()
    assert (g.quantity_type == "detected").all()
    # area column equals geometry area in the projected CRS
    assert np.allclose(g.area_m2, g.geometry.area.round(2))


def test_empty_chip_gives_no_polygons():
    a = np.zeros((3, 800, 800), np.uint8)
    a[1] = 150
    a[0], a[2] = 60, 40
    tr = Affine(0.2, 0, 700000.0, 0, -0.2, 5320160.0)
    assert footprint.propose(a, tr, 25832, "S0").empty


def test_manual_revision_keeps_history():
    a, tr = _synthetic_chip()
    g = footprint.propose(a, tr, 25832, "S1")
    pid = g.polygon_id.iloc[0]
    new = box(700100, 5320100, 700110, 5320120)  # 200 m2
    g2 = footprint.revise(g, pid, new)
    rows = g2[g2.polygon_id == pid]
    assert len(rows) == 2 and rows.is_current.sum() == 1
    cur = rows[rows.is_current].iloc[0]
    assert cur.source == "manual" and cur.version == 2 and cur.area_m2 == pytest.approx(200.0)
    with pytest.raises(KeyError):
        footprint.revise(g, "nope", new)


def test_geoparquet_roundtrip(tmp_path):
    a, tr = _synthetic_chip()
    g = footprint.propose(a, tr, 25832, "S1")
    f = tmp_path / "fp.parquet"
    g.to_parquet(f)
    back = gpd.read_parquet(f)
    assert back.crs.to_epsg() == 25832 and len(back) == len(g)


def test_hessen_date_and_resolution_fallback(tmp_path, monkeypatch):
    he = "    flugjahr = '2025'\n    bildflug = '14-06-2025'\n"
    assert dop.parse_flight_date("HE", he)[0].isoformat() == "2025-06-14"
    monkeypatch.setattr(dop, "RAW_DOP", tmp_path / "raw")
    monkeypatch.setattr(dop, "THROTTLE_S", 0.0)

    class S(FakeSession):
        def get(self, url, **kw):
            self.calls.append(url)
            if "GetFeatureInfo" in url:
                return FakeResp(he.encode(), "text/plain")
            n = int(parse_qs(urlparse(url).query)["width"][0])
            return FakeResp(_png(n=min(n, 8)), "image/png")

    # 640 m at 0.2 m = 3200 px exceeds Hessen MaxWidth 3000, so the layer falls back to 0.25 m
    c = dop.fetch_chip(50.59, 9.36, "Hessen", session=S(b""), with_date=True)
    assert c.meta["res_m"] == 0.25 and c.meta["size_px"] == 2560 and c.meta["date_known"]


def test_mecklenburg_vorpommern_is_marked_restricted():
    assert dop.SOURCES["Mecklenburg-Vorpommern"].use_restriction
