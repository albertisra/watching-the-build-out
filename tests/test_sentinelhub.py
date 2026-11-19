"""Sentinel Hub request builders, evalscript logic (run in node when available), auth and cost."""

from __future__ import annotations

import json
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bo.imagery import sentinelhub as sh
from bo.imagery import shcost
from bo.imagery.geo import chip_grid

NODE = shutil.which("node")


def run_js(script: str, expr: str):
    out = subprocess.run([NODE, "-e", f"{script}\nconsole.log(JSON.stringify({expr}))"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def sample(scl, b=0.1, mask=1, cld=0, bands=sh.S2_BANDS):
    d = {k: b for k in bands}
    d.update(SCL=scl, CLD=cld, dataMask=mask)
    return d


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_s2_evalscript_median_counts_and_missing_months():
    nb = len(sh.S2_BANDS)
    samples = [sample(4, 0.1), sample(5, 0.3), sample(9, 0.9, cld=80), sample(7, 0.5),
               sample(4, 0.2, mask=0), sample(6, 0.2)]
    months = [0, 0, 0, 0, 0, 0]
    out = run_js(sh.s2_evalscript(), f"compute({json.dumps(samples)}, {json.dumps(months)})")
    per = nb + 3
    jan = out[:per]
    assert jan[0] == 2000  # median of the clear values 0.1, 0.3, 0.2
    assert jan[nb] == 3  # clear count SCL 4/5/6 (masked pixel and cloud excluded)
    assert jan[nb + 1] == 4  # alternative adds class 7
    assert jan[nb + 2] == 4  # CLD <= 30 with valid data mask (cloud and masked excluded)
    assert out[per] == 65535 and out[per + nb] == 0  # February: NaN sentinel and count 0


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_s2_evalscript_floors_negative_reflectance():
    out = run_js(sh.s2_evalscript(), f"compute({json.dumps([sample(4, -0.05)])}, [3])")
    assert out[3 * (len(sh.S2_BANDS) + 3)] == 0


# (satellite, absolute orbit, relative orbit) read from Planetary Computer sentinel-1-rtc items
PC_PAIRS = [
    ("S1A", 59864, 117), ("S1A", 40388, 66), ("S1A", 13314, 117),
    ("S1B", 10767, 66), ("S1B", 29441, 15), ("S1B", 29419, 168), ("S1B", 2316, 15),
    ("S1C", 1637, 66), ("S1C", 3015, 44), ("S1C", 7937, 66),  # before the June 2026 manoeuvre
    ("S1C", 8010, 139), ("S1C", 8017, 146), ("S1C", 8018, 147), ("S1C", 8257, 36), ("S1C", 8258, 37),  # old
    ("S1C", 8264, 116), ("S1C", 8265, 117), ("S1C", 9840, 117), ("S1C", 10066, 168),  # after it
    ("S1D", 2783, 117), ("S1D", 4956, 15), ("S1D", 5058, 117),
]


@pytest.mark.parametrize(("sat", "absolute", "rel"), PC_PAIRS)
def test_relative_orbit_python_matches_planetary_computer(sat, absolute, rel):
    from bo.imagery.s1orbit import relative_orbit

    assert relative_orbit(sat, absolute) == rel


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_relative_orbit_evalscript_matches_python_for_every_satellite():
    base = ("creo://eodata/Sentinel-1/SAR/IW_GRDH_1S-COG/2024/02/08/{}_IW_GRDH_1SDV_20240208T053405_"
            "20240208T053430_{:06d}_065842_4F43_COG.SAFE")
    for sat, absolute, rel in PC_PAIRS:
        assert run_js(sh.JS_REL_ORBIT, f"relOrbit({base.format(sat, absolute)!r})") == rel
    assert run_js(sh.JS_REL_ORBIT, "relOrbit('garbage')") == -1


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_s1_evalscript_never_mixes_orbits_and_converts_to_db():
    s = sh.s1_evalscript(66)
    samples = [{"VV": 0.1, "VH": 0.01, "dataMask": 1}, {"VV": 1.0, "VH": 0.1, "dataMask": 1},
               {"VV": 1.0, "VH": 0.1, "dataMask": 1}]
    months = [0, 0, -1]  # third scene belongs to another relative orbit
    out = run_js(s, f"compute({json.dumps(samples)}, {json.dumps(months)})")
    vv, vh, n = out[0:3]
    assert n == 2
    assert vv == round((-5.0 + 50) * 1000)  # median of -10 dB and 0 dB
    assert vh == round((-15.0 + 50) * 1000)
    assert out[3] == 65535 and out[5] == 0
    assert "REL = 66" in s


def test_split_roundtrips_and_nodata():
    nb = len(sh.S2_BANDS)
    a = np.zeros((12 * (nb + 3), 2, 2), np.uint16)
    a[0, 0, 0] = 2500
    a[1:nb, :, :] = 65535
    a[nb, 0, 0] = 3
    r = sh.split_s2_year(a)
    assert r["refl"][0, 0, 0, 0] == pytest.approx(0.25) and np.isnan(r["refl"][0, 1, 0, 0])
    assert r["count"][0, 0, 0] == 3 and r["refl"].shape == (12, nb, 2, 2)
    b = np.full((36, 2, 2), 65535, np.uint16)
    b[0] = 45000
    b[2] = 4
    r1 = sh.split_s1_year(b)
    assert r1["db"][0, 0, 0, 0] == pytest.approx(-5.0) and np.isnan(r1["db"][1, 0, 0, 0])
    assert r1["count"][0, 0, 0] == 4


def test_request_body_is_on_the_chip_grid_and_states_harmonisation():
    g = chip_grid(11.67, 48.03)
    b = sh.s2_body(g, 2024)
    l, bt, r, t = g.bounds
    assert b["input"]["bounds"]["bbox"] == [l, bt, r, t]
    assert b["input"]["bounds"]["properties"]["crs"].endswith(f"/{g.epsg}")
    assert (b["output"]["width"], b["output"]["height"]) == (64, 64)
    d = b["input"]["data"][0]
    assert d["processing"] == {"harmonizeValues": True} and d["type"] == "sentinel-2-l2a"
    assert d["dataFilter"]["timeRange"]["from"].startswith("2024-01-01")
    b1 = sh.s1_body(g, 2019, "descending", 95)
    d1 = b1["input"]["data"][0]
    assert d1["dataFilter"]["orbitDirection"] == "DESCENDING"
    assert d1["processing"]["backCoeff"] == "GAMMA0_TERRAIN" and d1["processing"]["orthorectify"]


def test_auth_tries_client_credentials_first_then_password(monkeypatch):
    calls = []

    class S:
        def __init__(self, ok):
            self.ok = ok

        def post(self, url, data=None, timeout=None):
            calls.append(data["grant_type"])
            good = data["grant_type"] == "client_credentials" and self.ok or data["grant_type"] == "password"
            return SimpleNamespace(
                status_code=200 if good else 401,
                json=lambda: {"access_token": "t", "expires_in": 600},
                raise_for_status=lambda: None)

    monkeypatch.setenv("CDSE_CLIENT_ID", "x")
    monkeypatch.setenv("CDSE_CLIENT_SECRET", "y")
    monkeypatch.setenv("CDSE_USERNAME", "u")
    monkeypatch.setenv("CDSE_PASSWORD", "p")
    monkeypatch.setattr(sh, "load_dotenv", lambda *a, **k: None)
    assert sh._token_request(S(False))[2] == "password" and calls == ["client_credentials", "password"]
    calls.clear()
    assert sh._token_request(S(True))[2] == "client_credentials" and calls == ["client_credentials"]
    calls.clear()
    monkeypatch.delenv("CDSE_CLIENT_ID")
    assert sh._token_request(S(True))[2] == "password" and calls == ["password"]


def test_cost_model_matches_probes_and_decision_rule(tmp_path):
    # probe: 146 samples, 8 input bands -> 6.083 PU
    c = shcost.estimate(pd.DataFrame({"site_id": ["a", "a"], "year": [2023, 2024],
                                      "s2_samples": [0, 146], "s1_dates": [0, 31]}))
    assert c.s2_pu.sum() == pytest.approx(6.0833, abs=1e-3)
    assert c.s1_pu.sum() == pytest.approx(1.5885, abs=1e-3)
    assert c.s2_requests.sum() == 1 and c.s1_requests.sum() == 1
    assert shcost.decide(1000, 500, 900, 400)["proceed"] is True
    assert shcost.decide(5200, 500, 900, 400)["proceed"] is False  # 6100 PU > 60 percent
    assert shcost.decide(100, 5700, 0, 400)["proceed"] is False  # requests
    log = tmp_path / "q.csv"
    month = pd.Timestamp.now("UTC").strftime("%Y-%m")
    pd.DataFrame({"timestamp_utc": [f"{month}-01T00:00:00Z"] * 3 + ["2020-01-01T00:00:00Z"],
                  "stage": ["a", "a_site", "b", "c"], "platform": ["cdse_sentinelhub"] * 4,
                  "sentinel_hub_pu": [10.0, 10.0, 5.0, 99.0],
                  "sentinel_hub_requests": [2, 2, 1, 9]}).to_csv(log, index=False)
    assert shcost.used_this_month(log) == (15.0, 3)


def test_build_many_sh_hard_budget_stop_and_resume(monkeypatch, tmp_path):
    from bo.imagery import shchips
    from bo.imagery.quota import GLOBAL

    built = []

    def fake(site_id, lon, lat, y2, y1, orbit, start, end, root=None, sensors=("s1", "s2"), **k):
        GLOBAL.add(sentinel_hub_pu=40.0, sentinel_hub_requests=10)
        (tmp_path / f"{site_id}.zarr").mkdir()
        built.append((site_id, sensors))

    monkeypatch.setattr(shchips, "build_site_sh", fake)
    monkeypatch.setattr("bo.imagery.store.site_path", lambda sid, root=None: tmp_path / f"{sid}.zarr")
    monkeypatch.setattr(shchips, "Stage", lambda *a, **k: __import__("contextlib").nullcontext())
    sites = pd.DataFrame({"site_id": [f"Q{i:03d}" for i in range(10)], "lat": 50.0, "lon": 10.0})
    plan = pd.DataFrame({"site_id": sites.site_id, "year": 2024, "s2_samples": 1, "s1_dates": 1,
                         "s1_rel_orbit": 1, "s1_direction": "ascending"})
    done, failed = shchips.build_many_sh(sites, plan, "2024-01-01", "2024-12-31", tmp_path, workers=1,
                                         sensors=("s1",), pu_cap=200.0, margin_pu=40.0)
    assert len(done) == 5 and all(f[1] == "BUDGET_STOP" for f in failed) and len(failed) == 5
    assert {s for _, s in built} == {("s1",)}
    n = len(built)
    done2, _ = shchips.build_many_sh(sites, plan, "2024-01-01", "2024-12-31", tmp_path, workers=1,
                                     sensors=("s1",))  # resume without cap: stored chips skipped
    assert len(built) == 10 and len(done2) == 10 and n == 5


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_s1_evalscript_masks_window_per_scene_before_median_and_count():
    s = sh.s1_evalscript(66)
    # linear 1e-5 = -50 dB (fill-like) in VV; 0.1 / 0.01 are -10 / -20 dB
    samples = [{"VV": 1e-5, "VH": 1e-5, "dataMask": 1}, {"VV": 0.1, "VH": 0.01, "dataMask": 1},
               {"VV": 0.1, "VH": 1e-5, "dataMask": 1}]  # third: VV valid, VH below its floor
    out = run_js(s, f"compute({json.dumps(samples)}, [0, 0, 0])")
    vv, vh, n = out[0:3]
    assert n == 2  # the -50 dB scene is not counted
    assert vv == round((-10.0 + 50) * 1000)
    assert vh == round((-20.0 + 50) * 1000)  # only the valid VH value enters the median
    assert "FLOORS = [-30.0, -35.0]" in s
