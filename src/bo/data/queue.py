"""First-round labelling queue (Phase 3, task 3.4).

Builds ``data/processed/labels/queue_round1.parquet``: registry positives, the pilot v1 sites,
hard negatives from OpenStreetMap (national Geofabrik extract) and random negatives stratified by
ESA WorldCover land cover. The queue holds only the columns the labelling app may see; every
registry-derived stratification field lives in ``queue_round1_strata.parquet`` next to it, which
the app never reads (circularity guard, KICKOFF 3.x). Coordinates stay under ``data/``.
The summary in ``results/labels/`` has counts only, no coordinates.

Design choices are recorded as assumptions A55 to A63 in ``docs/assumptions.md``.

Quantity types: registry attributes are observed; OSM and WorldCover attributes are observed map
data. Nothing here is detected or modelled.
"""

from __future__ import annotations

import argparse
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

from bo import paths

METRIC = 25832  # ETRS89 / UTM 32N, one metric CRS for Germany (distance error below 1 percent)
LABELS_DIR = paths.PROCESSED / "labels"
QUEUE = LABELS_DIR / "queue_round1.parquet"
STRATA = LABELS_DIR / "queue_round1_strata.parquet"
HARD_CANDIDATES = LABELS_DIR / "osm_hard_negative_candidates.parquet"
SUMMARY = paths.RESULTS / "labels" / "queue_round1_summary.csv"
SITES = paths.PROCESSED / "registry" / "registry_sites.parquet"
UNITS = paths.PROCESSED / "registry" / "units_ge_threshold.parquet"
PILOT = paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet"
PBF = paths.RAW / "osm" / "geofabrik" / "germany-latest.osm.pbf"
NE_ZIP = paths.RAW / "ne" / "ne_10m_admin_1_states_provinces.zip"
PBF_URL = "https://download.geofabrik.de/europe/germany-latest.osm.pbf"
PBF_MAX_BYTES = 5 * 1024**3  # stop above 5 GB (brief)

# Columns the labelling app may read. Nothing else leaves this module in the queue file.
QUEUE_COLUMNS = ["queue_id", "site_id", "stratum", "lat", "lon", "bundesland", "landkreis",
                 "osm_category", "worldcover_class"]
STRATA_OF_QUEUE = ["positive_battery", "positive_pv", "hard_negative", "random_negative", "pilot"]

# Design parameters (assumptions A55 to A63).
N_POS = {"battery": 120, "ground_pv": 120}
SIZE_BINS_KW = [1_000, 5_000, 20_000, 100_000, math.inf]
SIZE_LABELS = ["1-5 MW", "5-20 MW", "20-100 MW", ">=100 MW"]
PERIODS = ["before_2019", "2019_2022", "2023_2024", "2025_2026", "planned"]
PERIOD_WEIGHT = {"before_2019": 0.15, "2019_2022": 0.20, "2023_2024": 0.25, "2025_2026": 0.25,
                 "planned": 0.15}
SIZE_WEIGHT = dict.fromkeys(SIZE_LABELS, 0.25)
COLOCATED_SHARE = 0.25
POS_MIN_SEP_M = 1_000.0
NEG_MIN_DIST_M = 2_000.0
N_HARD = 60
HARD_CATEGORIES = ["greenhouse", "industrial_yard", "car_park", "quarry", "warehouse_roof"]
HARD_MIN_AREA_M2 = {"greenhouse": 5_000, "industrial_yard": 20_000, "car_park": 10_000,
                    "quarry": 20_000, "warehouse_roof": 5_000}
N_RANDOM = 60
WORLDCOVER_CLASSES = {10: "tree_cover", 20: "shrubland", 30: "grassland", 40: "cropland",
                      50: "built_up", 60: "bare_sparse_vegetation", 70: "snow_ice",
                      80: "water", 90: "herbaceous_wetland", 95: "mangroves", 100: "moss_lichen"}
# Target per class; classes with too few candidate points hand their remainder to cropland and
# grassland (the land the targets sit on).
WORLDCOVER_TARGET = {"cropland": 16, "grassland": 12, "tree_cover": 12, "built_up": 10,
                     "bare_sparse_vegetation": 3, "water": 3, "shrubland": 2,
                     "herbaceous_wetland": 2}
WORLDCOVER_FALLBACK = ["cropland", "grassland", "tree_cover"]
WORLDCOVER_YEAR = "2021"  # ESA WorldCover v200
N_CANDIDATE_POINTS = 4000
STATE_GROUPS = {
    "Nord": ["Schleswig-Holstein", "Hamburg", "Bremen", "Niedersachsen", "Mecklenburg-Vorpommern"],
    "Ost": ["Brandenburg", "Berlin", "Sachsen", "Sachsen-Anhalt", "Thüringen"],
    "West": ["Nordrhein-Westfalen", "Hessen", "Rheinland-Pfalz", "Saarland"],
    "Sued": ["Bayern", "Baden-Württemberg"],
}


# ----------------------------------------------------------------------------- geometry helpers


def to_xy(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Project WGS84 to ETRS89 / UTM 32N metres, shape (n, 2)."""
    g = gpd.GeoSeries(gpd.points_from_xy(np.asarray(lon), np.asarray(lat)), crs=4326).to_crs(METRIC)
    return np.column_stack([g.x.to_numpy(), g.y.to_numpy()])


def min_dist(xy: np.ndarray, ref_xy: np.ndarray) -> np.ndarray:
    """Distance in metres from each row of ``xy`` to the nearest row of ``ref_xy``."""
    if len(ref_xy) == 0:
        return np.full(len(xy), np.inf)
    d, _ = cKDTree(ref_xy).query(xy, k=1)
    return d


def german_states() -> gpd.GeoDataFrame:
    g = gpd.read_file(f"zip://{NE_ZIP}")
    g = g[g.admin == "Germany"][["name", "geometry"]].rename(columns={"name": "bundesland"})
    return g.reset_index(drop=True)


# ----------------------------------------------------------------------------- positives


def period_of(status: str, commissioning: pd.Timestamp) -> str | None:
    """Stratification period from registry status and first commissioning date."""
    if status == "In Planung":
        return "planned"
    if status != "In Betrieb" or pd.isna(commissioning):
        return None
    y = commissioning.year
    if y < 2019:
        return "before_2019"
    if y <= 2022:
        return "2019_2022"
    if y <= 2024:
        return "2023_2024"
    return "2025_2026"


def positive_pool(sites: pd.DataFrame, exclude_site_ids: set[str] | None = None,
                  states: gpd.GeoDataFrame | None = None) -> pd.DataFrame:
    """Eligible registry sites with their stratification fields (all ``reg_`` prefixed)."""
    s = sites[sites["coord_state"] == "ok"].copy()
    s = s[~s["site_id"].isin(exclude_site_ids or set())]
    if states is not None and s["bundesland"].isna().any():  # fill from the coordinate
        s["bundesland"] = s["bundesland"].fillna(assign_states(s, states))
    s = s[s["bundesland"].notna()]
    s = s[~s["flag_coord_rounded_any"].astype(bool)]
    s = s[~s["reg_flag_commissioning_placeholder_any"].astype(bool)]
    s = s[~s["reg_flag_commissioning_before_1990_any"].astype(bool)]
    s["reg_period"] = [
        period_of(st, c) for st, c in zip(s["reg_status"], s["reg_commissioning_date_first"],
                                          strict=True)
    ]
    s = s[s["reg_period"].notna()]
    s["reg_size_class"] = pd.cut(s["power_kw"], bins=SIZE_BINS_KW, labels=SIZE_LABELS,
                                 right=False).astype(object)
    s = s[s["reg_size_class"].notna()]
    s["reg_colocated"] = np.where(s["technology"] == "battery", s["colocated_pv"],
                                  s["colocated_bess"]).astype(bool)
    return s.reset_index(drop=True)


def allocate_cells(avail: dict[tuple[str, str], int], n: int,
                   weights: dict[tuple[str, str], float]) -> dict[tuple[str, str], int]:
    """Split ``n`` over cells by weight, capped by availability, remainder re-spread.

    Water-filling: cells that hit their cap keep it, the rest share what is left by weight, with
    largest-remainder rounding. If total availability is below ``n``, all cells are exhausted.
    """
    quota = dict.fromkeys(avail, 0)
    remaining = min(n, sum(avail.values()))
    open_cells = {c for c in avail if avail[c] > 0 and weights[c] > 0}
    while remaining > 0 and open_cells:
        wsum = sum(weights[c] for c in open_cells)
        raw = {c: remaining * weights[c] / wsum for c in open_cells}
        base = {c: min(math.floor(raw[c]), avail[c] - quota[c]) for c in open_cells}
        given = sum(base.values())
        # largest remainders get one more each, within caps
        order = sorted(open_cells, key=lambda c: (-(raw[c] - math.floor(raw[c])), str(c)))
        extra = remaining - given
        for c in order:
            if extra <= 0:
                break
            if base[c] < avail[c] - quota[c] and base[c] == math.floor(raw[c]):
                base[c] += 1
                extra -= 1
        for c in open_cells:
            quota[c] += base[c]
        remaining -= sum(base.values())
        open_cells = {c for c in open_cells if quota[c] < avail[c]}
        if sum(base.values()) == 0:
            break
    return quota


def select_positives(pool: pd.DataFrame, n: int, rng: np.random.Generator,
                     fixed_xy: np.ndarray, min_sep_m: float = POS_MIN_SEP_M,
                     colocated_share: float = COLOCATED_SHARE) -> pd.DataFrame:
    """Pick ``n`` sites of one technology, stratified by size class x period, spread over states.

    1. Cell quotas from ``allocate_cells`` (size weights x period weights, capped by availability).
    2. Every state with eligible sites receives one pick first (smallest state first).
    3. Remaining picks fill the cells; within a cell the state furthest below its target
       (target proportional to the square root of the state's eligible sites) goes first, and
       co-located sites are preferred until ``colocated_share`` is reached.
    Every pick keeps ``min_sep_m`` to all earlier picks and to ``fixed_xy`` (e.g. pilot sites).
    """
    pool = pool.reset_index(drop=True).copy()
    pool[["_x", "_y"]] = to_xy(pool["lat"].to_numpy(), pool["lon"].to_numpy())
    cells = sorted({(a, b) for a, b in zip(pool["reg_size_class"], pool["reg_period"],
                                           strict=True)})
    avail = {c: int(((pool["reg_size_class"] == c[0]) & (pool["reg_period"] == c[1])).sum())
             for c in cells}
    weights = {c: SIZE_WEIGHT[c[0]] * PERIOD_WEIGHT[c[1]] for c in cells}
    quota = allocate_cells(avail, n, weights)

    state_avail = pool["bundesland"].value_counts()
    root = np.sqrt(state_avail.astype(float))
    target = n * root / root.sum()
    picks_state: dict[str, int] = dict.fromkeys(state_avail.index, 0)
    chosen_xy = [tuple(p) for p in np.asarray(fixed_xy).reshape(-1, 2)]
    chosen_idx: list[int] = []
    n_col = 0

    def free(i: int) -> bool:
        x, y = pool.at[i, "_x"], pool.at[i, "_y"]
        return all(math.hypot(x - a, y - b) >= min_sep_m for a, b in chosen_xy)

    def take(i: int, cell: tuple[str, str]) -> None:
        nonlocal n_col
        chosen_idx.append(i)
        chosen_xy.append((pool.at[i, "_x"], pool.at[i, "_y"]))
        picks_state[pool.at[i, "bundesland"]] += 1
        n_col += int(pool.at[i, "reg_colocated"])
        if quota.get(cell, 0) > 0:
            quota[cell] -= 1

    def candidates(cell: tuple[str, str], state: str | None = None) -> list[int]:
        m = ((pool["reg_size_class"] == cell[0]) & (pool["reg_period"] == cell[1])
             & ~pool.index.isin(chosen_idx))
        if state is not None:
            m &= pool["bundesland"] == state
        idx = np.array(pool.index[m])
        return [int(i) for i in rng.permutation(idx)]

    # step 2: state presence, smallest pool first
    for st in sorted(state_avail.index, key=lambda s: (state_avail[s], s)):
        if len(chosen_idx) >= n:
            break
        for cell in sorted(cells, key=lambda c: -quota[c]):
            if quota[cell] <= 0:
                continue
            hit = next((i for i in candidates(cell, st) if free(i)), None)
            if hit is not None:
                take(hit, cell)
                break

    # step 3: fill the cells in round-robin order so no cell is served last
    while len(chosen_idx) < n and any(q > 0 for q in quota.values()):
        progressed = False
        for cell in sorted(cells, key=lambda c: -quota[c]):
            if quota[cell] <= 0 or len(chosen_idx) >= n:
                continue
            cand = [i for i in candidates(cell) if free(i)]
            if not cand:
                quota[cell] = 0  # exhausted by the separation rule; redistributed below
                continue
            want_col = n_col < colocated_share * (len(chosen_idx) + 1)
            if want_col and any(pool.at[i, "reg_colocated"] for i in cand):
                cand = [i for i in cand if pool.at[i, "reg_colocated"]]
            cand.sort(key=lambda i: picks_state[pool.at[i, "bundesland"]]
                      / max(target[pool.at[i, "bundesland"]], 1e-9))
            take(cand[0], cell)
            progressed = True
        if not progressed:
            break

    # shortfall (separation exhausted cells): fill from any cell, nearest to its weight
    if len(chosen_idx) < n:
        rest = [i for i in rng.permutation(np.array(pool.index.difference(chosen_idx)))
                if free(int(i))]
        for i in rest:
            if len(chosen_idx) >= n:
                break
            if free(int(i)):
                take(int(i), (pool.at[i, "reg_size_class"], pool.at[i, "reg_period"]))
    return pool.loc[chosen_idx].drop(columns=["_x", "_y"]).reset_index(drop=True)


# ----------------------------------------------------------------------------- hard negatives


def pbf_size_ok(url: str = PBF_URL) -> int:
    """Size in bytes from the HTTP header; raises above 5 GB."""
    import requests

    r = requests.head(url, allow_redirects=True, timeout=60)
    size = int(r.headers["Content-Length"])
    if size > PBF_MAX_BYTES:
        raise RuntimeError(f"Geofabrik extract is {size / 1e9:.2f} GB, above the 5 GB limit")
    return size


# OSM tag per category, and the share of ways kept (deterministic by way id modulo, to bound
# memory for the very frequent classes; the draw stays random with respect to location).
OSM_TAGS = {"greenhouse": ("landuse", "greenhouse_horticulture"),
            "industrial_yard": ("landuse", "industrial"), "car_park": ("amenity", "parking"),
            "quarry": ("landuse", "quarry"), "warehouse_roof": ("building", "warehouse")}
OSM_KEEP_MODULO = {"greenhouse": 1, "industrial_yard": 2, "car_park": 3, "quarry": 1,
                   "warehouse_roof": 5}


def extract_hard_candidates(pbf: Path = PBF, out: Path = HARD_CANDIDATES) -> pd.DataFrame:
    """Two streaming passes over the Germany extract: closed ways of the five confuser classes.

    Pass 1 reads ways only and keeps closed ways with one of the tags (``OSM_KEEP_MODULO`` thins
    the frequent classes by way id). Pass 2 reads only the nodes those ways use. Multipolygon
    relations are not read (large quarries and industrial areas mapped as relations are missing,
    stated in the data card of the queue). Each polygon is reduced to one representative point.
    Output (ODbL derived database, data/processed/labels): osm_id, osm_category, area_m2, lat, lon.
    """
    import osmium
    from shapely.geometry import Polygon

    tag_to_cat = {v: k for k, v in OSM_TAGS.items()}
    flt = osmium.filter.TagFilter(*OSM_TAGS.values())
    ways: dict[int, tuple[str, list[int]]] = {}
    for w in osmium.FileProcessor(str(pbf), osmium.osm.WAY).with_filter(flt):
        if not w.is_closed() or len(w.nodes) < 4:
            continue
        cat = next((tag_to_cat[(k, v)] for k, v in ((t.k, t.v) for t in w.tags)
                    if (k, v) in tag_to_cat), None)
        if cat is None or w.id % OSM_KEEP_MODULO[cat] != 0:
            continue
        ways[w.id] = (cat, [n.ref for n in w.nodes])
    ids = {r for _, refs in ways.values() for r in refs}
    coords: dict[int, tuple[float, float]] = {}
    for n in osmium.FileProcessor(str(pbf), osmium.osm.NODE).with_filter(
            osmium.filter.IdFilter(ids)):
        coords[n.id] = (n.location.lon, n.location.lat)
    rows = []
    for wid, (cat, refs) in ways.items():
        if any(r not in coords for r in refs):
            continue
        poly = Polygon([coords[r] for r in refs])
        if not poly.is_valid or poly.is_empty:
            continue
        pt = poly.representative_point()
        rows.append({"osm_id": f"way/{wid}", "osm_category": cat, "lat": pt.y, "lon": pt.x,
                     "_poly": poly})
    g = gpd.GeoDataFrame(rows, geometry="_poly", crs=4326)
    g["area_m2"] = g.geometry.to_crs(METRIC).area
    g = g[g["area_m2"] >= g["osm_category"].map(HARD_MIN_AREA_M2)]
    df = pd.DataFrame(g[["osm_id", "osm_category", "area_m2", "lat", "lon"]])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


HARD_CATEGORIES_ORDER = ["greenhouse", "industrial_yard", "car_park", "quarry", "warehouse_roof"]


def assign_states(df: pd.DataFrame, states: gpd.GeoDataFrame) -> pd.Series:
    pts = gpd.GeoDataFrame(df[["lat", "lon"]].copy(),
                           geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    j = gpd.sjoin(pts, states, how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j["bundesland"].reindex(df.index)


def pick_hard(cands: pd.DataFrame, n: int, rng: np.random.Generator, forbid_xy: np.ndarray,
              min_dist_m: float = NEG_MIN_DIST_M, min_sep_m: float = NEG_MIN_DIST_M,
              per_category: int | None = None) -> pd.DataFrame:
    """Equal draw per category, spread over states (state with fewest picks first).

    ``forbid_xy`` are units and queue positives; every pick is at least ``min_dist_m`` from them
    and ``min_sep_m`` from earlier negatives. ``cands`` needs lat, lon, osm_category, bundesland.
    """
    cands = cands.reset_index(drop=True).copy()
    cands[["_x", "_y"]] = to_xy(cands["lat"].to_numpy(), cands["lon"].to_numpy())
    cands = cands[min_dist(cands[["_x", "_y"]].to_numpy(), forbid_xy) >= min_dist_m]
    cands = cands.iloc[rng.permutation(len(cands))].reset_index(drop=True)
    cats = [c for c in HARD_CATEGORIES if (cands["osm_category"] == c).any()]
    per = per_category or math.ceil(n / max(len(cats), 1))
    picks: list[int] = []
    xy: list[tuple[float, float]] = []
    state_n: dict[str, int] = {}
    count = dict.fromkeys(cats, 0)

    def take_one(cat: str) -> bool:
        sub = cands[(cands["osm_category"] == cat) & ~cands.index.isin(picks)]
        if sub.empty:
            return False
        order = sorted(sub.index, key=lambda i: state_n.get(str(cands.at[i, "bundesland"]), 0))
        for i in order:
            x, y = cands.at[i, "_x"], cands.at[i, "_y"]
            if all(math.hypot(x - a, y - b) >= min_sep_m for a, b in xy):
                picks.append(i)
                xy.append((x, y))
                st = str(cands.at[i, "bundesland"])
                state_n[st] = state_n.get(st, 0) + 1
                count[cat] += 1
                return True
        return False

    for _ in range(per):
        for cat in cats:
            if len(picks) < n:
                take_one(cat)
    progress = True
    while len(picks) < n and progress:  # categories that fell short hand over to the others
        progress = False
        for cat in cats:
            if len(picks) < n and take_one(cat):
                progress = True
    return cands.loc[picks].drop(columns=["_x", "_y"]).reset_index(drop=True)


# ----------------------------------------------------------------------------- random negatives


def worldcover_sample(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """ESA WorldCover 2021 v200 class code at points, read through Planetary Computer COGs.

    Only the pixels at the points are read (rasterio windowed reads), no whole tiles.
    """
    import planetary_computer as pc
    import pystac_client
    import rasterio

    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                    modifier=pc.sign_inplace)
    items = list(cat.search(collections=["esa-worldcover"], bbox=[5.8, 47.2, 15.1, 55.1],
                            datetime=f"{WORLDCOVER_YEAR}-01-01/{WORLDCOVER_YEAR}-12-31").items())
    out = np.zeros(len(lat), dtype=np.int32)

    def read_chunk(href: str, idx: np.ndarray) -> tuple[np.ndarray, list[int]]:
        with rasterio.open(href) as src:  # one dataset per thread (rasterio is not thread-safe)
            return idx, [int(v[0]) for v in src.sample(list(zip(lon[idx], lat[idx], strict=True)))]

    jobs = []
    for it in items:
        left, bottom, right, top = it.bbox
        m = np.flatnonzero((lon >= left) & (lon < right) & (lat >= bottom) & (lat < top))
        for chunk in np.array_split(m, max(1, len(m) // 100)) if len(m) else []:
            jobs.append((it.assets["map"].href, chunk))
    with ThreadPoolExecutor(max_workers=12) as ex:
        for idx, vals in ex.map(lambda j: read_chunk(*j), jobs):
            out[idx] = vals
    return out


def draw_land_points(states: gpd.GeoDataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Uniform random points inside Germany (area-weighted through rejection sampling)."""
    land = states.to_crs(METRIC).geometry.union_all()
    minx, miny, maxx, maxy = land.bounds
    rows: list[tuple[float, float]] = []
    while len(rows) < n:
        x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
        if land.contains(Point(x, y)):
            rows.append((x, y))
    xy = np.array(rows)
    ll = gpd.GeoSeries(gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=METRIC).to_crs(4326)
    return pd.DataFrame({"lat": ll.y.to_numpy(), "lon": ll.x.to_numpy()})


def class_quota(available: dict[str, int], target: dict[str, int], n: int) -> dict[str, int]:
    """Per-class counts: the target capped by availability, the remainder to the fallback classes."""
    q = {c: min(target.get(c, 0), available.get(c, 0)) for c in target}
    short = n - sum(q.values())
    while short > 0:
        moved = False
        for c in WORLDCOVER_FALLBACK:
            if short > 0 and q.get(c, 0) < available.get(c, 0):
                q[c] = q.get(c, 0) + 1
                short -= 1
                moved = True
        if not moved:
            break
    return q


def pick_random(points: pd.DataFrame, quota: dict[str, int], rng: np.random.Generator,
                forbid_xy: np.ndarray, taken_xy: np.ndarray | None = None,
                min_dist_m: float = NEG_MIN_DIST_M, min_sep_m: float = NEG_MIN_DIST_M
                ) -> pd.DataFrame:
    """Draw points per land cover class under the separation rules.

    ``points`` needs lat, lon and ``worldcover_class``. Points closer than ``min_dist_m`` to
    ``forbid_xy`` are dropped; picks keep ``min_sep_m`` to each other and to ``taken_xy``.
    """
    p = points.reset_index(drop=True).copy()
    p[["_x", "_y"]] = to_xy(p["lat"].to_numpy(), p["lon"].to_numpy())
    p = p[min_dist(p[["_x", "_y"]].to_numpy(), forbid_xy) >= min_dist_m]
    p = p.iloc[rng.permutation(len(p))]
    xy = [tuple(a) for a in np.asarray(taken_xy if taken_xy is not None else []).reshape(-1, 2)]
    picks = []
    for cls, k in quota.items():
        got = 0
        for i, row in p[p["worldcover_class"] == cls].iterrows():
            if got >= k:
                break
            if all(math.hypot(row["_x"] - a, row["_y"] - b) >= min_sep_m for a, b in xy):
                picks.append(i)
                xy.append((row["_x"], row["_y"]))
                got += 1
    return p.loc[picks].drop(columns=["_x", "_y"]).reset_index(drop=True)


# ----------------------------------------------------------------------------- assembly


def assemble(positives: dict[str, pd.DataFrame], pilot: pd.DataFrame, hard: pd.DataFrame,
             rand: pd.DataFrame, seed: int = paths.SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Combine all strata, shuffle with ``seed``, assign queue ids. Returns (queue, strata)."""
    parts = []

    def add(df: pd.DataFrame, stratum: str) -> None:
        q = pd.DataFrame({c: df.get(c, pd.NA) for c in QUEUE_COLUMNS})
        q["stratum"] = stratum
        parts.append(q)

    for tech, df in positives.items():
        add(df, "positive_battery" if tech == "battery" else "positive_pv")
    add(pilot, "pilot")
    add(hard, "hard_negative")
    add(rand, "random_negative")
    full = pd.concat(parts, ignore_index=True)
    extra = pd.concat(
        [positives["battery"], positives["ground_pv"], pilot, hard, rand], ignore_index=True)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(full))
    full = full.iloc[order].reset_index(drop=True)
    extra = extra.iloc[order].reset_index(drop=True)
    full["queue_id"] = [f"L1-{i + 1:04d}" for i in range(len(full))]
    strata = pd.DataFrame({"queue_id": full["queue_id"], "stratum": full["stratum"],
                           "site_id": full["site_id"]})
    for c in ["technology", "reg_size_class", "reg_period", "reg_status", "reg_colocated",
              "osm_id", "area_m2"]:
        strata[c] = extra.get(c, pd.NA)
    queue = full[QUEUE_COLUMNS].copy()
    for c in ["site_id", "landkreis", "osm_category", "worldcover_class", "bundesland"]:
        queue[c] = queue[c].astype("object").where(queue[c].notna(), None)
    return queue, strata


def summarise(queue: pd.DataFrame, strata: pd.DataFrame) -> pd.DataFrame:
    """Counts per stratum, technology, size class, period and state. No coordinates."""
    s = strata.merge(queue[["queue_id", "bundesland"]], on="queue_id")
    rows = []
    for dim, col in [("stratum", "stratum"), ("technology", "technology"),
                     ("size_class", "reg_size_class"), ("period", "reg_period"),
                     ("state", "bundesland"), ("stratum_x_state", None)]:
        if col is None:
            g = s.groupby(["stratum", "bundesland"], dropna=False).size()
            rows += [{"dimension": dim, "value": f"{a} | {b}", "n": int(v)}
                     for (a, b), v in g.items()]
        else:
            g = s[col].fillna("n/a").astype(str).value_counts()
            rows += [{"dimension": dim, "value": k, "n": int(v)} for k, v in g.items()]
    rows.append({"dimension": "total", "value": "queue", "n": len(queue)})
    return pd.DataFrame(rows)


def build(seed: int = paths.SEED, refresh_osm: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sites = pd.read_parquet(SITES)
    units = pd.read_parquet(UNITS)
    units = units[units["coord_state"] == "ok"]
    pilot_raw = pd.read_parquet(PILOT)
    pilot_ids = set(pilot_raw["site_key"])
    states = german_states()
    pool = positive_pool(sites, pilot_ids, states)

    pilot = pilot_raw.rename(columns={"site_key": "site_id"})
    meta = sites.set_index("site_id")[["landkreis", "technology"]]
    pilot["landkreis"] = pilot["site_id"].map(meta["landkreis"])
    pilot["technology"] = pilot["site_id"].map(meta["technology"])
    pilot["reg_size_class"] = pilot["reg_size_class"]
    pilot["reg_period"] = [
        "planned" if st == "In Planung" else period_of(st, c)
        for st, c in zip(pilot["reg_status"], pilot["reg_commissioning_date"], strict=True)]
    pilot_xy = to_xy(pilot["lat"].to_numpy(), pilot["lon"].to_numpy())

    positives = {}
    fixed = pilot_xy
    for tech, n in N_POS.items():  # the second technology keeps its distance to the first
        positives[tech] = select_positives(pool[pool["technology"] == tech], n, rng, fixed)
        fixed = np.vstack([fixed, to_xy(positives[tech]["lat"].to_numpy(),
                                        positives[tech]["lon"].to_numpy())])
    all_pos = pd.concat([*positives.values(), pilot], ignore_index=True)
    pos_xy = to_xy(all_pos["lat"].to_numpy(), all_pos["lon"].to_numpy())
    unit_xy = to_xy(units["lat"].to_numpy(), units["lon"].to_numpy())
    forbid = np.vstack([unit_xy, pos_xy])

    if refresh_osm or not HARD_CANDIDATES.exists():
        extract_hard_candidates()
    cands = pd.read_parquet(HARD_CANDIDATES)
    cands["bundesland"] = assign_states(cands, states)
    cands = cands[cands["bundesland"].notna()]
    hard = pick_hard(cands, N_HARD, rng, forbid)
    hard["osm_id"] = hard["osm_id"].astype(str)

    pts = draw_land_points(states, N_CANDIDATE_POINTS, rng)
    codes = worldcover_sample(pts["lat"].to_numpy(), pts["lon"].to_numpy())
    pts["worldcover_class"] = [WORLDCOVER_CLASSES.get(int(c), "nodata") for c in codes]
    pts = pts[pts["worldcover_class"] != "nodata"].reset_index(drop=True)
    avail = pts["worldcover_class"].value_counts().to_dict()
    quota = class_quota(avail, WORLDCOVER_TARGET, N_RANDOM)
    hard_xy = to_xy(hard["lat"].to_numpy(), hard["lon"].to_numpy())
    rand = pick_random(pts, quota, rng, forbid, taken_xy=hard_xy)
    rand["bundesland"] = assign_states(rand, states).to_numpy()

    queue, strata = assemble(positives, pilot, hard, rand, seed)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    queue.to_parquet(QUEUE, index=False)
    strata.to_parquet(STRATA, index=False)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary = summarise(queue, strata)
    summary.to_csv(SUMMARY, index=False)
    return summary


VIEW = LABELS_DIR / "queue_round1_view.parquet"
DOP_VIEW = LABELS_DIR / "dop_chips_queue_round1_view.parquet"
DOP_SOURCE = LABELS_DIR / "dop_chips_queue_round1.parquet"


def write_view(queue_path: Path = QUEUE, view_path: Path = VIEW, dop_source: Path = DOP_SOURCE,
               dop_view_path: Path = DOP_VIEW) -> None:
    """Blind files for the labelling app (m2): the queue reduced to queue_id, lat, lon, bundesland in file
    order, and the DOP chip index re-keyed by queue_id. Neither holds stratum, registry key, OSM category
    or land cover. The queue itself is not changed."""
    from bo.labelling.chipview import build_dop_index

    q = pd.read_parquet(queue_path)
    q[["queue_id", "lat", "lon", "bundesland"]].to_parquet(view_path, index=False)
    if dop_source.exists():
        build_dop_index(pd.read_parquet(dop_source), q[["queue_id", "site_id"]]).reset_index().to_parquet(
            dop_view_path, index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=paths.SEED)
    ap.add_argument("--refresh-osm", action="store_true",
                    help="re-extract hard negative candidates from the Geofabrik extract")
    ap.add_argument("--view-only", action="store_true",
                    help="only regenerate the blind view files from the existing queue")
    a = ap.parse_args()
    if a.view_only:
        write_view()
        return
    if not PBF.exists():
        size = pbf_size_ok()
        raise SystemExit(f"Geofabrik extract missing ({size / 1e9:.2f} GB): download {PBF_URL} to "
                         f"{PBF} first")
    s = build(a.seed, a.refresh_osm)
    write_view()
    print(s[s["dimension"].isin(["stratum", "total"])].to_string(index=False))


if __name__ == "__main__":
    main()
