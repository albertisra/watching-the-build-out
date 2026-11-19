"""CDSE Sentinel Hub Statistical API client (used for the R3 cloud-mask test).

Server-side statistics: no pixels are downloaded. Auth is the CDSE account password grant for
the public client ``cdse-public``; the four ``CDSE_*`` variables are read from the environment
(``.env`` through python-dotenv) and never printed. The OAuth client in ``.env`` is not used
because the identity server rejected it (invalid_client) on 2026-11-18.

Quota (docs/research/access_platforms.md facts 7, 8): 10,000 requests and 10,000 processing units
per month, 300 per minute. Every call is counted in ``Counters`` and logged by ``quota.Stage``.
"""

from __future__ import annotations

import os
import threading
import time

import requests
from dotenv import load_dotenv

from bo import paths

from .quota import GLOBAL, Counters

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

_lock = threading.Lock()
_token: dict = {"value": None, "exp": 0.0, "grant": None}
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


def _token_request(session=requests) -> tuple[str, float, str]:
    """Client-credentials grant first, password grant (public client) as fallback.

    Values come from the environment (``.env`` through python-dotenv) and are never printed.
    """
    load_dotenv(paths.REPO_ROOT / ".env")
    cid, sec = os.environ.get("CDSE_CLIENT_ID"), os.environ.get("CDSE_CLIENT_SECRET")
    if cid and sec:
        r = session.post(TOKEN_URL, timeout=30, data={
            "grant_type": "client_credentials", "client_id": cid, "client_secret": sec})
        if r.status_code == 200:
            j = r.json()
            return j["access_token"], float(j.get("expires_in", 600)), "client_credentials"
    r = session.post(TOKEN_URL, timeout=30, data={
        "grant_type": "password", "client_id": "cdse-public",
        "username": os.environ["CDSE_USERNAME"], "password": os.environ["CDSE_PASSWORD"]})
    r.raise_for_status()
    j = r.json()
    return j["access_token"], float(j.get("expires_in", 600)), "password"


def get_token() -> str:
    with _lock:
        if _token["value"] and time.time() < _token["exp"] - 60:
            return _token["value"]
        tok, exp, grant = _token_request()
        _token.update(value=tok, exp=time.time() + exp, grant=grant)
        return tok


CLD_THRESHOLDS = (10, 30, 50)  # percent; sensitivity set for the cloud-probability alternative

R3_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["SCL", "CLD", "dataMask"]}],
    output: [
      {id: "scl", bands: 12, sampleType: "UINT8"},
      {id: "cld", bands: 3, sampleType: "UINT8"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(s) {
  var scl = [0,0,0,0,0,0,0,0,0,0,0,0];
  scl[s.SCL] = 1;
  return {
    scl: scl,
    cld: [s.CLD <= 10 ? 1 : 0, s.CLD <= 30 ? 1 : 0, s.CLD <= 50 ? 1 : 0],
    dataMask: [s.dataMask]
  };
}
"""


def stats_request(polygon_xy: list[list[float]], epsg: int, start: str, end: str,
                  evalscript: str = R3_EVALSCRIPT, counters: Counters = GLOBAL,
                  interval: str = "P1D", retries: int = 4) -> dict:
    """Daily statistics of the evalscript outputs over one polygon (UTM metres)."""
    body = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": [polygon_xy]},
                       "properties": {"crs": f"http://www.opengis.net/def/crs/EPSG/0/{epsg}"}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {}}],
        },
        "aggregation": {
            "timeRange": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
            "aggregationInterval": {"of": interval},
            "evalscript": evalscript, "resx": 10, "resy": 10,
        },
    }
    last = None
    for attempt in range(retries):
        r = requests.post(STATS_URL, json=body, timeout=180,
                          headers={"Authorization": f"Bearer {get_token()}"})
        counters.add(sentinel_hub_requests=1)
        if r.status_code == 200:
            pu = r.headers.get("x-processingunits-spent")
            if pu:
                counters.add(sentinel_hub_pu=float(pu))
            return r.json()
        last = f"HTTP {r.status_code} {r.text[:200]}"
        if r.status_code in (429, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        break
    raise RuntimeError(f"Statistical API failed: {last}")


# ----------------------------------------------------------------------------------------------
# Process API: server-side monthly composites for one chip and one calendar year
# ----------------------------------------------------------------------------------------------
import io
import json
import tarfile

import numpy as np

from .config import S2_BANDS
from .geo import ChipGrid

JS_MEDIAN = """function median(a) {
  var n = a.length;
  if (n === 0) { return NaN; }
  a.sort(function (x, y) { return x - y; });
  return n % 2 ? a[(n - 1) / 2] : 0.5 * (a[n / 2 - 1] + a[n / 2]);
}
"""

# Same rules as the Python pipeline: A5 clear = SCL 4, 5, 6; alternative = SCL 2, 4, 5, 6, 7;
# cloud-probability alternative = Sen2Cor CLD <= 30 percent (A33). Reflectance floored at 0.
NODATA_U16 = 65535
S2_PER_MONTH = len(S2_BANDS) + 3  # medians, clear count, alt count, CLD count


def s2_evalscript(bands: tuple[str, ...] = S2_BANDS) -> str:
    nb = len(bands)
    bl = ", ".join(f'"{b}"' for b in bands)
    return f"""//VERSION=3
var BANDS = [{bl}];
var NODATA = 65535;
{JS_MEDIAN}
function setup() {{
  return {{
    input: [{{bands: [{bl}, "SCL", "CLD", "dataMask"]}}],
    output: [{{id: "m", bands: {12 * (nb + 3)}, sampleType: "UINT16"}}],
    mosaicking: "ORBIT", temporal: true
  }};
}}
function compute(samples, months) {{
  var out = [];
  for (var m = 0; m < 12; m++) {{
    var vals = [];
    for (var k = 0; k < BANDS.length; k++) {{ vals.push([]); }}
    var c456 = 0, calt = 0, ccld = 0;
    for (var i = 0; i < samples.length; i++) {{
      if (months[i] !== m) {{ continue; }}
      var s = samples[i];
      if (!s.dataMask) {{ continue; }}
      var scl = s.SCL;
      if (scl === 4 || scl === 5 || scl === 6) {{
        c456++;
        for (var k = 0; k < BANDS.length; k++) {{ vals[k].push(Math.max(0, s[BANDS[k]])); }}
      }}
      if (scl === 2 || scl === 4 || scl === 5 || scl === 6 || scl === 7) {{ calt++; }}
      if (s.CLD <= 30) {{ ccld++; }}
    }}
    for (var k = 0; k < BANDS.length; k++) {{
      var md = median(vals[k]);
      out.push(isNaN(md) ? NODATA : Math.round(md * 10000));
    }}
    out.push(c456); out.push(calt); out.push(ccld);
  }}
  return out;
}}
function evaluatePixel(samples, scenes) {{
  var months = [];
  for (var i = 0; i < scenes.orbits.length; i++) {{
    months.push(new Date(scenes.orbits[i].dateFrom).getUTCMonth());
  }}
  return {{m: compute(samples, months)}};
}}
function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {{
  var o = [];
  for (var i = 0; i < scenes.orbits.length; i++) {{
    var t = scenes.orbits[i].tiles.map(function (x) {{ return x.dataPath; }});
    o.push({{date: scenes.orbits[i].dateFrom, tiles: t}});
  }}
  outputMetadata.userData = {{orbits: o}};
}}
"""


def process_body(grid: ChipGrid, evalscript: str, collection: str, year: int, data_extra: dict,
                 processing: dict | None = None, time_from: str | None = None,
                 time_to: str | None = None) -> dict:
    """Request body; the time range is the calendar year unless ``time_from`` / ``time_to`` (dates) are given
    (used to cap requests at the end of the store axis and to refetch single months)."""
    l, b, r, t = grid.bounds
    d = {"type": collection,
         "dataFilter": {"timeRange": {"from": f"{time_from or f'{year}-01-01'}T00:00:00Z",
                                      "to": f"{time_to or f'{year}-12-31'}T23:59:59Z"},
                        **data_extra.get("filter", {})}}
    if processing:
        d["processing"] = processing
    return {
        "input": {"bounds": {"bbox": [l, b, r, t], "properties": {
            "crs": f"http://www.opengis.net/def/crs/EPSG/0/{grid.epsg}"}}, "data": [d]},
        "output": {"width": grid.size, "height": grid.size, "responses": [
            {"identifier": "m", "format": {"type": "image/tiff"}},
            {"identifier": "userdata", "format": {"type": "application/json"}}]},
        "evalscript": evalscript,
    }


def s2_body(grid: ChipGrid, year: int, bands: tuple[str, ...] = S2_BANDS) -> dict:
    # harmonizeValues is stated explicitly: values are returned on the pre-04.00 convention, so
    # the Planetary Computer rule (DN - 1000 for baseline >= 04.00, floor 0) is already applied
    return process_body(grid, s2_evalscript(bands), "sentinel-2-l2a", year, {},
                        {"harmonizeValues": True})


def post_process(body: dict, counters: Counters = GLOBAL, retries: int = 5, log_stage: str | None = None,
                 log_note: str = "") -> tuple[np.ndarray, dict, float]:
    """POST to the Process API; returns (array bands x H x W, userdata, PU spent)."""
    import rasterio

    last = None
    for attempt in range(retries):
        r = requests.post(PROCESS_URL, json=body, timeout=300, headers={
            "Authorization": f"Bearer {get_token()}", "Accept": "application/tar"})
        counters.add(sentinel_hub_requests=1)
        pu = float(r.headers.get("x-processingunits-spent", 0) or 0)
        counters.add(sentinel_hub_pu=pu)
        if log_stage:  # one row per request, written at once
            from .quota import append_request_row

            append_request_row(log_stage, pu, f"{log_note} HTTP {r.status_code}")
        if r.status_code == 200:
            with tarfile.open(fileobj=io.BytesIO(r.content)) as tf:
                names = tf.getnames()
                tif = next(n for n in names if n.endswith(".tif"))
                tif_bytes = tf.extractfile(tif).read()
                ud = json.loads(tf.extractfile("userdata.json").read()) if "userdata.json" in names else {}
            with rasterio.MemoryFile(tif_bytes) as mf, mf.open() as ds:
                arr = ds.read()
            return arr, ud, pu
        last = f"HTTP {r.status_code} {r.text[:300]}"
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        break
    raise RuntimeError(f"Process API failed: {last}")


def split_s2_year(arr: np.ndarray, nb: int = len(S2_BANDS)) -> dict:
    """(12*(nb+3), H, W) -> refl (12, nb, H, W), counts (12, H, W) x 3."""
    a = arr.reshape(12, nb + 3, *arr.shape[1:])
    refl = a[:, :nb].astype(np.float32) / 10000.0
    refl[a[:, :nb] == NODATA_U16] = np.nan
    return {"refl": refl, "count": a[:, nb].astype(np.uint16),
            "count_alt": a[:, nb + 1].astype(np.uint16), "count_cld30": a[:, nb + 2].astype(np.uint16)}


# ----------------------------------------------------------------------------------------------
# Sentinel-1: gamma0 terrain-flattened dB, one relative orbit enforced inside the evalscript
# ----------------------------------------------------------------------------------------------
# Relative orbit from the absolute orbit in the product name; offsets and the S1C change in
# June 2026 are documented in ``s1orbit`` (fitted on Planetary Computer items, all four satellites).
JS_REL_ORBIT = """function relOrbit(path) {
  var m = /\\/(S1[ABCD])_IW_GRDH_1S[DS][VH]{1}_\\d{8}T\\d{6}_\\d{8}T\\d{6}_(\\d{6})_/.exec(path);
  if (!m) { return -1; }
  var a = parseInt(m[2], 10);
  if (m[1] === "S1A") { return (a - 73) % 175 + 1; }
  if (m[1] === "S1B") { return (a - 27) % 175 + 1; }
  if (m[1] === "S1C") { return (a - (a >= 8260 ? 99 : 172)) % 175 + 1; }
  if (m[1] === "S1D") { return (a - 42) % 175 + 1; }
  return -1;
}
"""


def s1_evalscript(rel_orbit: int, pols: tuple[str, ...] = ("VV", "VH")) -> str:
    from .s1 import S1_DB_CEIL, S1_DB_FLOOR

    floors = [S1_DB_FLOOR["vv"] if p == "VV" else S1_DB_FLOOR["vh"] for p in pols]
    pl = ", ".join(f'"{p}"' for p in pols)
    n = 12 * (len(pols) + 1)
    return f"""//VERSION=3
var POLS = [{pl}];
var REL = {int(rel_orbit)};
var FLOORS = {floors};  // A42 validity window in dB, applied per scene before the median and the count
var CEIL = {S1_DB_CEIL};
var NODATA = 65535;
{JS_MEDIAN}{JS_REL_ORBIT}
function setup() {{
  return {{
    input: [{{bands: [{pl}, "dataMask"]}}],
    output: [{{id: "m", bands: {n}, sampleType: "UINT16"}}],
    mosaicking: "ORBIT", temporal: true
  }};
}}
// dB values are stored as round((dB + 50) * 1000), so 0 .. 64000; NODATA marks no observation
function compute(samples, months) {{
  var out = [];
  for (var m = 0; m < 12; m++) {{
    var vals = [];
    for (var k = 0; k < POLS.length; k++) {{ vals.push([]); }}
    var n = 0;
    for (var i = 0; i < samples.length; i++) {{
      if (months[i] !== m) {{ continue; }}
      var s = samples[i];
      if (!s.dataMask) {{ continue; }}
      var ok = true, db = [];
      for (var k = 0; k < POLS.length; k++) {{
        if (!(s[POLS[k]] > 0)) {{ ok = false; break; }}
        db.push(10 * Math.log(s[POLS[k]]) / Math.LN10);
      }}
      if (!ok) {{ continue; }}
      // count follows the first polarisation (VV): outside its window the scene is dropped for both
      if (!(db[0] >= FLOORS[0] && db[0] <= CEIL)) {{ continue; }}
      n++;
      for (var k = 0; k < POLS.length; k++) {{
        if (db[k] >= FLOORS[k] && db[k] <= CEIL) {{ vals[k].push(db[k]); }}
      }}
    }}
    for (var k = 0; k < POLS.length; k++) {{
      var md = median(vals[k]);
      out.push(isNaN(md) ? NODATA : Math.round((md + 50) * 1000));
    }}
    out.push(n);
  }}
  return out;
}}
// samples of other relative orbits get month -1 and are ignored: one orbit per series
function evaluatePixel(samples, scenes) {{
  var months = [];
  for (var i = 0; i < scenes.orbits.length; i++) {{
    var o = scenes.orbits[i];
    var keep = o.tiles.length > 0 && relOrbit(o.tiles[0].dataPath) === REL;
    months.push(keep ? new Date(o.dateFrom).getUTCMonth() : -1);
  }}
  return {{m: compute(samples, months)}};
}}
function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {{
  var o = [];
  for (var i = 0; i < scenes.orbits.length; i++) {{
    var t = scenes.orbits[i].tiles.map(function (x) {{ return x.dataPath; }});
    if (t.length > 0 && relOrbit(t[0]) === REL) {{ o.push({{date: scenes.orbits[i].dateFrom, tiles: t}}); }}
  }}
  outputMetadata.userData = {{orbits: o}};
}}
"""


def s1_body(grid: ChipGrid, year: int, direction: str, rel_orbit: int,
            pols: tuple[str, ...] = ("VV", "VH"), time_from: str | None = None,
            time_to: str | None = None) -> dict:
    return process_body(
        grid, s1_evalscript(rel_orbit, pols), "sentinel-1-grd", year,
        {"filter": {"acquisitionMode": "IW", "polarization": "DV", "resolution": "HIGH",
                    "orbitDirection": direction.upper()}},
        {"backCoeff": "GAMMA0_TERRAIN", "orthorectify": True, "demInstance": "COPERNICUS_30",
         "speckleFilter": {"type": "NONE"}}, time_from, time_to)


def split_s1_year(arr: np.ndarray, npol: int = 2) -> dict:
    a = arr.reshape(12, npol + 1, *arr.shape[1:])
    db = a[:, :npol].astype(np.float32) / 1000.0 - 50.0
    db[a[:, :npol] == NODATA_U16] = np.nan
    cnt = a[:, npol].astype(np.uint16)
    if npol == 2:
        from .s1 import mask_s1_db  # A42 validity window
        db[:, 0], db[:, 1], cnt, _, _ = mask_s1_db(db[:, 0], db[:, 1], cnt)
    return {"db": db, "count": cnt}
