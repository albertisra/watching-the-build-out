"""Open state orthophoto (DOP) access layer: georeferenced chips with flight date.

One ``DopSource`` per federal state whose DOP is open data (survey in
``docs/research/dop_sources.md``, licences in ``docs/data_sources.md``). A chip is requested as a
WMS 1.3.0 GetMap in the state projected CRS (EPSG:25832 or 25833), snapped to the pixel grid so
the request is reproducible, and cached under ``data/raw/dop/<state>/``. A cached request is
never repeated. At most one request per second leaves this process (``THROTTLE_S``).

Flight date: read per chip centre from the state's own metadata (WMS GetFeatureInfo on the
state's info layer, or the official flight-date tile index). Where a state publishes no such
metadata in the service, ``flight_date`` is ``None`` and ``date_known`` is False. The date is
never guessed. The date refers to the chip centre; a 640 m chip can straddle two flight blocks.

Quantity label: pixel values are observed (aerial imagery); nothing here is modelled.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests
from affine import Affine
from pyproj import Transformer

from bo import paths

USER_AGENT = "bo-research-client/0.1"
THROTTLE_S = 1.0
TIMEOUT_S = 120
DEFAULT_SIZE_M = 640.0
DEFAULT_RES_M = 0.2
RAW_DOP = paths.RAW / "dop"
CHIPS_DOP = paths.CHIPS / "dop"
ST_TILE_INDEX = RAW_DOP / "st_aktualitaet" / "dop_aktualitaet.zip"

_last_request = 0.0


@dataclass(frozen=True)
class DopSource:
    key: str
    state: str  # Bundesland name as in the pilot table
    office: str
    url: str  # WMS endpoint without query string
    layer: str
    epsg: int  # CRS the state publishes in natively
    native_res_m: float
    max_px: int  # documented MaxWidth/MaxHeight of the service
    licence: str
    attribution: str
    image_format: str = "image/png"
    date_method: str = "none"  # gfi | st_tile_index | none
    info_layer: str | None = None
    date_note: str = ""
    edition_year: int | None = None  # year in the service title, when the day is not exposed
    use_restriction: str = ""  # non-empty: service terms restrict external use; see docs
    production_info: bool = False  # info layer gives a production (not flight) date
    extra_params: dict = field(default_factory=dict, hash=False, compare=False)


SOURCES: dict[str, DopSource] = {s.state: s for s in [
    DopSource("BY", "Bayern", "Landesamt für Digitalisierung, Breitband und Vermessung (LDBV)",
              "https://geoservices.bayern.de/od/wms/dop/v1/dop20", "by_dop20c", 25832, 0.2, 6000,
              "CC BY 4.0", "© Bayerische Vermessungsverwaltung (LDBV), CC BY 4.0, modified",
              date_method="gfi", info_layer="by_dop20_info"),
    DopSource("BW", "Baden-Württemberg", "Landesamt für Geoinformation und Landentwicklung (LGL-BW)",
              "https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C",
              "IMAGES_DOP_20_RGB", 25832, 0.2, 15000, "dl-de/by-2-0",
              "LGL-BW (2024), Datenlizenz Deutschland - Namensnennung - Version 2.0, www.lgl-bw.de",
              date_note="service has no queryable flight-date layer"),
    DopSource("BE", "Berlin", "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen",
              "https://gdi.berlin.de/services/wms/truedop_2024", "truedop_2024", 25833, 0.2, 15000,
              "dl-de/zero-2-0", "Geoportal Berlin / TrueDOP 2024 (no attribution required)",
              date_note="service is the 2024 edition; day of flight not exposed", edition_year=2024),
    DopSource("BB", "Brandenburg", "Landesvermessung und Geobasisinformation Brandenburg (LGB)",
              "https://isk.geobasis-bb.de/mapproxy/dop20c/service/wms", "bebb_dop20c", 25833, 0.2,
              8000, "dl-de/by-2-0", "© GeoBasis-DE/LGB, dl-de/by-2-0 (Daten geändert)",
              date_note="info layer bb_dop_info returns HTTP 500 on GetFeatureInfo (2026-11-18)"),
    DopSource("HB", "Bremen", "Landesamt GeoInformation Bremen",
              "https://geodienste.bremen.de/wms_dop20_2023", "DOP20_2023_HB", 25832, 0.2, 14276,
              "CC BY (version not stated in service)", "Quelle: Landesamt GeoInformation Bremen",
              date_note="service is the 2023 edition; day of flight not exposed", edition_year=2023),
    DopSource("MV", "Mecklenburg-Vorpommern", "Landesamt für innere Verwaltung M-V, AfGVK",
              "https://www.geodaten-mv.de/dienste/adv_dop", "mv_dop", 25833, 0.2, 4192,
              "not open data: INSPIRE 13(1)(e) access restriction; internal use allowed, other external use needs approval (AGNB AfGVK)", "© GeoBasis-DE/M-V <year of last data delivery>",
              use_restriction="service metadata: external use beyond internal processes needs permission and may be charged",
              date_method="gfi", info_layer="mv_dop_info"),
    DopSource("HE", "Hessen", "Hessisches Landesamt für Bodenmanagement und Geoinformation (HLBG, HVBG)",
              "https://www.gds-srv.hessen.de/cgi-bin/lika-services/ogc-free-images.ows",
              "he_dop20_rgb", 25832, 0.2, 3000, "HVGG §18/§24: free, no restriction or condition",
              "Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation (modified)",
              date_method="gfi", info_layer="he_dop_rgb_info"),
    DopSource("NI", "Niedersachsen", "Landesamt für Geoinformation und Landentwicklung (LGLN)",
              "https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms", "ni_dop20", 25832,
              0.2, 15000, "CC BY 4.0", "LGLN (<year>) Creative Commons Namensnennung 4.0 International",
              date_method="gfi", info_layer="ni_dop20_info"),
    DopSource("NW", "Nordrhein-Westfalen", "Geobasis NRW (Bezirksregierung Köln)",
              "https://www.wms.nrw.de/geobasis/wms_nw_dop", "nw_dop_rgb", 25832, 0.1, 5000,
              "dl-de/zero-2-0", "none required (Datenlizenz Deutschland Zero 2.0)",
              date_method="gfi", info_layer="nw_dop_utm_info",
              date_note="native 10 cm; chip requested at 20 cm so 640 m fits MaxWidth 5000"),
    DopSource("RP", "Rheinland-Pfalz", "Landesamt für Vermessung und Geobasisinformation RLP",
              "https://geo4.service24.rlp.de/wms/rp_dop20.fcgi", "rp_dop20", 25832, 0.2, 10000,
              "dl-de/by-2-0",
              "©GeoBasis-DE / LVermGeoRP (Jahr des Datenbezugs), dl-de/by-2-0, http://www.lvermgeo.rlp.de [Daten bearbeitet]",
              date_note="info layer gives production date ('erstellung'), not flight date",
              date_method="gfi", info_layer="rp_dop20_info", production_info=True),
    DopSource("SH", "Schleswig-Holstein", "Landesamt für Vermessung und Geoinformation SH (LVermGeo SH)",
              "https://dienste.gdi-sh.de/WMS_SH_DOP20col_OpenGBD", "sh_dop20_rgb", 25832, 0.2, 5000,
              "CC BY 4.0", "© GeoBasis-DE/LVermGeo SH/CC BY 4.0",
              date_note="service has a single layer, no flight-date information"),
    DopSource("SN", "Sachsen", "Landesamt für Geobasisinformation Sachsen (GeoSN)",
              "https://geodienste.sachsen.de/wms_geosn_dop-rgb/guest", "sn_dop_020", 25833, 0.2,
              4096, "dl-de/by-2-0", "Quelle: GeoSN, dl-de/by-2-0",
              date_method="gfi", info_layer="sn_dop_020_info"),
    DopSource("ST", "Sachsen-Anhalt", "Landesamt für Vermessung und Geoinformation (LVermGeo ST)",
              "https://www.geodatenportal.sachsen-anhalt.de/wss/service/ST_LVermGeo_DOP_WMS_OpenData/guest",
              "lsa_lvermgeo_dop20_2", 25832, 0.2, 4096, "dl-de/by-2-0",
              "© LVermGeo ST, dl-de/by-2-0", date_method="st_tile_index"),
    DopSource("TH", "Thüringen", "Thüringer Landesamt für Bodenmanagement und Geoinformation",
              "https://www.geoproxy.geoportal-th.de/geoproxy/services/DOP20", "th_dop", 25832, 0.2,
              5000, "CC BY 4.0", "© GDI-Th",
              date_note="info layer gives production date, not flight date",
              date_method="gfi", info_layer="th_dop_info", production_info=True),
]}
SOURCES_BY_KEY = {s.key: s for s in SOURCES.values()}


def bayern_history_source(year: int) -> DopSource:
    """Bavarian historical DOP of one flight year (same office, CC BY 4.0; 20 cm from 2006)."""
    base = SOURCES["Bayern"]
    return DopSource(
        "BY", "Bayern", base.office, "https://geoservices.bayern.de/od/wms/histdop/v1/histdop",
        f"by_dop_{year}_h", 25832, 0.2 if year >= 2006 else 0.4, 6000, base.licence,
        base.attribution, date_method="gfi", info_layer=f"by_dop_{year}_h_info")


def restricted_states() -> set[str]:
    """State names whose DOP terms restrict external use (e.g. Mecklenburg-Vorpommern)."""
    return {s.state for s in SOURCES.values() if s.use_restriction}


def drop_restricted(df: pd.DataFrame, state_col: str = "state") -> pd.DataFrame:
    """Remove rows derived from use-restricted DOP before anything is written to results/.

    Chips from those states may stay in data/ for internal use; nothing measured on them
    (areas, flight dates, counts) may be published (KICKOFF rule 6, review phase-2-r3 R3-B1).
    """
    return df[~df[state_col].isin(restricted_states())].copy()
# Pilot-table state names without a usable open source (see docs/research/dop_sources.md).
NO_SOURCE_REASON = {
    "Hamburg": "WMS has a time dimension mixing aerial years with closed-licence Maxar satellite years; not coded",
    "Saarland": "not confirmed open; LVGL terms on its WMS charge for use beyond viewing",
}


# ---------------------------------------------------------------- geometry

def to_projected(lat: float, lon: float, epsg: int) -> tuple[float, float]:
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    x, y = t.transform(lon, lat)
    return float(x), float(y)


def chip_grid(x: float, y: float, size_m: float = DEFAULT_SIZE_M, res_m: float = DEFAULT_RES_M):
    """Pixel-aligned square grid centred on (x, y). Returns (bbox, n_px, transform).

    The origin is snapped to a multiple of ``res_m`` so repeated requests for the same site give
    the identical bbox (and hence the same cache key). The point lies within half a pixel of the
    chip centre.
    """
    n = round(size_m / res_m)
    if n % 2:
        n += 1
    minx = round((x - n * res_m / 2) / res_m) * res_m
    maxy = round((y + n * res_m / 2) / res_m) * res_m
    bbox = (minx, maxy - n * res_m, minx + n * res_m, maxy)
    return bbox, n, Affine(res_m, 0.0, minx, 0.0, -res_m, maxy)


def getmap_params(src: DopSource, bbox, n_px: int, layer: str | None = None) -> dict:
    """WMS 1.3.0 GetMap parameters. For EPSG:2583x the axis order is easting, northing."""
    if n_px > src.max_px:
        raise ValueError(f"{src.key}: {n_px} px exceeds documented MaxWidth {src.max_px}")
    p = {
        "service": "WMS", "version": "1.3.0", "request": "GetMap",
        "layers": layer or src.layer, "styles": "", "crs": f"EPSG:{src.epsg}",
        "bbox": ",".join(f"{v:.3f}" for v in bbox), "width": n_px, "height": n_px,
        "format": src.image_format, "transparent": "FALSE",
    }
    p.update(src.extra_params)
    return p


def getfeatureinfo_params(src: DopSource, x: float, y: float, info_layer: str | None = None,
                          info_format: str = "text/plain") -> dict:
    """GetFeatureInfo on a 101 m window centred on (x, y); pixel (50, 50) is the centre."""
    lay = info_layer or src.info_layer
    return {
        "service": "WMS", "version": "1.3.0", "request": "GetFeatureInfo", "layers": lay,
        "query_layers": lay, "styles": "", "crs": f"EPSG:{src.epsg}",
        "bbox": f"{x - 50:.3f},{y - 50:.3f},{x + 50:.3f},{y + 50:.3f}", "width": 100,
        "height": 100, "i": 50, "j": 50, "info_format": info_format, "format": "image/png",
    }


def build_url(base: str, params: dict) -> str:
    return f"{base}?{urlencode(params)}"


# ---------------------------------------------------------------- cache + throttle

def cache_path(state_key: str, url: str, suffix: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    return RAW_DOP / state_key / f"{h}{suffix}"


def _throttle() -> None:
    global _last_request
    wait = THROTTLE_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def cached_get(state_key: str, url: str, suffix: str, session=None) -> tuple[bytes, Path, bool]:
    """Return (body, path, from_cache). Network only if the file is absent; one request/second."""
    path = cache_path(state_key, url, suffix)
    if path.exists():
        return path.read_bytes(), path, True
    _throttle()
    sess = session or requests
    r = sess.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "")
    body = r.content
    if suffix in (".png", ".jpg", ".tif") and not ctype.lower().startswith("image/"):
        raise RuntimeError(f"{state_key}: service did not return an image ({ctype}): {body[:200]!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    meta = {"url": url, "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "content_type": ctype, "bytes": len(body)}
    path.with_suffix(path.suffix + ".json").write_text(json.dumps(meta, indent=1))
    return body, path, False


# ---------------------------------------------------------------- flight date parsing

_KV = re.compile(r"^\s*([\wäöüÄÖÜß\-]+)\s*=\s*'?(.*?)'?\s*$")


def parse_kv_text(text: str) -> dict[str, str]:
    """Parse MapServer/GeoServer text/plain GetFeatureInfo ('key = 'value'' lines)."""
    out = {}
    for line in text.splitlines():
        m = _KV.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _d(s: str, fmt: str) -> date | None:
    try:
        return datetime.strptime(s, fmt).date()
    except ValueError:
        return None


def parse_flight_date(state_key: str, text: str) -> tuple[date | None, str]:
    """Extract the flight date from a GetFeatureInfo body. Returns (date or None, raw string).

    BY: ``ua = 'dd.mm.yyyy'``; NW: ``Bildflugdatum``; MV: ``Befliegungszeitraum = 'yyyy-mm-dd'``;
    NI (GML): ``<BF_DATUM>yyyymmdd``; SN: ``Datum: 20.03. +  26.03.2024`` (first date, the year
    is taken from the last date when the first has none).
    """
    if state_key == "BY":
        v = parse_kv_text(text).get("ua", "")
        return _d(v, "%d.%m.%Y"), v
    if state_key == "NW":
        v = parse_kv_text(text).get("Bildflugdatum", "")
        return _d(v, "%d.%m.%Y"), v
    if state_key == "HE":
        v = parse_kv_text(text).get("bildflug", "")
        return _d(v, "%d-%m-%Y"), v
    if state_key == "MV":
        v = parse_kv_text(text).get("Befliegungszeitraum", "")
        return _d(v, "%Y-%m-%d"), v
    if state_key == "NI":
        m = re.search(r"<BF_DATUM>(\d{8})<", text)
        return (_d(m.group(1), "%Y%m%d") if m else None), (m.group(1) if m else "")
    if state_key == "SN":
        m = re.search(r"Datum:\s*([^\n|]+)", text)
        raw = m.group(1).strip() if m else ""
        parts = re.findall(r"\d{1,2}\.\d{1,2}\.(?:\d{4})?", raw)
        years = re.findall(r"\d{4}", raw)
        if not parts or not years:
            return None, raw
        first = parts[0] if re.search(r"\d{4}$", parts[0]) else parts[0] + years[-1]
        return _d(first, "%d.%m.%Y"), raw
    return None, ""


def parse_production_date(state_key: str, text: str) -> tuple[date | None, str]:
    """RP (``erstellung = dd.mm.yyyy``) and TH (``Erstellung=dd.mm.yyyy``): production date only."""
    m = re.search(r"(?:erstellung|Erstellung)\s*=\s*'?(\d{2}\.\d{2}\.\d{4})", text)
    return (_d(m.group(1), "%d.%m.%Y") if m else None), (m.group(1) if m else "")


def st_flight_date(x: float, y: float, index_zip: Path = ST_TILE_INDEX) -> tuple[date | None, str]:
    """Sachsen-Anhalt: flight date of the 2 km DOP tile containing (x, y) in EPSG:25832.

    Source: LVermGeo ST tile index ``dop_aktualitaet.zip`` (field BFDATUM), cached once.
    """
    if not index_zip.exists():
        return None, "tile index not cached"
    from shapely.geometry import Point

    g = _load_st_index(str(index_zip))
    hit = g[g.geometry.contains(Point(x, y))]
    if hit.empty:
        return None, "outside tile index"
    row = hit.iloc[0]
    return pd.Timestamp(row["BFDATUM"]).date(), f"{row['NAME']} {row['BFLOS']}"


_ST_CACHE: dict = {}


def _load_st_index(zip_path: str):
    if zip_path not in _ST_CACHE:
        import zipfile

        import geopandas as gpd

        with zipfile.ZipFile(zip_path) as z:
            shp = next(n for n in z.namelist() if n.endswith(".shp"))
        _ST_CACHE[zip_path] = gpd.read_file(f"zip://{zip_path}!{shp}")
    return _ST_CACHE[zip_path]


def lookup_flight_date(src: DopSource, x: float, y: float, session=None) -> dict:
    """Flight date at (x, y). Returns dict(flight_date, date_known, date_source, date_raw, note)."""
    out = {"flight_date": None, "date_known": False, "date_type": "none", "production_date": None,
           "flight_year": src.edition_year, "date_source": None, "date_raw": "",
           "date_note": src.date_note}
    if src.edition_year:
        out.update(date_type="year_edition", date_source="service title (edition year)")
    if src.date_method == "gfi":
        fmt = "application/vnd.ogc.gml" if src.key == "NI" else "text/plain"
        url = build_url(src.url, getfeatureinfo_params(src, x, y, info_format=fmt))
        body, _, _ = cached_get(src.key, url, ".txt", session)
        txt = body.decode("utf-8", errors="replace")
        out.update(date_source=f"{src.url} GetFeatureInfo {src.info_layer}")
        if src.production_info:
            d, raw = parse_production_date(src.key, txt)
            out.update(date_raw=raw, date_type="production_only" if d else "none",
                       production_date=d.isoformat() if d else None)
        else:
            d, raw = parse_flight_date(src.key, txt)
            out.update(date_raw=raw)
            if d:
                out.update(flight_date=d.isoformat(), date_known=True, date_type="day")
    elif src.date_method == "st_tile_index":
        d, raw = st_flight_date(x, y)
        out.update(date_raw=raw, date_source="LVermGeo ST dop_aktualitaet.zip (BFDATUM)")
        if d:
            out.update(flight_date=d.isoformat(), date_known=True, date_type="day")
    return out


# ---------------------------------------------------------------- chips

@dataclass
class DopChip:
    array: np.ndarray  # (3, H, W) uint8
    transform: Affine
    epsg: int
    meta: dict


def decode_image(body: bytes) -> np.ndarray:
    import io

    from PIL import Image

    im = Image.open(io.BytesIO(body)).convert("RGB")
    return np.asarray(im).transpose(2, 0, 1).copy()


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(paths.REPO_ROOT))
    except ValueError:
        return str(p)


def fetch_chip(lat: float, lon: float, state: str, size_m: float = DEFAULT_SIZE_M,
               res_m: float | None = None, session=None, with_date: bool = True,
               source: DopSource | None = None) -> DopChip:
    """Request one chip centred on (lat, lon) from the open DOP service of ``state``.

    ``res_m`` defaults to max(native resolution, 0.2 m). Raises KeyError for states without a
    usable open source.
    """
    if source is None and state not in SOURCES:
        raise KeyError(f"no open DOP source for {state}: {NO_SOURCE_REASON.get(state, 'not surveyed')}")
    src = source or SOURCES[state]
    res = res_m or max(src.native_res_m, DEFAULT_RES_M)
    if not res_m:
        for cand in (res, 0.25, 0.3, 0.4):  # coarser grid when the service MaxWidth is too small
            res = max(cand, res)
            if round(size_m / res) <= src.max_px:
                break
    x, y = to_projected(lat, lon, src.epsg)
    bbox, n, tr = chip_grid(x, y, size_m, res)
    url = build_url(src.url, getmap_params(src, bbox, n))
    body, path, cached = cached_get(src.key, url, ".png", session)
    arr = decode_image(body)
    meta = {
        "state": state, "state_key": src.key, "office": src.office, "epsg": src.epsg,
        "res_m": res, "native_res_m": src.native_res_m, "size_px": n, "bbox": list(bbox),
        "transform": list(tr)[:6], "centre_x": x, "centre_y": y, "source_url": url,
        "raw_path": _rel(path), "from_cache": cached,
        "licence": src.licence, "attribution": src.attribution,
        "use_restriction": src.use_restriction, "quantity_type": "observed",
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    meta.update(lookup_flight_date(src, x, y, session) if with_date else
                {"flight_date": None, "date_known": False, "date_type": "none", "date_source": None,
                 "date_raw": "", "date_note": "date lookup skipped"})
    if not meta["date_known"]:
        meta["flag"] = "no_flight_date"
    return DopChip(arr, tr, src.epsg, meta)


def save_chip(chip: DopChip, site_id: str, out_dir: Path = CHIPS_DOP) -> Path:
    """Write GeoTIFF (3 bands, uint8, DEFLATE) plus a JSON sidecar with the metadata."""
    import rasterio

    out_dir.mkdir(parents=True, exist_ok=True)
    tif = out_dir / f"{site_id}.tif"
    with rasterio.open(tif, "w", driver="GTiff", height=chip.array.shape[1],
                       width=chip.array.shape[2], count=3, dtype="uint8",
                       crs=f"EPSG:{chip.epsg}", transform=chip.transform,
                       compress="deflate", tiled=True, blockxsize=256, blockysize=256) as dst:
        dst.write(chip.array)
    meta = dict(chip.meta, site_id=site_id)
    tif.with_suffix(".json").write_text(json.dumps(meta, indent=1, default=str))
    return tif

