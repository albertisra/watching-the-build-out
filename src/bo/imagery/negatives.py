"""Negative sites: hard negatives from OpenStreetMap and stratified random points.

Hard negatives are non-PV, non-battery land cover that a detector could confuse with the
targets: greenhouses, industrial yards, large car parks, quarries and warehouse roofs.
OSM data: (c) OpenStreetMap contributors, ODbL 1.0 (docs/data_sources.md).

Overpass usage policy: a handful of requests, one at a time, with a pause, cached verbatim under
``data/raw/osm/``; nothing is refetched when the cache file exists.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree
from shapely.geometry import Point, Polygon

from bo import paths

OVERPASS = "https://overpass-api.de/api/interpreter"
OVERPASS_ENDPOINTS = (OVERPASS,)  # two other public endpoints did not answer on 2026-11-18
OSM_DIR = paths.RAW / "osm"
NE_ZIP = paths.RAW / "ne" / "ne_10m_admin_1_states_provinces.zip"
METRIC = 25832  # ETRS89 / UTM 32N: one metric CRS for all of Germany, distances good to < 1 percent
EXCLUDE_M = 2000.0
MIN_SEP_M = 3000.0

# category -> (Overpass filter, minimum area in m2). Areas are computed locally.
CATEGORIES: dict[str, tuple[str, float]] = {
    "greenhouse": ('way["landuse"="greenhouse_horticulture"]', 5_000),
    "industrial_yard": ('way["landuse"="industrial"]', 20_000),
    # capacity of at least 200 spaces keeps the Overpass answer small; the area is checked locally
    "car_park": ('way["amenity"="parking"]["capacity"~"^([2-9][0-9]{2}|[0-9]{4,})$"]', 10_000),
    "quarry": ('way["landuse"="quarry"]', 20_000),
    "warehouse_roof": ('way["building"="warehouse"]', 5_000),
}
PER_CATEGORY = 10
N_RANDOM = 50
CELL_DEG = (0.35, 0.22)  # lon, lat extent of one Overpass cell (about 26 x 24 km)
N_CELLS = 8


def german_states() -> gpd.GeoDataFrame:
    g = gpd.read_file(f"zip://{NE_ZIP}")
    g = g[g.admin == "Germany"][["name", "geometry"]].rename(columns={"name": "bundesland"})
    return g.reset_index(drop=True)


def exclusion_tree(points_lonlat: np.ndarray) -> cKDTree:
    gs = gpd.GeoSeries([Point(x, y) for x, y in points_lonlat], crs=4326).to_crs(METRIC)
    return cKDTree(np.array([[p.x, p.y] for p in gs]))


def far_enough(xy: np.ndarray, tree: cKDTree, dist: float = EXCLUDE_M) -> np.ndarray:
    d, _ = tree.query(xy, k=1)
    return d >= dist


def random_cells(states: gpd.GeoDataFrame, rng: np.random.Generator, n: int) -> list[tuple]:
    """n bounding boxes (south, west, north, east) whose centres lie inside Germany."""
    land = states.geometry.union_all()
    cells = []
    minx, miny, maxx, maxy = land.bounds
    while len(cells) < n:
        x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
        if land.contains(Point(x, y)):
            cells.append((y - CELL_DEG[1] / 2, x - CELL_DEG[0] / 2, y + CELL_DEG[1] / 2,
                          x + CELL_DEG[0] / 2))
    return cells


def overpass_query(filt: str, cells: list[tuple]) -> str:
    parts = "".join(f"{filt}({s:.4f},{w:.4f},{n:.4f},{e:.4f});" for s, w, n, e in cells)
    return f"[out:json][timeout:280];({parts});out geom tags qt;"


def fetch_chunked(category: str, filt: str, cells: list[tuple], per_request: int = 2,
                  force: bool = False) -> dict:
    """The full 8-cell answer if cached, else ``per_request`` cells per Overpass request."""
    full = OSM_DIR / f"hard_negatives_{category}.json"
    if full.exists() and not force:
        return json.loads(full.read_text())
    elements = []
    for i in range(0, len(cells), per_request):
        part = cells[i : i + per_request]
        d = fetch(f"{category}_part{i // per_request}", overpass_query(filt, part), force)
        elements += d.get("elements", [])
    return {"elements": elements}


def fetch(category: str, query: str, force: bool = False) -> dict:
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    f = OSM_DIR / f"hard_negatives_{category}.json"
    if f.exists() and not force:
        return json.loads(f.read_text())
    last = None
    for attempt in range(4):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            r = requests.post(endpoint, data={"data": query}, timeout=300,
                              headers={"User-Agent": "research-imagery-pipeline/0.1"})
            if r.status_code == 200:
                f.write_bytes(r.content)
                time.sleep(15)  # one request at a time, with a pause (Overpass usage policy)
                return r.json()
            last = f"{endpoint}: HTTP {r.status_code}"
        except requests.RequestException as e:
            last = f"{endpoint}: {e}"
        time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"Overpass failed for {category}: {last}")


def ways_to_frame(data: dict, category: str) -> gpd.GeoDataFrame:
    rows = []
    for el in data.get("elements", []):
        geom = el.get("geometry")
        if el.get("type") != "way" or not geom or len(geom) < 4:
            continue
        pts = [(p["lon"], p["lat"]) for p in geom]
        if pts[0] != pts[-1]:
            continue
        poly = Polygon(pts)
        if not poly.is_valid or poly.is_empty:
            continue
        rows.append({"osm_type": "way", "osm_id": el["id"], "category": category, "geometry": poly})
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs=4326)
    if g.empty:
        return g
    g["area_m2"] = g.to_crs(METRIC).area
    g["geometry"] = g.geometry.representative_point()
    return g


def pick_hard(frames: dict[str, gpd.GeoDataFrame], excl: cKDTree, states: gpd.GeoDataFrame,
              seed: int, n_total: int = 50) -> pd.DataFrame:
    """Up to ``PER_CATEGORY`` per category, then round-robin top-up from the categories that still
    have candidates until ``n_total`` (a category such as large car parks can be short)."""
    rng = np.random.default_rng(seed)
    pools: dict[str, list[dict]] = {}
    for cat, (_, min_area) in CATEGORIES.items():
        g = frames[cat]
        g = g[g.area_m2 >= min_area].copy()
        if len(g):
            gm = g.to_crs(METRIC)
            xy = np.array([[p.x, p.y] for p in gm.geometry])
            ok = far_enough(xy, excl)
            g, xy = g[ok], xy[ok]
        else:
            xy = np.empty((0, 2))
        pools[cat] = [
            {"lat": g.iloc[i].geometry.y, "lon": g.iloc[i].geometry.x, "kind": "hard",
             "category": cat, "osm_type": g.iloc[i].osm_type, "osm_id": int(g.iloc[i].osm_id),
             "area_m2": float(g.iloc[i].area_m2), "_xy": tuple(xy[i])}
            for i in rng.permutation(len(g))
        ]
    chosen: list[dict] = []
    counts = dict.fromkeys(CATEGORIES, 0)

    def take(cat: str) -> bool:
        pool = pools[cat]
        while pool:
            c = pool.pop(0)
            if any(np.hypot(c["_xy"][0] - r["_xy"][0], c["_xy"][1] - r["_xy"][1]) < MIN_SEP_M
                   for r in chosen):
                continue
            chosen.append(c)
            counts[cat] += 1
            return True
        return False

    for cat in CATEGORIES:
        while counts[cat] < PER_CATEGORY and take(cat):
            pass
    progress = True
    while len(chosen) < n_total and progress:
        progress = False
        for cat in CATEGORIES:
            if len(chosen) < n_total and take(cat):
                progress = True
    df = pd.DataFrame(chosen)
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    df["bundesland"] = gpd.sjoin(pts, states, how="left", predicate="within")["bundesland"].values
    return df


def allocate_by_state(states: gpd.GeoDataFrame, n_total: int, min_each: int = 2) -> dict[str, int]:
    """At least ``min_each`` per state, the rest proportional to area (largest remainder)."""
    area = states.to_crs(METRIC).area.values
    rest = n_total - min_each * len(states)
    raw = rest * area / area.sum()
    base = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - base))[: rest - base.sum()]:
        base[i] += 1
    return dict(zip(states.bundesland, (base + min_each).tolist(), strict=True))


def pick_random(states: gpd.GeoDataFrame, excl: cKDTree, taken_xy: list[tuple[float, float]],
                seed: int, n_total: int = N_RANDOM) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    alloc = allocate_by_state(states, n_total)
    rows = []
    xy_taken = list(taken_xy)
    sm = states.to_crs(METRIC)
    for name, geom_m, geom_ll in zip(states.bundesland, sm.geometry, states.geometry, strict=True):
        minx, miny, maxx, maxy = geom_m.bounds
        got = 0
        for _ in range(20000):
            x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
            if not geom_m.contains(Point(x, y)):
                continue
            if excl.query([x, y])[0] < EXCLUDE_M:
                continue
            if any(np.hypot(x - a, y - b) < MIN_SEP_M for a, b in xy_taken):
                continue
            ll = gpd.GeoSeries([Point(x, y)], crs=METRIC).to_crs(4326).iloc[0]
            rows.append({"lat": ll.y, "lon": ll.x, "kind": "random", "category": "random",
                         "bundesland": name})
            xy_taken.append((x, y))
            got += 1
            if got == alloc[name]:
                break
    return pd.DataFrame(rows)


def build_negatives(pilot: Path, units: Path, out: Path, seed: int = paths.SEED,
                    force_fetch: bool = False) -> pd.DataFrame:
    states = german_states()
    p = pd.read_parquet(pilot)[["lat", "lon"]]
    u = pd.read_parquet(units)[["lat", "lon"]].dropna()
    pts = pd.concat([p, u]).drop_duplicates().to_numpy()[:, ::-1]  # (lon, lat)
    excl = exclusion_tree(pts)
    rng = np.random.default_rng(seed)
    cells = random_cells(states, rng, N_CELLS)
    frames = {}
    for cat, (filt, _) in CATEGORIES.items():
        frames[cat] = ways_to_frame(fetch_chunked(cat, filt, cells, force=force_fetch), cat)
    hard = pick_hard(frames, excl, states, seed)
    rnd = pick_random(states, excl, list(hard["_xy"]), seed)
    hard = hard.drop(columns="_xy")
    df = pd.concat([hard, rnd], ignore_index=True)
    df.insert(0, "neg_id", [f"N{i:03d}" for i in range(len(df))])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    return df


def top_up_random(neg_in: Path, pilot: Path, units: Path, out: Path, n_total: int = 100,
                  seed: int = paths.SEED) -> pd.DataFrame:
    """Add random negatives to ``neg_in`` until ``n_total``, same 2 km and 3 km rules.

    Exclusion points: pilot sites and registry units with ``coord_state == 'ok'``. New points go
    to the federal states with the fewest random negatives so far.
    """
    states = german_states()
    df = pd.read_parquet(neg_in)
    p = pd.read_parquet(pilot)[["lat", "lon"]]
    u = pd.read_parquet(units)
    u = u[u.coord_state == "ok"][["lat", "lon"]].dropna()
    excl = exclusion_tree(pd.concat([p, u]).drop_duplicates().to_numpy()[:, ::-1])
    gs = gpd.GeoSeries(gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(METRIC)
    taken = [(q.x, q.y) for q in gs]
    rng = np.random.default_rng(seed + 2)
    rows = []
    start = int(df.neg_id.str[1:].astype(int).max()) + 1
    while len(df) + len(rows) < n_total:
        cnt = df[df.kind == "random"].bundesland.value_counts().reindex(states.bundesland).fillna(0)
        cnt = cnt + pd.Series([r["bundesland"] for r in rows]).value_counts().reindex(
            states.bundesland).fillna(0)
        name = cnt.idxmin()
        geom = states[states.bundesland == name].to_crs(METRIC).geometry.iloc[0]
        minx, miny, maxx, maxy = geom.bounds
        for _ in range(20000):
            x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
            if (geom.contains(Point(x, y)) and excl.query([x, y])[0] >= EXCLUDE_M
                    and all(np.hypot(x - a, y - b) >= MIN_SEP_M for a, b in taken)):
                ll = gpd.GeoSeries([Point(x, y)], crs=METRIC).to_crs(4326).iloc[0]
                rows.append({"neg_id": f"N{start + len(rows):03d}", "lat": ll.y, "lon": ll.x,
                             "kind": "random", "category": "random", "bundesland": name,
                             "nearest_unit_m": float(excl.query([x, y])[0])})
                taken.append((x, y))
                break
    out_df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out)
    return out_df
