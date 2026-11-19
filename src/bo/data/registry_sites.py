"""Group registry units into physical sites and flag storage co-located with PV.

Grouping rule (documented in ``docs/data_card_registry.md``), applied per technology:

1. Units that share a ``LokationMaStRNummer`` (the registry's technical location) are linked
   when their usable coordinates lie within ``location_link_max_m`` of each other. Units of the
   same location without usable coordinates are linked to the first unit of that location. In the
   partial export the same location ID carried units tens to hundreds of kilometres apart, so the
   ID alone is not trusted when both units have coordinates.
2. Units of the same technology whose usable coordinates lie within ``site_distance_m`` of each
   other are linked (single linkage, so chains of close units form one site).
3. Units without a location ID and without usable coordinates stay single-unit sites.

Co-location: ``colocated_pv`` on a storage site means that a ground-mounted PV site from the PV
threshold lies within ``colocation_distance_m`` (default 300 m) of one of its units; the flag is
symmetric (``colocated_bess``). Nothing else sets it. Other matches are separate columns:
``shares_location_id_other_tech`` (same LokationMaStRNummer, both with coordinates within the link
distance or one without), ``declared_storage_pv_link`` (registry fields that name a joint
PV/storage unit) and ``nearest_other_tech_site_m``. PV units below the threshold are not seen.

Registry date columns carry the prefix ``reg_`` (circularity guard); this module never creates
a date column without it. Site coordinates are written only to ``data/processed``.

All quantities are observed (registry).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist

PROJ = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)  # ETRS89 / UTM 32N
SITE_PREFIX = {"battery": "BESS", "ground_pv": "PV"}
USABLE_COORD_STATES = ("ok", "swapped")


PRECISE_CLASSES = ("dp3", "dp4plus")


def project(lat: pd.Series, lon: pd.Series) -> np.ndarray:
    """Project WGS84 degrees to metres (UTM 32N; scale error below 0.3 % inside Germany)."""
    x, y = PROJ.transform(lon.to_numpy(float), lat.to_numpy(float))
    return np.column_stack([x, y])


def _usable(units: pd.DataFrame) -> pd.Series:
    return units["coord_state"].isin(USABLE_COORD_STATES) & units["lat"].notna() & units["lon"].notna()


def _components(n: int, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    g = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n))
    return connected_components(g, directed=False)[1]


def assign_sites(
    units: pd.DataFrame, site_distance_m: float = 300.0, location_link_max_m: float = 2000.0
) -> pd.Series:
    """Return a ``site_id`` per unit (same index as ``units``).

    ``units`` needs ``unit_id``, ``technology``, ``location_id``, ``lat``, ``lon``,
    ``coord_state``. The site id is ``BESS-`` or ``PV-`` plus the smallest unit id of the site.
    """
    link_m = max(site_distance_m, location_link_max_m)
    out = pd.Series(index=units.index, dtype=object)
    for tech, sub in units.groupby("technology"):
        sub = sub.reset_index()  # column "index" holds the original index
        n = len(sub)
        rows, cols = [np.arange(n)], [np.arange(n)]
        loc = sub["location_id"].where(sub["location_id"].astype(str).str.len() > 0)
        usable = _usable(sub).to_numpy()
        pos = pd.Series(np.arange(n), index=sub.index)
        # coordinate-less units attach to the first unit of their location
        first = pos.groupby(loc).transform("min")
        attach = loc.notna().to_numpy() & ~usable
        rows.append(np.arange(n)[attach])
        cols.append(first[attach].to_numpy(int))
        if usable.sum() > 1 and site_distance_m > 0:
            idx = np.flatnonzero(usable)
            xy = project(sub["lat"][usable], sub["lon"][usable])
            pairs = cKDTree(xy).query_pairs(link_m, output_type="ndarray")
            if len(pairs):
                d = np.hypot(*(xy[pairs[:, 0]] - xy[pairs[:, 1]]).T)
                lv = loc.to_numpy()[idx]
                same_loc = (lv[pairs[:, 0]] == lv[pairs[:, 1]]) & pd.notna(lv[pairs[:, 0]])
                keep = (d <= site_distance_m) | (same_loc & (d <= location_link_max_m))
                rows.append(idx[pairs[keep, 0]])
                cols.append(idx[pairs[keep, 1]])
        comp = _components(n, np.concatenate(rows), np.concatenate(cols))
        sub["_comp"] = comp
        rep = sub.groupby("_comp")["unit_id"].transform("min")
        out.loc[sub["index"].to_numpy()] = (SITE_PREFIX.get(tech, tech.upper()) + "-" + rep).to_numpy()
    return out


def colocation_pairs(
    units: pd.DataFrame, colocation_distance_m: float, location_link_max_m: float = 2000.0
) -> pd.DataFrame:
    """Site pairs (battery site, PV site) linked by distance or a shared location ID.

    Needs ``site_id`` on ``units``. Returns columns ``bess_site``, ``pv_site``, ``basis``
    (``location_id``, ``distance`` or ``both``).
    """
    bess = units[units["technology"] == "battery"]
    pv = units[units["technology"] == "ground_pv"]
    parts = []
    cols_ = ["site_id", "location_id", "lat", "lon", "coord_state"]
    lb = bess[bess["location_id"].astype(str).str.len() > 0][cols_]
    lp = pv[pv["location_id"].astype(str).str.len() > 0][cols_]
    shared = lb.merge(lp, on="location_id", suffixes=("_b", "_p"))
    if len(shared):
        both = _usable(shared.rename(columns={"lat_b": "lat", "lon_b": "lon", "coord_state_b": "coord_state"})) & \
            _usable(shared.rename(columns={"lat_p": "lat", "lon_p": "lon", "coord_state_p": "coord_state"}))
        dist = np.full(len(shared), np.nan)
        if both.any():
            sb = shared[both]
            dist[both.to_numpy()] = np.hypot(*(project(sb["lat_b"], sb["lon_b"]) - project(sb["lat_p"], sb["lon_p"])).T)
        shared = shared[(~both.to_numpy()) | (dist <= location_link_max_m)]
    if len(shared):
        parts.append(
            pd.DataFrame(
                {"bess_site": shared["site_id_b"], "pv_site": shared["site_id_p"], "basis": "location_id"}
            )
        )
    bu, pu = bess[_usable(bess)], pv[_usable(pv)]
    if len(bu) and len(pu) and colocation_distance_m > 0:
        tree = cKDTree(project(pu["lat"], pu["lon"]))
        hits = tree.query_ball_point(project(bu["lat"], bu["lon"]), colocation_distance_m)
        b_ids, p_ids = bu["site_id"].to_numpy(), pu["site_id"].to_numpy()
        rec = [(b_ids[i], p_ids[j]) for i, js in enumerate(hits) for j in js]
        if rec:
            parts.append(pd.DataFrame(rec, columns=["bess_site", "pv_site"]).assign(basis="distance"))
    if not parts:
        return pd.DataFrame(columns=["bess_site", "pv_site", "basis"])
    allp = pd.concat(parts, ignore_index=True)
    return (
        allp.groupby(["bess_site", "pv_site"])["basis"]
        .agg(lambda s: "both" if len(set(s)) > 1 else next(iter(s)))
        .reset_index()
    )


def _nearest_other_tech_m(u: pd.DataFrame) -> pd.Series:
    """Distance in metres from each site to the nearest unit of the other technology (min over units)."""
    us = u[_usable(u)]
    out = {}
    for tech, other in (("battery", "ground_pv"), ("ground_pv", "battery")):
        a, b = us[us["technology"] == tech], us[us["technology"] == other]
        if a.empty or b.empty:
            continue
        d, _ = cKDTree(project(b["lat"], b["lon"])).query(project(a["lat"], a["lon"]))
        out.update(pd.Series(d, index=a["site_id"].to_numpy()).groupby(level=0).min().to_dict())
    return pd.Series(out, dtype=float)


def _mode(s: pd.Series):
    s = s.dropna()
    s = s[s.astype(str).str.len() > 0]
    return s.value_counts().index[0] if len(s) else None


def _join(s: pd.Series) -> str:
    return ";".join(sorted({str(v) for v in s.dropna() if str(v)}))


def _extent_m(xy: np.ndarray) -> float:
    return float(pdist(xy).max()) if len(xy) > 1 else 0.0


def build_sites(
    units: pd.DataFrame,
    site_distance_m: float = 300.0,
    colocation_distance_m: float | None = None,
    location_link_max_m: float = 2000.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(units_with_site_id, sites)`` as plain DataFrames (geometry added by the caller).

    Expected unit columns: ``unit_id, technology, location_id, lat, lon, coord_state, gross_kw,
    net_kw, power_kw, usable_kwh_alloc, reg_status, bundesland, landkreis, grid_operator_id,
    voltage_level, reg_registration_date, reg_commissioning_date,
    reg_planned_commissioning_date``. Missing optional columns are tolerated.
    """
    if colocation_distance_m is None:
        colocation_distance_m = site_distance_m
    u = units.copy()
    u["site_id"] = assign_sites(u, site_distance_m, location_link_max_m)
    pairs = colocation_pairs(u, colocation_distance_m, location_link_max_m)
    u["flag_location_split_by_distance"] = (u["location_id"].astype(str).str.len() > 0) & (
        u.groupby(["technology", "location_id"])["site_id"].transform("nunique") > 1
    )
    flag_cols = [c for c in u.columns if c.startswith(("flag_", "reg_flag_"))]
    recs = []
    for sid, g in u.groupby("site_id", sort=True):
        usable = _usable(g)
        # m-new-3: a coarse (dp1/dp2) unit must not drag the position of a site that also has precise units.
        coarse_dropped = False
        if "coord_precision_class" in g:
            precise = usable & g["coord_precision_class"].isin(PRECISE_CLASSES)
            if precise.any() and (precise != usable).any():
                coarse_dropped = True
                usable = precise
        w = g["power_kw"].where(usable).fillna(0.0)
        if usable.any():
            ww = w if w.sum() > 0 else usable.astype(float)
            lat = float(np.average(g["lat"][usable], weights=ww[usable]))
            lon = float(np.average(g["lon"][usable], weights=ww[usable]))
            extent = _extent_m(project(g["lat"][usable], g["lon"][usable]))
            state = "ok" if (g.loc[usable, "coord_state"] == "ok").any() else "swapped"
        else:
            lat = lon = np.nan
            extent = np.nan
            state = "missing" if (g["coord_state"] == "missing").all() else "outside"
        by_status = g.groupby("reg_status", dropna=False)["power_kw"].sum().sort_values(ascending=False)
        rec = {
            "site_id": sid,
            "technology": g["technology"].iloc[0],
            "n_units": len(g),
            "n_units_with_coords": int(usable.sum()),
            "unit_ids": _join(g["unit_id"]),
            "location_ids": _join(g["location_id"]),
            "lat": lat,
            "lon": lon,
            "coord_state": state,
            "site_extent_m": extent,
            "gross_kw": g["gross_kw"].sum(min_count=1),
            "net_kw": g["net_kw"].sum(min_count=1),
            "power_kw": g["power_kw"].sum(min_count=1),
            "usable_kwh": g["usable_kwh_alloc"].sum(min_count=1) if "usable_kwh_alloc" in g else np.nan,
            "reg_status": by_status.index[0] if len(by_status) else None,
            "reg_status_set": _join(g["reg_status"]),
            "bundesland": _mode(g["bundesland"]),
            "landkreis": _mode(g["landkreis"]) if "landkreis" in g else None,
            "grid_operator_id": _mode(g["grid_operator_id"]) if "grid_operator_id" in g else None,
            "voltage_level": _mode(g["voltage_level"]) if "voltage_level" in g else None,
            "reg_registration_date_first": g["reg_registration_date"].min(),
            "reg_commissioning_date_first": g["reg_commissioning_date"].min(),
            "reg_commissioning_date_last": g["reg_commissioning_date"].max(),
            "reg_planned_commissioning_date_last": g["reg_planned_commissioning_date"].max(),
            "n_locations": g["location_id"].replace("", np.nan).nunique(),
        }
        if "coord_precision_class" in g:  # coarsest unit class: the site position is only as good as that
            cl = g["coord_precision_class"].dropna()
            order = ["dp1", "dp2", "dp3", "dp4plus"]
            rec["coord_precision_class"] = min(cl, key=order.index) if len(cl) else None
            if coarse_dropped:  # position and uncertainty come from the precise units only
                cl = g.loc[usable, "coord_precision_class"].dropna()
                rec["coord_precision_class"] = min(cl, key=order.index)
                unc = g.loc[usable, "coord_unc_m"]
            else:
                unc = g["coord_unc_m"]
            rec["coord_unc_m"] = float(unc.max()) if unc.notna().any() else np.nan
            rec["coord_coarse_units_excluded"] = coarse_dropped
        for c in flag_cols:
            rec[c + "_any"] = bool(g[c].fillna(False).any())
        recs.append(rec)
    sites = pd.DataFrame(recs)
    if sites.empty:
        sites = pd.DataFrame(columns=["site_id", "technology"])
    # Co-location. ``colocated_pv`` / ``colocated_bess`` mean ONE thing: a site of the other
    # technology (ground-mounted PV from the PV threshold, or battery from the storage threshold)
    # lies within ``colocation_distance_m``. Other kinds of match are separate columns.
    sid = sites["site_id"]
    dist_pairs = pairs[pairs["basis"].isin(["distance", "both"])]
    loc_pairs = pairs[pairs["basis"].isin(["location_id", "both"])]

    def partners(df, key, other):
        return df.groupby(key)[other].agg(lambda x: ";".join(sorted(set(x))))

    dist_partners = pd.concat([partners(dist_pairs, "bess_site", "pv_site"),
                               partners(dist_pairs, "pv_site", "bess_site")])
    loc_partners = pd.concat([partners(loc_pairs, "bess_site", "pv_site"),
                              partners(loc_pairs, "pv_site", "bess_site")])
    near = sid.isin(dist_partners.index)
    sites["colocated_pv"] = near & (sites["technology"] == "battery")
    sites["colocated_bess"] = near & (sites["technology"] == "ground_pv")
    sites["colocated_site_ids"] = sid.map(dist_partners).astype(object).fillna("")
    sites["shares_location_id_other_tech"] = sid.isin(loc_partners.index)
    sites["location_id_partner_site_ids"] = sid.map(loc_partners).astype(object).fillna("")
    sites["nearest_other_tech_site_m"] = sid.map(_nearest_other_tech_m(u))
    declared = pd.Series(False, index=u.index)
    if "storage_pv_unit_link" in u:
        declared = declared | (u["storage_pv_unit_link"].astype(object).fillna("").astype(str).str.len() > 0)
    if "pv_declares_storage_same_site" in u:
        declared = declared | u["pv_declares_storage_same_site"].astype(object).fillna("").astype(str).isin(["1", "true", "True"])
    sites["declared_storage_pv_link"] = sid.isin(u.loc[declared, "site_id"]) if len(u) else False
    return u, sites
