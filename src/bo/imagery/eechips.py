"""Chip stores built on Google Earth Engine (Community tier, free non-commercial project).

Same 64 x 64 pixel chips at 10 m on the local UTM grid and the same monthly products as the Sentinel Hub backend, fetched
with ``ee.data.computePixels`` straight to numpy (no export, no Drive, no Cloud Storage). Stores carry ``source = earthengine``.

Sentinel-2: ``COPERNICUS/S2_SR_HARMONIZED`` (values already harmonised to the pre-04.00 convention, so no offset is
applied here). Median of clear pixels (SCL 4, 5, 6; A5), three per-pixel counts: SCL 4/5/6, the alternative SCL rule
(2, 4, 5, 6, 7) and the cloud-probability alternative, for which **Cloud Score+ ``cs_cdf`` >= 0.60** is used
(``GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED``, the Sen2Cor CLD band is not in the Earth Engine product). Tiles of one
sensing day are mosaicked first so an overlap of two tiles counts once.

Sentinel-1: ``COPERNICUS/S1_GRD``, IW, VV and VH, one fixed (relative orbit, direction) per site chosen from the catalogue
property ``relativeOrbitNumber_start`` (no formula). **Product difference:** Earth Engine GRD is sigma0 in dB with border
and thermal noise removal and an ellipsoid-based terrain correction (SRTM, ASTER DEM); it is NOT gamma0 terrain-flattened
like the Sentinel Hub stores (gamma0 terrain, Copernicus 30 m DEM) or the Planetary Computer RTC. Levels differ on slopes
and by the incidence-angle dependence of sigma0 against gamma0; series from the platforms must not be combined.

Credentials: ``EE_PROJECT`` from ``.env`` (explicit path). The project id is never written to logs or results.
"""

from __future__ import annotations

import os
import time

import ee
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from bo import paths

from .composite import month_index
from .config import ChipConfig
from .geo import ChipGrid, chip_grid
from .s1 import S1_DB_CEIL, S1_DB_FLOOR, mask_s1_db, select_orbit
from .store import build_dataset, write_site

S2_EE_BANDS = ("B2", "B3", "B4", "B8", "B11", "B12")
S2_STORE_BANDS = ("B02", "B03", "B04", "B08", "B11", "B12")
CSP_THRESHOLD = 0.60
NODATA = -9999.0
S2_PER_MONTH = len(S2_EE_BANDS) + 3
S1_PER_MONTH = 3  # VV dB, VH dB, count


def project_id() -> str:
    load_dotenv(paths.REPO_ROOT / ".env")
    return os.environ["EE_PROJECT"]


def scrub(text: str) -> str:
    """Remove the project id from any message that could reach a log or a result file."""
    try:
        return text.replace(project_id(), "<project>")
    except KeyError:
        return text


def init() -> None:
    ee.Initialize(project=project_id())


def grid_request(grid: ChipGrid) -> dict:
    """The ``grid`` part of a computePixels request for a chip (pure)."""
    return {
        "dimensions": {"width": grid.size, "height": grid.size},
        "affineTransform": {"scaleX": grid.res, "shearX": 0, "translateX": grid.transform.c,
                            "shearY": 0, "scaleY": -grid.res, "translateY": grid.transform.f},
        "crsCode": f"EPSG:{grid.epsg}",
    }


def pixels_request(expression, grid: ChipGrid) -> dict:
    return {"expression": expression, "fileFormat": "NUMPY_NDARRAY", "grid": grid_request(grid)}


def chip_geometry(grid: ChipGrid):
    l, b, r, t = grid.bounds
    return ee.Geometry.Rectangle([l, b, r, t], proj=f"EPSG:{grid.epsg}", geodesic=False)


def fetch_array(image, grid: ChipGrid, retries: int = 4) -> np.ndarray:
    """computePixels to a float array (bands, H, W); masked pixels were unmasked to NODATA server-side."""
    last = None
    for attempt in range(retries):
        try:
            arr = ee.data.computePixels(pixels_request(image, grid))
            names = arr.dtype.names
            return np.stack([arr[n] for n in names]).astype(np.float32)
        except ee.EEException as e:  # quota, transient errors
            last = scrub(str(e))
            if "limit" in last.lower() and "exceed" in last.lower():
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"computePixels failed: {last[:200]}")


# ----------------------------------------------------------------------------- Sentinel-2
def _daily_mosaics(col: ee.ImageCollection, start: ee.Date, end: ee.Date) -> ee.ImageCollection:
    """One image per sensing day (tiles of the same day mosaicked, so tile overlaps count once)."""
    col = col.filterDate(start, end)
    days = col.aggregate_array("system:time_start").map(
        lambda t: ee.Date(t).format("YYYY-MM-dd")).distinct()

    def one(d):
        d = ee.Date(d)
        return col.filterDate(d, d.advance(1, "day")).mosaic().set("system:time_start", d.millis())

    return ee.ImageCollection(days.map(one))


def s2_month_image(geom, year: int, month: int) -> ee.Image:
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(geom)
    csp = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED").filterBounds(geom)
    s2 = s2.linkCollection(csp, ["cs_cdf"]).select(list(S2_EE_BANDS) + ["SCL", "cs_cdf"])
    days = _daily_mosaics(s2, start, end)
    scl = days.select("SCL")
    clear = scl.map(lambda im: im.eq(4).Or(im.eq(5)).Or(im.eq(6)).rename("c"))
    alt = scl.map(lambda im: im.eq(2).Or(im.eq(4)).Or(im.eq(5)).Or(im.eq(6)).Or(im.eq(7)).rename("c"))
    csp_ok = days.select("cs_cdf").map(lambda im: im.gte(CSP_THRESHOLD).rename("c"))

    def mask_clear(im):
        s = im.select("SCL")
        return im.select(list(S2_EE_BANDS)).updateMask(s.eq(4).Or(s.eq(5)).Or(s.eq(6)))

    med = days.map(mask_clear).median().divide(10000).max(0).unmask(NODATA)
    med = med.rename(list(S2_STORE_BANDS))
    def cnt(c, n):
        return c.sum().unmask(0).rename(n)

    real = ee.Image.cat([med, cnt(clear, "n456"), cnt(alt, "nalt"), cnt(csp_ok, "ncsp")])
    names = [*S2_STORE_BANDS, "n456", "nalt", "ncsp"]
    empty = ee.Image.constant([NODATA] * len(S2_STORE_BANDS) + [0, 0, 0]).rename(names)
    return ee.Image(ee.Algorithms.If(days.size().gt(0), real, empty))  # a month without any image stays missing


def s2_year_image(geom, year: int) -> ee.Image:
    return ee.Image.cat([s2_month_image(geom, year, m).rename(
        [f"{b}_{m:02d}" for b in (*S2_STORE_BANDS, "n456", "nalt", "ncsp")]) for m in range(1, 13)])


def split_s2(arr: np.ndarray) -> dict:
    a = arr.reshape(12, S2_PER_MONTH, *arr.shape[1:])
    nb = len(S2_STORE_BANDS)
    refl = a[:, :nb].copy()
    refl[refl <= NODATA + 1] = np.nan
    return {"refl": refl, "count": a[:, nb].astype(np.uint16), "count_alt": a[:, nb + 1].astype(np.uint16),
            "count_csp": a[:, nb + 2].astype(np.uint16)}


# ----------------------------------------------------------------------------- Sentinel-1
def s1_collection(geom, contains: bool = True) -> ee.ImageCollection:
    c = (ee.ImageCollection("COPERNICUS/S1_GRD").filter(ee.Filter.eq("instrumentMode", "IW"))
         .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
         .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))
    return c.filter(ee.Filter.contains(".geo", geom)) if contains else c.filterBounds(geom)


def orbit_records(rows: list[dict]) -> list[dict]:
    """Catalogue rows (relativeOrbitNumber_start, orbitProperties_pass, time_start ms) -> select_orbit records."""
    out = []
    for r in rows:
        out.append({"relative_orbit": int(r["relativeOrbitNumber_start"]),
                    "direction": str(r["orbitProperties_pass"]).lower(),
                    "date": pd.Timestamp(r["system:time_start"], unit="ms").date(), "covers": True})
    return out


def choose_orbit(geom, start: str, end: str):
    """(relative orbit, direction) with most acquisition days among scenes intersecting the chip (ties: lower orbit)."""
    col = s1_collection(geom, contains=False).filterDate(start, end)  # intersecting scenes: the contains filter is far too slow
    info = col.reduceColumns(ee.Reducer.toList(3), ["relativeOrbitNumber_start", "orbitProperties_pass",
                                                    "system:time_start"]).get("list").getInfo()
    rows = [{"relativeOrbitNumber_start": a, "orbitProperties_pass": b, "system:time_start": c} for a, b, c in info]
    return select_orbit(orbit_records(rows))


def s1_validity_mask(im: ee.Image) -> ee.Image:
    """Mask VV and VH outside the A42 window (fill values, border noise) in one daily mosaic, so they enter neither
    the monthly median nor the observation count. Count follows VV: a VV-masked pixel is VH-masked too."""
    vv, vh = im.select("VV"), im.select("VH")
    ok_v = vv.gte(S1_DB_FLOOR["vv"]).And(vv.lte(S1_DB_CEIL))
    ok_h = vh.gte(S1_DB_FLOOR["vh"]).And(vh.lte(S1_DB_CEIL)).And(ok_v)
    return ee.Image.cat([vv.updateMask(ok_v), vh.updateMask(ok_h)]).copyProperties(im, ["system:time_start"])


def s1_month_image(geom, year: int, month: int, rel_orbit: int, direction: str) -> ee.Image:
    start = ee.Date.fromYMD(year, month, 1)
    col = (s1_collection(geom, contains=False)
           .filter(ee.Filter.eq("relativeOrbitNumber_start", rel_orbit))
           .filter(ee.Filter.eq("orbitProperties_pass", direction.upper())).select(["VV", "VH"]))
    days = _daily_mosaics(col, start, start.advance(1, "month"))
    days = days.map(s1_validity_mask)  # A42 per scene day, before median and count (review N3)
    med = days.median().unmask(NODATA)
    n = days.map(lambda im: im.select("VV").mask().rename("n")).sum().unmask(0)
    real = ee.Image.cat([med, n])
    empty = ee.Image.constant([NODATA, NODATA, 0]).rename(["VV", "VH", "n"])
    return ee.Image(ee.Algorithms.If(days.size().gt(0), real, empty))


def s1_year_image(geom, year: int, rel_orbit: int, direction: str) -> ee.Image:
    return ee.Image.cat([s1_month_image(geom, year, m, rel_orbit, direction).rename(
        [f"VV_{m:02d}", f"VH_{m:02d}", f"n_{m:02d}"]) for m in range(1, 13)])


def split_s1(arr: np.ndarray) -> dict:
    a = arr.reshape(12, S1_PER_MONTH, *arr.shape[1:])
    db = a[:, :2].copy()
    db[db <= NODATA + 1] = np.nan
    cnt = a[:, 2].astype(np.uint16)
    vv, vh, cnt, _, _ = mask_s1_db(db[:, 0], db[:, 1], cnt)  # fill values (about -50 dB) and impossible highs
    db[:, 0], db[:, 1] = vv, vh
    return {"db": db, "count": cnt}


# ----------------------------------------------------------------------------- store
EE_OFFSET_POLICY = ("none client-side: COPERNICUS/S2_SR_HARMONIZED already applies the processing-baseline offset "
                    "(pre-04.00 convention); floor 0")
ITEMS_NOT_KEPT_NOTE = ("not kept: Earth Engine stores aggregate server-side, so scene ids per month are not recorded; "
                       "the items_by_month attribute is the empty dict {}")


def build_site_ee(site_id, lon, lat, start: str, end: str, years_s2, years_s1, root, cfg=None,
                  orbit: tuple[int, str] | None = None, own_site_key: str | None = None,
                  context: bool = True, on_request=None):
    """Build one store: yearly computePixels requests for S2 and S1 (S1 on one fixed orbit)."""
    cfg = cfg or ChipConfig(bands=S2_STORE_BANDS)
    grid = chip_grid(lon, lat, cfg.size, cfg.res)
    geom = chip_geometry(grid)
    months = month_index(start, end)
    T, nb = len(months), len(S2_STORE_BANDS)
    H, W = grid.shape
    idx = {m: i for i, m in enumerate(months)}
    refl = np.full((T, nb, H, W), np.nan, np.float32)
    cnt = np.zeros((T, H, W), np.uint16)
    cnt_alt = np.zeros((T, H, W), np.uint16)
    cnt_csp = np.zeros((T, H, W), np.uint16)
    for y in years_s2:
        r = split_s2(fetch_array(s2_year_image(geom, y), grid))
        if on_request:
            on_request("s2", y)
        for mo in range(12):
            m = np.datetime64(f"{y}-{mo + 1:02d}", "M")
            if m in idx:
                i = idx[m]
                refl[i], cnt[i], cnt_alt[i], cnt_csp[i] = r["refl"][mo], r["count"][mo], r["count_alt"][mo], r["count_csp"][mo]
    vv = np.full((T, H, W), np.nan, np.float32)
    vh = np.full((T, H, W), np.nan, np.float32)
    c1 = np.zeros((T, H, W), np.uint16)
    n1 = np.zeros(T, np.int16)
    if orbit is None and years_s1:
        ch = choose_orbit(geom, f"{min(years_s1)}-01-01", f"{max(years_s1) + 1}-01-01")
        orbit = (ch.relative_orbit, ch.direction) if ch else None  # whole period, ties to the lower orbit (A41)
    if orbit is not None:
        for y in years_s1:
            r = split_s1(fetch_array(s1_year_image(geom, y, orbit[0], orbit[1]), grid))
            if on_request:
                on_request("s1", y)
            for mo in range(12):
                m = np.datetime64(f"{y}-{mo + 1:02d}", "M")
                if m in idx:
                    i = idx[m]
                    vv[i], vh[i], c1[i] = r["db"][mo, 0], r["db"][mo, 1], r["count"][mo]
                    n1[i] = int(c1[i].max())
    s2 = {"months": months, "refl": refl, "count": cnt, "count_alt": cnt_alt,
          "n_passes": np.zeros(T, np.int16), "n_used": cnt.reshape(T, -1).max(axis=1).astype(np.int16),
          "items_by_month": "{}", "baselines": "{}"}
    s1 = None
    if orbit is not None:
        s1 = {"months": months, "vv_db": vv, "vh_db": vh, "count": c1, "n_scenes": n1, "relative_orbit": int(orbit[0]),
              "direction": orbit[1], "orbit_candidates": "from catalogue property relativeOrbitNumber_start",
              "items_by_month": "{}", "speckle": "none", "pols": "vv,vh"}
    ds = build_dataset(site_id, grid, cfg, s2 if years_s2 else None, s1, start, end)
    if years_s2:
        ds["s2_clear_count_csp060"] = (("month", "y", "x"), cnt_csp)
    if context:  # registry-derived; the labelling queue stores leave it out
        from .regcontext import attr_value

        ds.attrs["other_registered_sites_in_chip"] = attr_value(grid, own_site_key)
    ds.attrs.update({
        "source": "earthengine",
        "s2_harmonised": "true: COPERNICUS/S2_SR_HARMONIZED, pre-04.00 convention, floor 0; no client-side offset",
        "s2_offset_policy": EE_OFFSET_POLICY,
        "s2_items_by_month_note": ITEMS_NOT_KEPT_NOTE,
        "s1_items_by_month_note": ITEMS_NOT_KEPT_NOTE,
        "s2_collection": "COPERNICUS/S2_SR_HARMONIZED; daily mosaics of tiles; Cloud Score+ cs_cdf >= 0.60 for the alternative count",
        "s2_clear_count_csp060": "count of days with cs_cdf >= 0.60 per pixel",
        "s2_n_passes_used_note": "per-month maximum of the per-pixel clear count (lower bound); s2_n_passes not recorded",
        "s1_collection": "COPERNICUS/S1_GRD IW VV+VH: sigma0 in dB, ellipsoid-based terrain correction (SRTM/ASTER), "
                         "NOT gamma0 terrain-flattened; one relativeOrbitNumber_start and direction per site",
        "s1_orbit_rule": "relative orbit chosen from the catalogue (most acquisition days among scenes containing the chip) and "
                         "enforced by filtering on relativeOrbitNumber_start and orbitProperties_pass",
    })
    write_site(ds, site_id, root)
    return ds
