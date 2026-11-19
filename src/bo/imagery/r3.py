"""R3 test: are bright PV and container sites masked as cloud by the SCL 4/5/6 rule?

For each site, daily Sentinel Hub Statistical API summaries over a small footprint disk and a
surrounding ring give, per acquisition day, the fraction of pixels in each SCL class and under
three cloud-probability thresholds (Sen2Cor ``CLD`` band). The footprint is a fixed disk
(radius 40 m) around the site coordinate and the ring runs from 150 m to 300 m, so no registry
field enters the geometry. Raw responses are cached under ``data/raw/sentinelhub/r3/``.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point

from bo import paths

from .geo import transformer, utm_epsg
from .quota import GLOBAL
from .sentinelhub import CLD_THRESHOLDS, stats_request

CACHE = paths.RAW / "sentinelhub" / "r3"
FOOTPRINT_R = 40.0
RING_IN, RING_OUT = 150.0, 300.0


def geometries(lon: float, lat: float) -> tuple[int, dict[str, list[list[float]]]]:
    epsg = utm_epsg(lon, lat)
    x, y = transformer(4326, epsg).transform(lon, lat)
    c = Point(x, y)
    fp = c.buffer(FOOTPRINT_R, 16)
    ring = c.buffer(RING_OUT, 32).difference(c.buffer(RING_IN, 32))
    return epsg, {
        "footprint": [list(p) for p in fp.exterior.coords],
        "ring": [list(p) for p in ring.exterior.coords],
    }


def _parse(resp: dict, site_id: str, which: str) -> pd.DataFrame:
    rows = []
    for d in resp.get("data", []):
        o = d["outputs"]
        scl = [o["scl"]["bands"][f"B{k}"]["stats"] for k in range(12)]
        cld = [o["cld"]["bands"][f"B{k}"]["stats"] for k in range(len(CLD_THRESHOLDS))]
        n = scl[0]["sampleCount"] - scl[0]["noDataCount"]
        if n <= 0:
            continue
        row = {"site_id": site_id, "geom": which, "date": d["interval"]["from"][:10], "n_px": n}
        row.update({f"scl_{k}": scl[k]["mean"] for k in range(12)})
        row.update({f"cld_le{t}": cld[i]["mean"] for i, t in enumerate(CLD_THRESHOLDS)})
        rows.append(row)
    return pd.DataFrame(rows)


def fetch_site(site_id: str, lon: float, lat: float, start: str, end: str,
               force: bool = False) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    epsg, geoms = geometries(lon, lat)
    frames = []
    for which, poly in geoms.items():
        f = CACHE / f"{site_id}_{which}_{start}_{end}.json"
        if f.exists() and not force:
            resp = json.loads(f.read_text())
        else:
            resp = stats_request(poly, epsg, start, end)
            f.write_text(json.dumps(resp))
        frames.append(_parse(resp, site_id, which))
    return pd.concat(frames, ignore_index=True)


def fetch_all(sites: pd.DataFrame, start: str, end: str, workers: int = 4) -> pd.DataFrame:
    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(lambda r: fetch_site(r.site_id, r.lon, r.lat, start, end),
                            sites.itertuples()))
    return pd.concat(parts, ignore_index=True)


def add_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Per-day clear fractions under each rule (fraction of valid pixels)."""
    out = df.copy()
    out["clear_scl456"] = out[["scl_4", "scl_5", "scl_6"]].sum(axis=1)
    out["clear_alt"] = out[["scl_2", "scl_4", "scl_5", "scl_6", "scl_7"]].sum(axis=1)
    for t in CLD_THRESHOLDS:
        out[f"clear_cld{t}"] = out[f"cld_le{t}"]
    out["cloud_scl"] = out[["scl_8", "scl_9", "scl_10"]].sum(axis=1)
    out["unclassified_or_shadow"] = out[["scl_2", "scl_7"]].sum(axis=1)
    return out


RULES = ["clear_scl456", "clear_alt"] + [f"clear_cld{t}" for t in CLD_THRESHOLDS]


def site_summary(df: pd.DataFrame, min_days: int = 20) -> pd.DataFrame:
    """Footprint versus ring per site and rule over the days both geometries were observed.

    clear_obs_fp / clear_obs_ring: sum over days of the clear pixel fraction (expected clear
    observations per pixel). ratio = fp / ring. cloud_fp_given_ring_clear: share of days on which
    the footprint is mostly cloud (SCL 8 to 10 above 50 percent) while the ring is mostly clear
    under SCL 4/5/6 (above 50 percent).
    """
    d = add_rules(df)
    fp = d[d.geom == "footprint"].set_index(["site_id", "date"])
    rg = d[d.geom == "ring"].set_index(["site_id", "date"])
    j = fp.add_suffix("_fp").join(rg.add_suffix("_ring"), how="inner")
    rows = []
    for sid, g in j.groupby(level=0):
        if len(g) < min_days:
            continue
        r = {"site_id": sid, "n_days": len(g)}
        for rule in RULES:
            a, b = g[f"{rule}_fp"].sum(), g[f"{rule}_ring"].sum()
            r[f"clear_obs_fp_{rule}"] = a
            r[f"clear_obs_ring_{rule}"] = b
            r[f"ratio_{rule}"] = a / b if b > 0 else np.nan
        ring_clear = g["clear_scl456_ring"] > 0.5
        r["n_days_ring_clear"] = int(ring_clear.sum())
        r["cloud_fp_given_ring_clear"] = (
            float(((g["cloud_scl_fp"] > 0.5) & ring_clear).sum() / ring_clear.sum())
            if ring_clear.sum() else np.nan)
        r["unclass_or_shadow_fp_given_ring_clear"] = (
            float(g.loc[ring_clear, "unclassified_or_shadow_fp"].mean()) if ring_clear.sum()
            else np.nan)
        r["unclass_or_shadow_ring_given_ring_clear"] = (
            float(g.loc[ring_clear, "unclassified_or_shadow_ring"].mean()) if ring_clear.sum()
            else np.nan)
        for k in (1, 2, 3, 7, 8, 9, 10, 11):
            r[f"mean_scl{k}_fp"] = float(g[f"scl_{k}_fp"].mean())
            r[f"mean_scl{k}_ring"] = float(g[f"scl_{k}_ring"].mean())
        rows.append(r)
    return pd.DataFrame(rows)


def bootstrap_ci(x: np.ndarray, n: int = 5000, seed: int = paths.SEED) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def analyse(daily: pd.DataFrame, groups: pd.DataFrame, operating_from: pd.Series | None = None,
            min_days: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-site table and per-group aggregates (mean over sites with a bootstrap interval).

    ``groups``: site_id, group. ``operating_from``: optional Series site_id -> first date counted
    as "operating" (registry commissioning date plus a margin). It only selects days for the
    "operating" rows; it is not written to the output. Pilot targets are expected to be bright
    only after construction, so the "operating" rows are the relevant ones for PV and batteries.
    """
    parts = []
    allrows = site_summary(daily, min_days).assign(period="all")
    parts.append(allrows)
    if operating_from is not None:
        d = daily.merge(operating_from.rename("t0"), left_on="site_id", right_index=True, how="inner")
        d = d[pd.to_datetime(d["date"]) >= d["t0"]].drop(columns="t0")
        parts.append(site_summary(d, min_days).assign(period="operating"))
    per_site = pd.concat(parts, ignore_index=True).merge(groups, on="site_id", how="left")
    metrics = [f"ratio_{r}" for r in RULES] + ["cloud_fp_given_ring_clear",
                                               "unclass_or_shadow_fp_given_ring_clear",
                                               "unclass_or_shadow_ring_given_ring_clear"]
    rows = []
    for (grp, per), g in per_site.groupby(["group", "period"]):
        for m in metrics:
            mean, lo, hi = bootstrap_ci(g[m].to_numpy())
            rows.append({"group": grp, "period": per, "metric": m, "n_sites": int(g[m].notna().sum()),
                         "mean": mean, "ci95_low": lo, "ci95_high": hi})
    return per_site, pd.DataFrame(rows)


_ = (GLOBAL, Path)
