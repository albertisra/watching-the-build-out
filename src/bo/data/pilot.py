"""Draw the Phase 2 pilot set of registered sites from the registry.

Version 0 was drawn from the partial MaStR export (5 of 30 storage files) and turned out to be
skewed towards older sites. Version 1 (the default) is drawn from the grouped site table of the
full export (``registry_sites.parquet``), so a pilot site is a physical site, not a unit.

Selection rules (registry fields are used to *select* sites only, never as model inputs):

* units with coordinates inside Germany (``coord_state == "ok"``);
* units sharing a ``LokationMaStRNummer`` collapse to one site, then sites closer than
  ``MIN_SEPARATION_M`` to an already chosen site are dropped, so no two pilot chips overlap;
* commissioning from ``MIN_YEAR`` (so construction falls in the Sentinel-2 L2A era) or status
  "In Planung", stratified by size class with a fixed seed; operating sites first, planned
  sites capped at ``MAX_PLANNED_SHARE`` of each technology.

Output: ``data/processed/pilot/pilot_sites_v1.parquet`` (not committed; site coordinates
stay out of the repository) and a count summary in ``results/registry/pilot_v1_summary.csv``.
Rebuild with ``make pilot``. Parameters are registered as A50 to A54 in ``docs/assumptions.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Geod

from bo import paths

SITES = paths.PROCESSED / "registry" / "registry_sites.parquet"
UNITS = paths.PROCESSED / "registry" / "units_ge_threshold.parquet"
NEG_IN = paths.PROCESSED / "pilot" / "negatives_v0.parquet"
NEG_OUT = paths.PROCESSED / "pilot" / "negatives_v1.parquet"
OUT = paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet"
SUMMARY = paths.RESULTS / "registry" / "pilot_v1_summary.csv"
NEG_SUMMARY = paths.RESULTS / "registry" / "negatives_v1_summary.csv"
NEG_MIN_DIST_M = 2_000.0
REG_RENAME = {
    "status": "reg_status",
    "commissioned": "reg_commissioning_date",
    "planned": "reg_planned",
    "size_class": "reg_size_class",
    "power_kw": "reg_power_kw",
}

N = {"battery": 20, "ground-mounted": 30}
MIN_YEAR = 2018
MIN_SEPARATION_M = 2_000.0
MAX_PLANNED_SHARE = 0.2  # planned sites may not exist on the ground yet
GEOD = Geod(ellps="WGS84")


def to_sites(units: pd.DataFrame) -> pd.DataFrame:
    """Collapse units to one row per location: summed power, first coordinate, latest dates."""
    u = units.copy()
    u["site_key"] = u["LokationMaStRNummer"].fillna(u["EinheitMastrNummer"])
    u["commissioned"] = pd.to_datetime(u["Inbetriebnahmedatum"], errors="coerce")
    agg = u.groupby(["subtype", "site_key"]).agg(
        lat=("lat", "first"),
        lon=("lon", "first"),
        power_kw=("power_kw", "sum"),
        n_units=("EinheitMastrNummer", "size"),
        unit_ids=("EinheitMastrNummer", lambda s: ";".join(s)),
        bundesland=("Bundesland_text", "first"),
        status=("EinheitBetriebsstatus_text", "first"),
        commissioned=("commissioned", "max"),
    )
    return agg.reset_index()


def size_class(power_kw: pd.Series) -> pd.Series:
    return pd.cut(
        power_kw,
        bins=[1_000, 5_000, 20_000, 100_000, np.inf],
        labels=["1-5 MW", "5-20 MW", "20-100 MW", ">=100 MW"],
        right=False,
    )


def far_enough(lat: float, lon: float, chosen: list[tuple[float, float]]) -> bool:
    for la, lo in chosen:
        _, _, d = GEOD.inv(lon, lat, lo, la)
        if d < MIN_SEPARATION_M:
            return False
    return True


def draw(sites: pd.DataFrame, subtype: str, n: int, rng: np.random.Generator,
         chosen: list[tuple[float, float]]) -> pd.DataFrame:
    s = sites[sites["subtype"] == subtype].copy()
    eligible = (s["commissioned"].dt.year >= MIN_YEAR) | (s["status"] == "In Planung")
    s = s[eligible & (s["status"] != "Endgültig stillgelegt")]
    s["size_class"] = size_class(s["power_kw"])
    classes = [c for c in s["size_class"].cat.categories if (s["size_class"] == c).any()]
    # Equal allocation across size classes, capped by availability, remainder to the largest pools.
    quota = {c: 0 for c in classes}
    # Shuffle, then put operating sites first and cap planned sites at MAX_PLANNED_SHARE.
    s = s.sample(frac=1, random_state=rng)
    s["planned"] = s["status"] == "In Planung"
    s = s.sort_values("planned", kind="stable")
    max_planned = round(MAX_PLANNED_SHARE * n)
    pools = {c: s[s["size_class"] == c] for c in classes}
    remaining = n
    while remaining > 0 and any(quota[c] < len(pools[c]) for c in classes):
        for c in classes:
            if remaining and quota[c] < len(pools[c]):
                quota[c] += 1
                remaining -= 1
    picked, planned = [], 0
    for c in classes:
        k = 0
        for _, row in pools[c].iterrows():
            if k == quota[c]:
                break
            if row.planned and planned >= max_planned:
                continue
            if far_enough(row.lat, row.lon, chosen):
                planned += int(row.planned)
                picked.append(row)
                chosen.append((row.lat, row.lon))
                k += 1
    return pd.DataFrame(picked)


def sites_from_registry(sites: pd.DataFrame) -> pd.DataFrame:
    """Map the grouped registry site table to the columns ``draw`` expects."""
    s = sites[sites["coord_state"] == "ok"]
    return pd.DataFrame(
        {
            "subtype": s["technology"].map({"battery": "battery", "ground_pv": "ground-mounted"}),
            "site_key": s["site_id"],
            "lat": s["lat"],
            "lon": s["lon"],
            "power_kw": s["power_kw"],
            "n_units": s["n_units"],
            "unit_ids": s["unit_ids"],
            "bundesland": s["bundesland"],
            "status": s["reg_status"],
            "commissioned": pd.to_datetime(s["reg_commissioning_date_last"], errors="coerce"),
        }
    ).reset_index(drop=True)


def nearest_unit_m(points: pd.DataFrame, units: pd.DataFrame) -> np.ndarray:
    """Great-circle distance in metres from each point to the nearest unit (haversine)."""
    from sklearn.neighbors import BallTree

    tree = BallTree(np.radians(units[["lat", "lon"]].to_numpy()), metric="haversine")
    dist, _ = tree.query(np.radians(points[["lat", "lon"]].to_numpy()), k=1)
    return dist[:, 0] * 6_371_008.8


def recheck_negatives() -> pd.DataFrame:
    """Drop negatives closer than NEG_MIN_DIST_M to any unit of the full large-unit table.

    Rechecks negatives v1 if it exists (it may have been topped up by the imagery code),
    otherwise starts from v0. Never adds negatives; a shortfall is reported in the summary.
    """
    source = NEG_OUT if NEG_OUT.exists() else NEG_IN
    neg = pd.read_parquet(source)
    units = pd.read_parquet(UNITS).query("coord_state == 'ok'")
    neg["nearest_unit_m"] = nearest_unit_m(neg, units)
    keep = neg[neg["nearest_unit_m"] >= NEG_MIN_DIST_M].copy()
    keep.to_parquet(NEG_OUT, index=False)
    summary = pd.DataFrame(
        [
            {"set": f"input ({source.stem})", "n": len(neg)},
            {"set": "dropped_too_close_to_full_registry", "n": len(neg) - len(keep)},
            {"set": "negatives_v1", "n": len(keep)},
        ]
    )
    summary.to_csv(NEG_SUMMARY, index=False)
    return summary


def main() -> None:
    rng = np.random.default_rng(paths.SEED)
    sites = sites_from_registry(pd.read_parquet(SITES))
    chosen: list[tuple[float, float]] = []
    pilot = pd.concat([draw(sites, k, n, rng, chosen) for k, n in N.items()], ignore_index=True)
    pilot.insert(0, "pilot_id", [f"Q{i:03d}" for i in range(len(pilot))])
    # Registry fields carry the reg_ prefix so registry_columns() drops them (circularity guard).
    pilot = pilot.rename(columns=REG_RENAME)
    pilot["quantity_type"] = "observed"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pilot.to_parquet(OUT, index=False)
    summary = (
        pilot.groupby(["subtype", "reg_size_class", "reg_status"], observed=True)
        .size()
        .rename("sites")
        .reset_index()
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY, index=False)
    print(summary.to_string(index=False))
    print(f"total={len(pilot)}  states={pilot['bundesland'].nunique()}  -> {OUT}")
    print(recheck_negatives().to_string(index=False))


if __name__ == "__main__":
    main()
