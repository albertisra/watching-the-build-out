"""OpenStreetMap features for comparison with the registry (ODbL data, kept in separate files).

Fetches, per bounding box via the Overpass API:

* ``power=plant`` with ``plant:source`` containing solar or battery,
* ``power=generator`` with ``generator:source`` containing solar or battery,
* ``power=substation`` as *context only* (coarse prior; never combined with grid topology).

Usage policy (https://wiki.openstreetmap.org/wiki/Overpass_API): one request per bounding box,
sequential, with a delay between requests, the response is cached under ``data/raw/osm/`` and
never fetched again for the same query. No scheduled or parallel use.

A full-Germany run is deliberately not wired to a default command. ``germany_tiles`` lists the
tiles and ``fetch_tiles`` runs them one after another; the author starts that run by hand
(``python -m bo.data.osm_features --germany``). A Geofabrik ``germany-latest.osm.pbf`` extract
is the alternative (one download, no API load); it needs an OSM reader that is not a dependency yet.

Output files carry OpenStreetMap data and fall under the ODbL: attribution
"© OpenStreetMap contributors" (https://www.openstreetmap.org/copyright). They are written
to ``data/processed/registry/osm/`` and must not be merged into the MaStR tables.

All quantities are observed (crowd-sourced map data, not registry data).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

from bo import paths
from bo.data.registry_sites import project

OSM_RAW = paths.RAW / "osm"
OSM_OUT = paths.PROCESSED / "registry" / "osm"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "bo-registry-research/0.1 (academic research, single cached requests)"
DELAY_S = 30.0  # between tiles in a multi-tile run
ATTRIBUTION = "© OpenStreetMap contributors (ODbL 1.0), https://www.openstreetmap.org/copyright"

# Small test box: a large solar park area in Brandenburg, about 8 km by 8 km.
TEST_BBOX = (51.90, 14.35, 51.97, 14.45)  # south, west, north, east


def build_query(bbox: tuple[float, float, float, float], timeout_s: int = 90) -> str:
    s, w, n, e = bbox
    box = f"({s},{w},{n},{e})"
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        "(\n"
        f'  nwr["power"="plant"]["plant:source"~"solar|battery"]{box};\n'
        f'  nwr["power"="generator"]["generator:source"~"solar|battery"]{box};\n'
        f'  nwr["power"="substation"]{box};\n'
        ");\nout center tags;\n"
    )


def cache_path(query: str, folder: Path = OSM_RAW) -> Path:
    return folder / f"overpass_{hashlib.sha1(query.encode()).hexdigest()[:16]}.json"


def fetch(query: str, folder: Path = OSM_RAW, session=None) -> tuple[dict, bool]:
    """Return ``(response_json, from_cache)``. A cached response is never re-requested."""
    path = cache_path(query, folder)
    if path.exists():
        return json.loads(path.read_text()), True
    folder.mkdir(parents=True, exist_ok=True)
    sess = session or requests
    resp = sess.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    path.write_text(json.dumps(data))
    return data, False


def _source_class(tags: dict) -> str | None:
    val = tags.get("plant:source") or tags.get("generator:source") or ""
    found = {part.strip().lower() for part in val.split(";")} & {"solar", "battery"}
    if "battery" in found and "solar" in found:
        return "solar;battery"
    return next(iter(found), None)


def parse_elements(response: dict) -> gpd.GeoDataFrame:
    """Turn an Overpass response into a point GeoDataFrame (centre for areas).

    Columns: osm_type, osm_id, power, category (solar, battery, substation_context), source,
    output, storage, plant_type, substation, voltage_class. Names and operators are not kept.
    """
    rows = []
    for el in response.get("elements", []):
        tags = el.get("tags", {})
        centre = el if el.get("type") == "node" else el.get("center", {})
        if "lat" not in centre or "lon" not in centre:
            continue
        power = tags.get("power")
        if power == "substation":
            category, source = "substation_context", None
        else:
            source = _source_class(tags)
            if source is None:
                continue
            category = "battery" if "battery" in source else "solar"
        rows.append({
            "osm_type": el.get("type"),
            "osm_id": el.get("id"),
            "power": power,
            "category": category,
            "source": source,
            "output": tags.get("plant:output:electricity") or tags.get("generator:output:electricity"),
            "storage": tags.get("plant:storage") or tags.get("generator:storage"),
            "plant_type": tags.get("plant:type") or tags.get("generator:type"),
            "substation": tags.get("substation"),
            "lat": centre["lat"],
            "lon": centre["lon"],
        })
    df = pd.DataFrame(rows, columns=[
        "osm_type", "osm_id", "power", "category", "source", "output", "storage", "plant_type",
        "substation", "lat", "lon"])
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")


def germany_tiles(step_deg: float = 0.5) -> list[tuple[float, float, float, float]]:
    """Tiles covering a Germany bounding box. Not fetched by default."""
    south, north, west, east = 47.2, 55.1, 5.8, 15.1
    lats = np.arange(south, north, step_deg)
    lons = np.arange(west, east, step_deg)
    return [(round(a, 3), round(b, 3), round(min(a + step_deg, north), 3), round(min(b + step_deg, east), 3))
            for a in lats for b in lons]


def fetch_tiles(tiles, folder: Path = OSM_RAW, delay_s: float = DELAY_S) -> gpd.GeoDataFrame:
    """Sequential fetch with a delay after each uncached request."""
    parts = []
    for tile in tiles:
        data, cached = fetch(build_query(tile), folder)
        parts.append(parse_elements(data))
        if not cached:
            time.sleep(delay_s)
    gdf = pd.concat(parts, ignore_index=True) if parts else parse_elements({})
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326").drop_duplicates(["osm_type", "osm_id"])


def match_to_sites(sites: pd.DataFrame, osm: pd.DataFrame, max_distance_m: float = 500.0) -> pd.DataFrame:
    """Nearest OSM generator or plant of the same technology per registry site (comparison only).

    ``sites`` needs ``site_id``, ``technology``, ``lat``, ``lon``. Returns ``site_id``,
    ``osm_match`` (bool) and ``osm_distance_m``. Substations are never matched.
    """
    out = sites[["site_id"]].copy()
    out["osm_match"] = False
    out["osm_distance_m"] = np.nan
    for tech, cat in (("battery", "battery"), ("ground_pv", "solar")):
        s = sites[(sites["technology"] == tech) & sites["lat"].notna()]
        o = osm[osm["category"].str.contains(cat, na=False)] if len(osm) else osm
        if s.empty or len(o) == 0:
            continue
        dist, _ = cKDTree(project(o["lat"], o["lon"])).query(project(s["lat"], s["lon"]))
        out.loc[s.index, "osm_distance_m"] = dist
        out.loc[s.index, "osm_match"] = dist <= max_distance_m
    return out


def main(argv: list[str]) -> None:
    if "--germany" in argv:
        gdf = fetch_tiles(germany_tiles())
        name = "osm_features_germany.parquet"
    else:
        data, cached = fetch(build_query(TEST_BBOX))
        gdf = parse_elements(data)
        name = "osm_features_testbox.parquet"
        print(f"test box, from_cache={cached}")
    OSM_OUT.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(OSM_OUT / name, index=False)
    print(gdf.groupby("category").size().to_string())
    print(ATTRIBUTION)


if __name__ == "__main__":
    main(sys.argv)
