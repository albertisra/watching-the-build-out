"""Summary tables, output files and the data card of the registry pipeline.

Everything written to ``results/`` and ``docs/`` is aggregated (counts, MW, MWh by technology,
status, federal state or month). Site and unit coordinates go only to GeoParquet files in
``data/processed/registry/``. All quantities are observed (registry data).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from bo.data import registry_compare as rc
from bo.data import registry_series as rs

TECH_LABEL = {"battery": "battery storage", "ground_pv": "ground-mounted PV"}
UNIT_FILE = "registry_units.parquet"
SITE_FILE = "registry_sites.parquet"


def _flag_columns(units: pd.DataFrame) -> list[str]:
    return [c for c in units.columns if c.startswith(("flag_", "reg_flag_"))]


def flag_counts(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tech, g in units.groupby("technology"):
        for c in _flag_columns(units):
            n = int(g[c].fillna(False).astype(bool).sum())
            rows.append({"technology": tech, "flag": c, "units": n, "share": n / len(g) if len(g) else 0.0,
                         "units_total": len(g)})
    return pd.DataFrame(rows)


COLOC_BANDS = [-1, 0, 10, 50, 100, 300, 1000, 2000, float("inf")]
COLOC_LABELS = ["0 m (same point)", ">0 to 10 m", ">10 to 50 m", ">50 to 100 m", ">100 to 300 m",
                ">300 to 1000 m", ">1000 to 2000 m", ">2000 m"]


def colocation_breakdown(sites: pd.DataFrame) -> pd.DataFrame:
    """Sites by distance to the nearest site of the other technology, and by other match kinds."""
    s = sites[sites["coord_state"].isin(["ok", "swapped"])].copy()
    s["distance_band"] = pd.cut(s["nearest_other_tech_site_m"], COLOC_BANDS, labels=COLOC_LABELS)
    s["distance_band"] = s["distance_band"].astype(object).fillna("no site of other technology")
    out = (
        s.groupby(["technology", "distance_band"])
        .agg(sites=("site_id", "size"), sites_sharing_location_id=("shares_location_id_other_tech", "sum"),
             sites_declared_link=("declared_storage_pv_link", "sum"))
        .reset_index()
    )
    return out


def summary_tables(units, sites, monthly, comparison, meta) -> dict[str, pd.DataFrame]:
    t: dict[str, pd.DataFrame] = {}
    sites = sites.assign(colocated_any=sites["colocated_pv"] | sites["colocated_bess"])
    t["members"] = pd.DataFrame([
        {"table": k, "members_in_zip": r.members,
         "members_readable": "not attempted" if r.note else r.readable,
         "members_unreadable": "" if r.note else len(r.unreadable), "rows_read": r.rows_read}
        for k, r in meta["reports"].items()
    ])
    t["units_summary"] = (
        units.groupby(["technology", "reg_status"], dropna=False)
        .agg(units=("unit_id", "size"), gross_mw=("gross_kw", lambda s: s.sum() / 1000.0),
             net_mw=("net_kw", lambda s: s.sum() / 1000.0),
             usable_mwh=("usable_kwh_alloc", lambda s: s.sum(min_count=1) / 1000.0),
             units_kwh_known=("usable_kwh_alloc", lambda s: int(s.notna().sum())))
        .reset_index()
    )
    t["coord_state"] = (
        units.groupby(["technology", "coord_state"]).agg(
            units=("unit_id", "size"), gross_mw=("gross_kw", lambda s: s.sum() / 1000.0)).reset_index()
    )
    t["coord_decimals"] = (
        units[units["coord_state"].isin(["ok", "swapped"])]
        .groupby(["technology", "coord_decimals"]).size().rename("units").reset_index()
    )
    t["coordinate_precision"] = coordinate_precision_table(units, sites)
    t["flags"] = flag_counts(units)
    cls = [{"kind": k, "class": c.replace(" | ", " / "), "units_ge_threshold": n} for k, cnt in meta["classes"].items()
           for c, n in cnt.most_common()]
    t["technology_classes"] = pd.DataFrame(cls)
    t["sites_summary"] = (
        sites.groupby("technology").agg(
            sites=("site_id", "size"), units=("n_units", "sum"),
            multi_unit_sites=("n_units", lambda s: int((s > 1).sum())),
            max_units_per_site=("n_units", "max"),
            sites_with_coords=("n_units_with_coords", lambda s: int((s > 0).sum())),
            sites_colocated=("colocated_any", "sum"),
            median_extent_m_multi=("site_extent_m", lambda s: s[s > 0].median()),
            max_extent_m=("site_extent_m", "max"),
            power_mw=("power_kw", lambda s: s.sum() / 1000.0),
        ).reset_index()
    )
    t["sites_by_state"] = (
        sites.groupby(["technology", "bundesland"], dropna=False)
        .agg(sites=("site_id", "size"), units=("n_units", "sum"),
             power_mw=("power_kw", lambda s: s.sum() / 1000.0),
             sites_colocated=("colocated_any", "sum"))
        .reset_index()
    )
    t["colocation_breakdown"] = colocation_breakdown(sites)
    planned = units[units["reg_status"] == rs.STATUS_PLANNED]
    t["pipeline_planned_by_state"] = (
        planned.groupby(["technology", "bundesland"], dropna=False)
        .agg(units=("unit_id", "size"), gross_mw=("gross_kw", lambda s: s.sum() / 1000.0),
             net_mw=("net_kw", lambda s: s.sum() / 1000.0),
             usable_mwh=("usable_kwh_alloc", lambda s: s.sum(min_count=1) / 1000.0))
        .reset_index()
    )
    t["series_exclusions"] = rs.exclusion_summary(units)
    t["capacity_by_state"] = monthly
    t["capacity_national"] = rs.national_totals(monthly) if len(monthly) else monthly
    t["comparison"] = comparison
    t["grid_coverage"] = rc.grid_coverage(units)
    cfg = meta["config"]
    rows = [("export_file", meta["export_file"]), ("export_date", meta["export_date"]),
            ("is_partial", meta["is_partial"]), ("grid_join_available", meta["grid_join_available"]),
            ("catalogue_entries", meta["catalogue_entries"]), ("units_in_scope", len(units)),
            ("sites", len(sites))] + [(f"config_{k}", v) for k, v in cfg.items()]
    t["run_meta"] = pd.DataFrame(rows, columns=["key", "value"])
    dated = units["reg_registration_date"].dropna().dt.date.astype(str)
    t["registration_date_mode"] = (
        dated.value_counts().head(5).rename_axis("reg_registration_date").rename("units").reset_index()
    )
    return t


def coordinate_precision_table(units: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    """Site counts by technology, subtype and coordinate precision class (observed, registry).

    Subtype is the most common unit-level storage technology (battery) or PV type (ground_pv) of the
    site. Only sites with usable coordinates (coord_state ok) are counted.
    """
    sub = units["storage_tech"].where(units["technology"] == "battery", units["pv_art"])
    mode = (units.assign(subtype=sub.fillna("unknown").replace("", "unknown"))
            .groupby("site_id")["subtype"].agg(lambda s: s.value_counts().index[0]))
    s = sites[sites["coord_state"] == "ok"].copy()
    s["subtype"] = s["site_id"].map(mode).fillna("unknown")
    t = (s.groupby(["technology", "subtype", "coord_precision_class"], dropna=False)
         .agg(sites=("site_id", "size"), median_implied_unc_m=("coord_unc_m", "median")).reset_index())
    t["coord_precision_class"] = t["coord_precision_class"].fillna("missing")
    return t


RESULT_FILES = {
    "coordinate_precision": "coordinate_precision.csv",
    "capacity_by_state": "capacity_monthly_by_state.csv",
    "capacity_national": "capacity_monthly_national.csv",
    "comparison": "comparison_official_statistics.csv",
    "flags": "registry_quality_flags.csv",
    "units_summary": "registry_units_summary.csv",
    "coord_state": "registry_coord_state.csv",
    "coord_decimals": "registry_coord_decimals.csv",
    "members": "registry_members_readable.csv",
    "sites_summary": "registry_sites_summary.csv",
    "sites_by_state": "registry_sites_by_state.csv",
    "colocation_breakdown": "registry_colocation_breakdown.csv",
    "pipeline_planned_by_state": "registry_pipeline_planned_by_state.csv",
    "series_exclusions": "capacity_series_exclusions.csv",
    "technology_classes": "registry_technology_classes.csv",
    "run_meta": "registry_run_meta.csv",
    "grid_coverage": "registry_grid_coverage.csv",
    "registration_date_mode": "registry_registration_date_top.csv",
}


def _to_geo(df: pd.DataFrame) -> gpd.GeoDataFrame:
    g = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    return g


def write_outputs(result, out_processed: Path, out_results: Path) -> None:
    out_processed.mkdir(parents=True, exist_ok=True)
    out_results.mkdir(parents=True, exist_ok=True)
    units = result.units.drop(columns=["lat_raw", "lon_raw"], errors="ignore")
    _to_geo(units).to_parquet(out_processed / UNIT_FILE, index=False)
    _to_geo(result.sites).to_parquet(out_processed / SITE_FILE, index=False)
    for key, name in RESULT_FILES.items():
        result.tables[key].to_csv(out_results / name, index=False)


# ---------------------------------------------------------------------------------------
# Data card


def _md(df: pd.DataFrame, floatfmt: str = ",.1f") -> str:
    if df.empty:
        return "_none_\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, (bool, np.bool_)):
                cells.append(str(bool(v)))
            elif isinstance(v, (int, np.integer)):
                cells.append(format(int(v), ","))
            elif isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else format(float(v), floatfmt))
            else:
                cells.append("" if v is None or v is pd.NA else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def write_data_card(result, path: Path) -> None:
    path.write_text(render_data_card(result), encoding="utf-8")


def render_data_card(result) -> str:
    m, t, cfg = result.meta, result.tables, result.meta["config"]
    partial = m["is_partial"]
    fl = t["flags"]

    def flag(tech: str, name: str) -> str:
        r = fl[(fl["technology"] == tech) & (fl["flag"] == name)]
        return "n/a" if r.empty else f"{int(r['units'].iloc[0]):,} ({r['share'].iloc[0]:.1%})"

    mem = t["members"].copy()
    mem["readable_share"] = [
        "" if (not n or isinstance(r, str)) else f"{r / n:.0%}"
        for r, n in zip(mem["members_readable"], mem["members_in_zip"], strict=True)
    ]
    banner = (
        "> **PARTIAL RUN. Read this first.** This card was produced from an export in which some members "
        "could not be read (table below). Every count, capacity and series in this run is a lower bound "
        "and is **not comparable with official statistics yet**. The comparison section is marked "
        "\"pending full export\". Rerun `make registry` on the complete export; the card is rewritten.\n"
        if partial else
        "> Run on a complete export: all core members were readable.\n"
    )
    flag_names = [
        ("flag_coord_missing", "coordinates missing"),
        ("flag_coord_outside_germany", "coordinates present but outside the Germany box"),
        ("flag_coord_swapped", "latitude and longitude swapped (fixed in `lat`, `lon`)"),
        ("flag_coord_rounded", "coordinates with at most 2 real decimals, judged on the numeric value (about 1 km or coarser)"),
        ("reg_flag_commissioning_placeholder", "commissioning date is a placeholder or unparseable"),
        ("reg_flag_registration_placeholder", "registration date is a placeholder or unparseable"),
        ("reg_flag_planned_commissioning_placeholder", "planned commissioning date is a placeholder"),
        ("reg_flag_commissioning_before_1990", "commissioning before 1990"),
        ("reg_flag_commissioning_future", "commissioning date after the export date"),
        ("reg_flag_registration_future", "registration date after the export date"),
        ("reg_flag_commissioned_before_registry_opened",
         "(a) commissioned before the registry opened on 2019-01-31 (expected, not an anomaly)"),
        ("reg_flag_registration_at_launch_date", "registration on or before 2019-01-31 (registry start)"),
        ("reg_flag_late_registration", "(b) commissioned since 2019-01-31 and registered more than 31 days later (late registration)"),
        ("reg_flag_registered_before_commissioning", "registered before commissioning (pre-construction registration)"),
        ("reg_flag_registered_in_planning_stage", "status In Planung (not yet built according to the registry)"),
        ("reg_flag_planned_date_in_past", "In Planung with planned date before the export date"),
        ("reg_flag_planned_without_date", "In Planung without a planned date"),
        ("reg_flag_planned_with_past_commissioning_date", "In Planung but carries a past commissioning date"),
        ("reg_flag_operating_without_commissioning_date", "In Betrieb without a usable commissioning date"),
        ("flag_power_implausible", "gross power above 2 GW for one unit"),
        ("flag_net_gt_gross", "net power above gross power"),
        ("flag_kwh_missing", "storage: usable kWh not available"),
        ("flag_kwh_implausible_duration", "storage: usable kWh over gross kW outside 0.1 to 12 h"),
        ("flag_duplicate_unit_id", "same unit ID more than once"),
        ("flag_duplicate_candidate", "candidate duplicate (same place, power and dates, different location ID)"),
    ]
    rows = [{"check": text, "battery storage": flag("battery", f), "ground-mounted PV": flag("ground_pv", f)}
            for f, text in flag_names]
    flag_table = _md(pd.DataFrame(rows))

    us = t["units_summary"].copy()
    us = us.rename(columns={"technology": "technology", "reg_status": "registry status"})
    cs = t["coord_state"].copy()
    ss = t["sites_summary"].copy()
    ex = t["series_exclusions"].copy()
    nat = t["capacity_national"]
    last_month = nat["month"].max() if len(nat) else ""

    comp = t["comparison"].copy()
    show = comp[["metric", "value", "unit", "stichtag", "grade"]].rename(
        columns={"value": "reference value", "grade": "source grade"})
    show["ours variant"] = comp["ours_variant"]
    if partial:
        show["ours (observed)"] = "pending full export"
        show["ratio"] = ""
    else:
        show["ours (observed)"] = comp["ours"].map(lambda v: "n/a" if pd.isna(v) else f"{v:,.2f}")
        show["ratio"] = comp["ratio_ours_to_reference"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    show["comparable"] = comp["comparable"]
    show["explanation class"] = comp["explanation_class"]
    explain = "\n".join(
        f"* `{r.metric}` ({r.ours_variant}): {r.explanation}" for r in comp.itertuples()
    )
    gc = t["grid_coverage"]
    grid_txt = (
        "Grid operator ID and voltage level are joined through `Lokationen` (unit location ID to connection point "
        "IDs) and `Netzanschlusspunkte` (`NetzanschlusspunktMastrNummer`, operator ID, voltage level). The join is "
        "partial by construction: **planned units carry no location ID in the export and can never be joined**. "
        "Coverage by technology and status:\n\n" + _md(gc)
        if m["grid_join_available"] else
        "**Grid operator and voltage level are empty in this run.** `Lokationen` and/or "
        "`Netzanschlusspunkte` were not fully readable, so the join was skipped rather than half done. "
        "It fills `grid_operator_id` and `voltage_level` on a readable export. The MV-and-above row needs it."
    )
    csv_note = (
        "Machine-readable: `results/registry/comparison_official_statistics.csv` (carries our partial values with "
        "`status = pending_full_export`; do not read them against the reference)."
        if partial else
        "Machine-readable: `results/registry/comparison_official_statistics.csv` (`status` is `computed`, or "
        "`not_computable` where an input such as voltage level is missing)."
    )
    intro10 = (
        "Our values are lower bounds from a partial export; the table shows the reference only."
        if partial else "Our values come from a complete export (grid join: " + ("yes" if m["grid_join_available"] else "no") + ")."
    )
    first_cols = ", ".join(f"`{c}`" for c in [
        "site_id", "technology", "n_units", "unit_ids", "location_ids", "lat", "lon", "coord_state",
        "site_extent_m", "gross_kw", "net_kw", "power_kw", "usable_kwh", "reg_status", "bundesland",
        "landkreis", "grid_operator_id", "voltage_level", "colocated_pv", "colocated_bess",
        "colocated_site_ids", "shares_location_id_other_tech", "location_id_partner_site_ids",
        "declared_storage_pv_link", "nearest_other_tech_site_m"])
    return f"""# Data card: registry sites (MaStR)

Export used: `{m['export_file']}` (export date {m['export_date']}). Run configuration: storage threshold
{cfg['storage_threshold_kw']:,.0f} kW ({cfg['storage_power_basis']} power), PV threshold
{cfg['pv_threshold_kw']:,.0f} kW ({cfg['pv_power_basis']} power), site distance {cfg['site_distance_m']:,.0f} m.
Generated by `src/bo/data/registry.py` (`make registry`); do not edit by hand, the file is rewritten on every run.
All quantities here are **observed** (registry data), unless stated otherwise.

{banner}
## 1. Source, licence, attribution

Marktstammdatenregister bulk export, Bundesnetzagentur, licence Datenlizenz Deutschland Namensnennung 2.0
(dl-de/by-2.0). Attribution for anything derived from these tables: "© Bundesnetzagentur,
Marktstammdatenregister, dl-de/by-2.0, data modified (filtered, aggregated, grouped into sites)". The
provider's exact attribution string is still an open question (`docs/research/mastr.md`, open question 4).
OpenStreetMap data (section 9) is ODbL and kept in separate files. Details in `docs/data_sources.md`.
The raw ZIP is never modified. Operator names and operator IDs are not extracted. Coordinates appear
only in `data/processed/registry/`, never in `results/` or `docs/`.

## 2. Coverage of this run (members readable per table)

{_md(mem)}
Tables marked as partly unreadable were skipped member by member: a member that failed to read contributes
no rows at all, never a truncated part. {"**Because core tables are incomplete, all totals below are lower bounds.**" if partial else ""}
Catalogue entries resolved: {m['catalogue_entries']:,}.

## 3. What is in scope

* Battery storage: `Technologie` resolves to "Batterie"; power from `Bruttoleistung` (BNetzA's large-battery
  definition is above 999 kW gross), threshold {cfg['storage_threshold_kw']:,.0f} kW. Pumped hydro and other storage technologies are left out.
* Ground-mounted PV: `ArtDerSolaranlage` resolves to "Freiflächensolaranlage"; the pre-2025 `Lage` value
  "Freifläche" and `SolaranlagenKategorie` are accepted as well (the column used is in `pv_class_source`).
  Power from `Nettonennleistung` (fallback `Bruttoleistung`), threshold {cfg['pv_threshold_kw']:,.0f} kW.
  Landfill and floating PV that the registry classes as ground-mounted cannot be separated by this field.
* Units registered "In Planung" are kept (they are the registry-visible pipeline) and carry `reg_status`.

Units at or above the threshold by class seen in the export (before the technology filter):

{_md(t['technology_classes'])}
Units in scope, by status:

{_md(us)}
## 4. Coordinates

Coordinates are optional in the export and legally withheld only for units up to 30 kW. The Germany check
is a bounding box (latitude 47.0 to 55.2, longitude 5.5 to 15.5), so a point in a neighbouring country or in
the wrong German district passes. Wrong-municipality checks need district polygons and are not done here.
Swapped values are corrected in `lat` and `lon`; the state `swapped` is kept in `coord_state`. Rows with
missing or outside coordinates are kept for the capacity series but get no geometry and are not geocoded.

{_md(cs)}
**Rounded coordinates.** The export pads every coordinate to 6 decimals (`54.300000`), so counting decimals
in the text finds no rounding at all (review M2). Precision is therefore judged on the numeric value: a
coordinate has at most d real decimals if it equals its d-decimal rounding within 5e-7 degrees, and the
coarser of latitude and longitude sets the class `dp1` (0.1 degree), `dp2`, `dp3`, `dp4plus`. A site takes the
coarsest class of its units. `flag_coord_rounded` is set for `dp1` and `dp2` (rounding cell 1 km or coarser);
`dp3` is reported but not flagged. `coord_unc_m` is the half-diagonal of the rounding cell, an upper bound on
the rounding error. A precise coordinate can look rounded by chance, so the class marks likely rounding.
These columns describe registry quality, are on the deny-list of `registry_columns()` and are never features.
Site counts by technology, subtype and class, with the median implied uncertainty, are in
`results/registry/coordinate_precision.csv`. The old text-based decimals histogram stays in
`results/registry/registry_coord_decimals.csv` and is not a rounding measure.
Round-1 queue items on coarse coordinates: `results/labels/queue_coarse_coordinates.csv`.

## 5. Date anomalies, duplicates, units registered before construction

Counts per check (units; share of units in scope for that technology). Dates are in `reg_` columns;
placeholders and unparseable dates become empty (NaT) in the cleaned column and are flagged.
Placeholder rule: the strings 1900-01-01, 1970-01-01, 0001-01-01, 9999-12-31, 2999-12-31, any year at or below 1900
or at or above 2100, and any non-empty text that is not an ISO date.
"Commissioning before registration" is split in two. (a) Units commissioned before the registry opened
(2019-01-31, assumption A18) were necessarily registered later; this is expected. Existing plants commissioned before
2017-07-01 had until 2021-09-30 to register (MaStRV §5(5), as read from gesetze-im-internet.de). (b) Units commissioned
since the opening and registered more than one month later are late registrations under the one-month rule.
Most frequent registration dates in this run:

{_md(t['registration_date_mode'])}
{flag_table}
Duplicate candidates are flagged only when the location IDs differ; identical units under one location ID
(for example one per inverter) are normal. The separate list of deleted and deactivated units
(`GeloeschteUndDeaktivierteEinheiten`, reason "DuplikatDoppelteRegistrierung") is not used yet.

## 6. Site grouping rule

Applied per technology, parameters in `RegistryConfig` (`--site-distance-m`, default {cfg['site_distance_m']:,.0f} m; `--location-link-max-m`):

1. Units with the same `LokationMaStRNummer` are linked when their usable coordinates are within the
   location link distance ({cfg['location_link_max_m']:,.0f} m, `--location-link-max-m`); location members without
   coordinates attach to the first unit of that location. The ID alone is not trusted: in the partial export one
   location ID carried units far apart (`flag_location_split_by_distance` marks such units).
2. Units of the same technology whose usable coordinates are within the site distance are linked
   (single linkage, distances in UTM 32N; chains of close units can grow a site, see `site_extent_m`).
3. Units without location ID and without usable coordinates stay one-unit sites.

Co-location: `colocated_pv` on a storage site means one thing: a ground-mounted PV site from the PV threshold lies within
the co-location distance ({cfg['colocation_distance_m'] if cfg['colocation_distance_m'] is not None else cfg['site_distance_m']:,.0f} m,
`--colocation-distance-m`, default equal to the site distance) of one of its units. `colocated_bess` is the symmetric flag on PV sites.
Other matches never set it and have their own columns: `shares_location_id_other_tech`, `declared_storage_pv_link`
(registry fields naming a joint PV and storage unit) and `nearest_other_tech_site_m`. PV below the threshold or not
ground-mounted is not seen. Breakdown by distance to the nearest site of the other technology (sites with coordinates):

{_md(t['colocation_breakdown'])}
Site ID is `BESS-` or `PV-` plus the smallest unit ID. Site coordinate is the power-weighted centroid of units with usable coordinates.

{_md(ss)}
Site columns: {first_cols}, dates `reg_*_first/last`, and `reg_flag_*_any` / `flag_*_any`.

## 7. Grid operator and voltage level

{grid_txt}

## 8. Monthly capacity series

`results/registry/capacity_monthly_by_state.csv` and `capacity_monthly_national.csv`: stock at month end and
monthly additions by technology and federal state (gross MW, net MW, usable MWh for storage). Rules are in the module
docstring of `src/bo/data/registry_series.py`: the series is reconstructed from the date fields of the current
snapshot (the export keeps no history); planned units are never counted; units without a usable commissioning date
are excluded (table below); final shutdown ends operation, temporary shutdown opens a gap, missing shutdown dates are
imputed with the last update date. Latest month in this run: {last_month} (cut at the export date).
Usable MWh covers only units whose plant record carries a capacity (`units_kwh_known`).

Units left out of the series:

{_md(ex)}
## 9. OSM context

`src/bo/data/osm_features.py` fetches `power=plant` and `power=generator` with solar or battery source and substations
(context only) through Overpass, one cached request per bounding box. No national download has been run yet.
Results are ODbL and live in `data/processed/registry/osm/`, separate from the MaStR tables.

## 10. Comparison with published statistics{" (pending full export)" if partial else ""}

{intro10} Reference values are quoted from `docs/research/bnetza_storage_stats.md`; the code in
`registry_compare.compare_with_statistics` computes our value for the same definition, rebuilt at the reference date
where possible (units registered by that date, commissioned or planned by then). Every row has a comparability verdict and an
explanation. Stock figures also have a backfill sensitivity row; additions count units registered by the reference's data date.
Where two references disagree (battery additions 2025: Battery-Charts 1,244 MWh against Energy-Charts 1,700 MWh) no agreement is claimed.

{_md(show)}
Explanations, row by row:

{explain}

**Would the quarterly snapshot settle the planned figures?** The portal lists a snapshot with Stichtag 2025-10-01
(`docs/research/mastr.md`, fact 3). It would give the status as entered on that date, fourteen days before the
reference Stichtag 2025-10-15, which removes the reconstruction (deletions, status changes) and leaves a 14-day
offset. Its size is not recorded in the repository; the listed neighbours are about 1.2 GB (2023-04-01) and about
3.1 GB (2026-10-01), so expect a few GB. It must be fetched by hand by the author (not downloaded here).

{csv_note}

## 11. Known limitations

* Coordinates are operator-entered; the bounding box cannot catch wrong places inside Germany.
* No status history: past months are reconstructed from dates of the current snapshot.
* The last month is incomplete because of the one-month registration window.
* The registry may withdraw location attributes in future exports (`docs/research/mastr.md`); the schema check fails
  loudly if required fields disappear.
* Registry date and status columns (`reg_*`) must not enter detection or timeline models. Use
  `bo.data.registry.registry_columns(df)` to drop them.
"""
