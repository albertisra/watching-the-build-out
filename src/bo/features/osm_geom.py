"""Outlines of the public illustration sites from OpenStreetMap (ODbL, (c) OpenStreetMap contributors).

Used only to *evaluate* features and to measure contrasts and the point spread function on public sites
(``docs/research/signatures.md``). Outlines never enter a feature: features are computed from the chip alone.
One Overpass request for all ids in ``figures/sanity/public_basis.csv``, cached under ``data/raw/osm/``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from bo import paths

CACHE = paths.RAW / "osm" / "public_basis_geom.json"
PUBLIC_BASIS = paths.FIGURES / "sanity" / "public_basis.csv"


def fetch(basis: pd.DataFrame, cache: Path = CACHE) -> dict:
    if cache.exists():
        return json.loads(cache.read_text())
    ways = ",".join(str(int(i)) for i in basis.loc[basis.osm_type == "way", "osm_id"])
    rels = ",".join(str(int(i)) for i in basis.loc[basis.osm_type == "relation", "osm_id"])
    parts = (f"way(id:{ways});" if ways else "") + (f"relation(id:{rels});" if rels else "")
    q = f"[out:json][timeout:120];({parts});out geom;"
    resp = None
    for attempt in range(3):
        resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=180,
                             headers={"User-Agent": "research-imagery-pipeline/0.1"})
        if resp.status_code == 200:
            break
        time.sleep(30 * (attempt + 1))
    resp.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(resp.content)
    return resp.json()


def _element_polygon(el: dict):
    if el["type"] == "way":
        pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        return Polygon(pts) if len(pts) >= 4 else None
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in el.get("members", []) if m.get("type") == "way" and m.get("role") != "inner"
             and len(m.get("geometry", [])) >= 2]
    polys = list(polygonize(unary_union(lines)))
    return unary_union(polys) if polys else None


def public_outlines() -> pd.DataFrame:
    """pilot_id, subtype, geometry (WGS84 lon/lat shapely)."""
    basis = pd.read_csv(PUBLIC_BASIS)
    data = fetch(basis)
    geoms = {(el["type"], el["id"]): _element_polygon(el) for el in data["elements"]}
    rows = []
    for r in basis.itertuples():
        g = geoms.get((r.osm_type, int(r.osm_id)))
        rows.append({"pilot_id": r.pilot_id, "subtype": r.subtype, "geometry": g})
    return pd.DataFrame(rows)
