"""Registry pipeline: battery storage and ground-mounted PV units from the MaStR bulk export.

One command, on the newest export under ``data/raw/mastr/`` or on a given ZIP::

    make registry                      # newest complete export
    make registry EXPORT=path/to.zip   # explicit file (for example a partial preview copy)
    uv run python -m bo.data.registry [path] [--storage-kw 1000] [--pv-kw 1000] [--site-distance-m 300]

What it does (all quantities observed, registry data, licence dl-de/by-2.0, data modified):

1. Streams ``EinheitenStromSpeicher_*.xml`` and ``EinheitenSolar_*.xml`` (UTF-16), keeps battery
   units and ground-mounted PV units above the thresholds. Catalogue IDs are resolved through
   ``Katalogwerte.xml``. A member that cannot be read is skipped whole and listed.
2. Joins usable storage kWh from ``AnlagenStromSpeicher`` and, when readable, grid operator ID
   and voltage level via ``Lokationen`` and ``Netzanschlusspunkte``. Missing members leave the
   columns empty and are reported.
3. Flags coordinate and date problems, groups units into sites (``registry_sites``), writes
   GeoParquet tables to ``data/processed/registry/`` and aggregate CSVs to ``results/registry/``.
4. Builds the monthly capacity series and the comparison with official statistics
   (``registry_series``) and rewrites ``docs/data_card_registry.md``.

Privacy: plant operator names and IDs are never extracted (the grid operator ID of the connection point is, as a public MaStR field; do not hand grid columns to detection or discovery stages). Coordinates go only to
``data/processed``; ``results/`` and ``docs/`` hold aggregates.

Registry dates and statuses are in columns prefixed ``reg_`` so detection code can drop them
with ``registry_columns(df)`` (circularity guard).
"""

from __future__ import annotations

import re
import sys
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from bo import paths
from bo.data import registry_compare as rc
from bo.data import registry_series as rs
from bo.data import registry_sites as rsi
from bo.data.mastr_coords import (
    READ_ERRORS,
    classify_coordinate_precision,
    classify_coordinates,
    find_members,
    iter_rows,
    read_catalogue,
    to_float,
)

MASTR_RAW = paths.RAW / "mastr"
OUT_PROCESSED = paths.PROCESSED / "registry"
OUT_RESULTS = paths.RESULTS / "registry"
DATA_CARD = paths.DOCS / "data_card_registry.md"

TABLES = {
    "storage_units": re.compile(r"^EinheitenStromSpeicher(_\d+)?\.xml$", re.IGNORECASE),
    "solar_units": re.compile(r"^EinheitenSolar(_\d+)?\.xml$", re.IGNORECASE),
    "storage_plants": re.compile(r"^AnlagenStromSpeicher(_\d+)?\.xml$", re.IGNORECASE),
    "locations": re.compile(r"^Lokationen(_\d+)?\.xml$", re.IGNORECASE),
    "grid_connection_points": re.compile(r"^Netzanschlusspunkte(_\d+)?\.xml$", re.IGNORECASE),
}
# A table counts toward "partial" when its members decide the capacity totals.
CORE_TABLES = ("storage_units", "solar_units", "storage_plants")

# Plausibility ranges for the loader checks (observed values outside are flagged, not dropped).
MAX_UNIT_KW = {"battery": 2_000_000.0, "ground_pv": 2_000_000.0}  # 2 GW in one unit
KWH_PER_KW_RANGE = (0.1, 12.0)  # usable energy over gross power, hours
EARLIEST_PLAUSIBLE_YEAR = 1990
REGISTRY_LAUNCH = pd.Timestamp("2019-01-31")  # registry opened; assumptions A18 (BNetzA: January 2019; day: Wikipedia)
LATE_REGISTRATION_DAYS = 31  # operators have one month after commissioning (mastr.md fact 6)
PLACEHOLDER_YEARS = (1900, 2100)  # year <= 1900 or >= 2100 counts as placeholder
PLACEHOLDER_STRINGS = {"1900-01-01", "1970-01-01", "0001-01-01", "9999-12-31", "2999-12-31"}

COMMON_FIELDS = [
    "EinheitMastrNummer", "LokationMaStRNummer", "Bruttoleistung", "Nettonennleistung",
    "EinheitBetriebsstatus", "Registrierungsdatum", "Inbetriebnahmedatum",
    "GeplantesInbetriebnahmedatum", "DatumEndgueltigeStilllegung",
    "DatumBeginnVoruebergehendeStilllegung", "DatumWiederaufnahmeBetrieb",
    "DatumLetzteAktualisierung", "Bundesland", "Landkreis", "Gemeinde", "Gemeindeschluessel",
    "Breitengrad", "Laengengrad",
]
ALLSIZE_FIELDS = ["EinheitMastrNummer", "Bruttoleistung", "Nettonennleistung", "EinheitBetriebsstatus",
                  "Registrierungsdatum", "Inbetriebnahmedatum"]
KIND_FIELDS = {
    "storage": ["Technologie", "Batterietechnologie", "SpeMastrNummer",
                "GemeinsamRegistrierteSolareinheitMastrNummer"],
    "solar": ["ArtDerSolaranlage", "Lage", "SolaranlagenKategorie", "SpeicherAmGleichenOrt"],
}
REQUIRED_FIELDS = ["EinheitMastrNummer", "Bruttoleistung", "EinheitBetriebsstatus",
                   "Registrierungsdatum", "Bundesland"]
CATALOGUE_COLUMNS = {
    "EinheitBetriebsstatus": "reg_status", "Bundesland": "bundesland", "Technologie": "storage_tech",
    "Batterietechnologie": "battery_chemistry", "ArtDerSolaranlage": "pv_art",
    "Lage": "pv_lage", "SolaranlagenKategorie": "pv_kategorie",
}


class SchemaError(RuntimeError):
    """The export does not have the fields this loader needs."""


@dataclass(frozen=True)
class RegistryConfig:
    storage_threshold_kw: float = 1000.0  # assumptions A1
    pv_threshold_kw: float = 1000.0  # assumptions A2
    storage_power_basis: str = "gross"  # BNetzA "Großbatteriespeicher" is > 999 kW gross
    pv_power_basis: str = "net"  # Nettonennleistung, fall back to gross when missing
    site_distance_m: float = 300.0  # assumptions A-registry-1
    location_link_max_m: float = 2000.0  # same location ID links units only within this distance
    colocation_distance_m: float | None = None  # default: site_distance_m

    @property
    def coloc_m(self) -> float:
        return self.site_distance_m if self.colocation_distance_m is None else self.colocation_distance_m


@dataclass
class MemberReport:
    table: str
    members: int = 0
    unreadable: list[str] = field(default_factory=list)
    rows_read: int = 0
    note: str = ""  # for example "not attempted"

    @property
    def readable(self) -> int:
        return self.members - len(self.unreadable)


CAPACITY_COLUMNS = ("gross_kw", "net_kw", "power_kw", "usable_kwh", "usable_kwh_alloc",
                    "usable_kwh_alloc_complete", "storage_plant_n_linked")


# Data-quality columns about the coordinates. They describe the registry, not the image, so they
# must never be model features.
COORD_QUALITY_COLUMNS = {"coord_decimals", "coord_rounded", "coord_precision_class",
                         "coord_unc_m", "flag_coord_rounded", "flag_coord_rounded_any",
                         "coord_coarse_units_excluded"}
# Size, grid and co-location proxies of the site tables: registry-derived, never features (defence in depth).
SITE_PROXY_COLUMNS = {"site_extent_m", "nearest_other_tech_site_m", "voltage_level", "grid_operator_id",
                      "shares_location_id_other_tech", "location_id_partner_site_ids", "declared_storage_pv_link"}
SITE_PROXY_PREFIXES = ("colocated_",)
CAPACITY_DERIVED_PREFIXES = ("flag_power_", "flag_kwh_", "flag_net_gt_gross")
UNIT_COUNT_COLUMNS = {"n_units", "n_units_with_coords", "n_locations"}


def registry_columns(df: pd.DataFrame) -> list[str]:
    """Columns that carry registry dates, status, derived timing or capacity; detection code drops these.

    Capacity counts because KICKOFF 6.4 keeps registry quantities out of model inputs, and so do
    flags and counts derived from capacity or from the number of registered units.

    This is a deny-list and a second line of defence only. Detection and timeline code must build
    its inputs from an explicit allow-list of imagery feature columns (see the ml-engineer brief).
    """
    return [
        c for c in df.columns
        if c.startswith(("reg_", "site_reg_") + CAPACITY_DERIVED_PREFIXES)
        or c in CAPACITY_COLUMNS
        or c in UNIT_COUNT_COLUMNS
        or c in COORD_QUALITY_COLUMNS
        or c in SITE_PROXY_COLUMNS
        or c.startswith(SITE_PROXY_PREFIXES)
    ]


# ---------------------------------------------------------------------------------------
# Streaming helpers


def read_members(zf: zipfile.ZipFile, table: str, row_fn) -> tuple[list, MemberReport]:
    """Apply ``row_fn(row) -> item | None`` to every row of every member of ``table``.

    Items of a member are committed only when the whole member read without error.
    """
    names = find_members(zf, TABLES[table])
    rep = MemberReport(table, members=len(names))
    items: list = []
    for name in names:
        part, n = [], 0
        try:
            with zf.open(name) as fh:
                for row in iter_rows(fh):
                    n += 1
                    got = row_fn(row)
                    if got is not None:
                        part.append(got)
        except READ_ERRORS:
            rep.unreadable.append(name)
            continue
        items.extend(part)
        rep.rows_read += n
    return items, rep


def _lower(row: dict) -> dict:
    return {k.lower(): v for k, v in row.items()}


def export_date_from_name(path: Path) -> pd.Timestamp:
    m = re.search(r"Gesamtdatenexport_(\d{8})", path.name)
    if not m:
        raise ValueError(f"No date in export file name {path.name}")
    return pd.Timestamp(m.group(1))


def newest_export(folder: Path = MASTR_RAW) -> Path:
    """Newest export ZIP by the date in its name. Preview copies are used only if nothing else exists."""
    zips = list(folder.glob("**/Gesamtdatenexport_*.zip"))
    full = [z for z in zips if "preview" not in str(z.relative_to(folder)).lower()]
    pool = full or zips
    if not pool:
        raise FileNotFoundError(f"No Gesamtdatenexport_*.zip under {folder}")
    return max(pool, key=lambda p: (export_date_from_name(p), p.name))


# ---------------------------------------------------------------------------------------
# Extraction


def _is_ground_mounted(art: str, lage: str, kat: str) -> bool:
    return any(str(x).strip().lower().startswith("freifl") for x in (art, lage, kat) if x)


def extract_units(
    zf: zipfile.ZipFile, kind: str, catalogue: dict[str, str], cfg: RegistryConfig
) -> tuple[pd.DataFrame, MemberReport, Counter, set[str], pd.DataFrame]:
    """Return raw units of ``kind`` ("storage" or "solar") that pass technology and power filters.

    The power filter here is the loose one (gross or net at or above the threshold); the strict
    basis is applied in ``build_units``. Also returns a Counter of technology classes seen above
    the threshold, the set of field names seen (for the schema check), and for solar a small table
    of ALL ground-mounted units of any size commissioned since 2025-01-01 (columns in
    ``ALLSIZE_FIELDS``), used only for the all-size comparison with published PV additions.
    """
    table = f"{kind}_units"
    thr = cfg.storage_threshold_kw if kind == "storage" else cfg.pv_threshold_kw
    fields = COMMON_FIELDS + KIND_FIELDS[kind]
    lower_to_field = {f.lower(): f for f in fields}
    classes: Counter = Counter()
    seen: set[str] = set()

    def cat(v):
        return catalogue.get(str(v).strip(), str(v).strip()) if v else ""

    def row_fn(row):
        if len(seen) < 120:
            seen.update(row)
        gross, net = to_float(row.get("Bruttoleistung")), to_float(row.get("Nettonennleistung"))
        if max(gross or 0.0, net or 0.0) < thr:
            if kind == "solar" and (row.get("Inbetriebnahmedatum") or "")[:4] >= "2025" and _is_ground_mounted(
                    cat(row.get("ArtDerSolaranlage")), cat(row.get("Lage")), cat(row.get("SolaranlagenKategorie"))):
                return {"_allsize": True, **{f: row.get(f) for f in ALLSIZE_FIELDS}}
            return None
        r = {lower_to_field[k.lower()]: v for k, v in row.items() if k.lower() in lower_to_field}
        if kind == "storage":
            tech = cat(r.get("Technologie"))
            classes[tech or "(missing)"] += 1
            if not tech.lower().startswith("batterie"):
                return None
        else:
            art, lage, kat = cat(r.get("ArtDerSolaranlage")), cat(r.get("Lage")), cat(r.get("SolaranlagenKategorie"))
            classes[f"{art or '-'} | {kat or '-'} | {lage or '-'}"] += 1
            if not _is_ground_mounted(art, lage, kat):
                return None
        return r

    items, rep = read_members(zf, table, row_fn)
    small = [i for i in items if "_allsize" in i]
    big = [i for i in items if "_allsize" not in i]
    df = pd.DataFrame(big, columns=fields)
    allsize = pd.concat([
        pd.DataFrame(small).drop(columns="_allsize", errors="ignore"),
        df.reindex(columns=ALLSIZE_FIELDS),
    ], ignore_index=True) if kind == "solar" else pd.DataFrame(columns=ALLSIZE_FIELDS)
    return df, rep, classes, seen, allsize


def check_schema(seen: set[str], kind: str, rep: MemberReport) -> None:
    """Fail loudly when the readable members lack required fields."""
    if rep.readable == 0:
        raise SchemaError(f"No readable member for {kind} units; cannot build the registry")
    low = {s.lower() for s in seen}
    missing = [f for f in REQUIRED_FIELDS if f.lower() not in low]
    if kind == "storage" and "technologie" not in low:
        missing.append("Technologie")
    if kind == "solar" and not ({"artdersolaranlage", "lage", "solaranlagenkategorie"} & low):
        missing.append("ArtDerSolaranlage/Lage/SolaranlagenKategorie")
    if missing:
        raise SchemaError(f"{kind} units: required fields missing from the export: {missing}")


def extract_storage_plants(
    zf: zipfile.ZipFile, spe_ids: set[str]
) -> tuple[pd.DataFrame, MemberReport]:
    """Usable kWh and linked unit IDs per storage plant (SPE...), for the wanted plants only."""

    def row_fn(row):
        r = _lower(row)
        pid = r.get("mastrnummer")
        if pid not in spe_ids:
            return None
        linked = [x for x in re.split(r"[,;\s]+", r.get("verknuepfteeinheitenmastrnummern", "")) if x]
        return {"spe_id": pid, "plant_kwh": to_float(r.get("nutzbarespeicherkapazitaet")),
                "linked_units": linked, "plant_status_id": r.get("anlagebetriebsstatus")}

    items, rep = read_members(zf, "storage_plants", row_fn)
    return pd.DataFrame(items, columns=["spe_id", "plant_kwh", "linked_units", "plant_status_id"]), rep


def extract_linked_gross(zf: zipfile.ZipFile, unit_ids: set[str]) -> dict[str, float]:
    """Gross power (kW) of the given storage units, read from all readable storage members."""

    def row_fn(row):
        uid = row.get("EinheitMastrNummer")
        return (uid, to_float(row.get("Bruttoleistung"))) if uid in unit_ids else None

    items, _ = read_members(zf, "storage_units", row_fn)
    return dict(items)


def allocate_kwh(units: pd.DataFrame, plants: pd.DataFrame, linked_gross: dict[str, float]) -> pd.DataFrame:
    """Attach plant kWh to storage units; split across linked units by gross power.

    A plant with one linked unit gives its kWh to that unit. With several linked units the plant
    kWh is split in proportion to gross power over the linked units found in the export
    (``usable_kwh_alloc_complete`` is False when some linked unit could not be read).
    """
    u = units.copy()
    u["usable_kwh"] = np.nan
    u["usable_kwh_alloc"] = np.nan
    u["storage_plant_n_linked"] = pd.array([pd.NA] * len(u), dtype="Int64")
    u["usable_kwh_alloc_complete"] = pd.array([pd.NA] * len(u), dtype="boolean")
    if plants.empty or u.empty:
        return u
    p = plants.drop_duplicates("spe_id").set_index("spe_id")
    st = u["technology"] == "battery"
    spe = u["spe_id"].where(st)
    plant_kwh = spe.map(p["plant_kwh"])
    n_linked = spe.map(p["linked_units"].map(len))
    u["usable_kwh"] = plant_kwh.where(plant_kwh > 0)
    u["storage_plant_n_linked"] = n_linked.astype("Int64")
    alloc = u["usable_kwh"].copy()
    complete = pd.Series(pd.NA, index=u.index, dtype="boolean")
    complete[u["usable_kwh"].notna()] = True
    for i in u.index[n_linked.fillna(0) > 1]:
        if pd.isna(u.at[i, "usable_kwh"]):
            continue
        links = p.at[u.at[i, "spe_id"], "linked_units"]
        w = {x: linked_gross.get(x) for x in links}
        found = {k: v for k, v in w.items() if v is not None}
        tot = sum(found.values())
        mine = w.get(u.at[i, "unit_id"])
        alloc[i] = u.at[i, "usable_kwh"] * (mine / tot) if tot > 0 and mine else u.at[i, "usable_kwh"] / len(links)
        complete[i] = len(found) == len(links)
    u["usable_kwh_alloc"] = alloc
    u["usable_kwh_alloc_complete"] = complete
    return u


def extract_grid(
    zf: zipfile.ZipFile, location_ids: set[str], catalogue: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, MemberReport]]:
    """Grid operator ID and voltage level per location via Lokationen -> Netzanschlusspunkte.

    Field names follow ``docs/research/mastr.md`` and are matched case-insensitively; they could
    not be checked against the data while these members were unreadable. Both tables must be
    fully readable, otherwise the result is empty so no half-joined values appear.
    """

    def loc_fn(row):
        r = _lower(row)
        lid = r.get("mastrnummer")
        if lid not in location_ids:
            return None
        pts = [x for x in re.split(r"[,;\s]+", r.get("netzanschlusspunktemastrnummern", "")) if x]
        return {"location_id": lid, "point_ids": pts} if pts else None

    locs, rep_l = read_members(zf, "locations", loc_fn)
    reports = {"locations": rep_l}
    empty = pd.DataFrame(columns=["location_id", "grid_operator_id", "voltage_level"])
    if rep_l.unreadable or rep_l.members == 0:
        n = len(find_members(zf, TABLES["grid_connection_points"]))
        reports["grid_connection_points"] = MemberReport(
            "grid_connection_points", members=n, note="not attempted (Lokationen incomplete)")
        return empty, reports
    wanted = {p for r in locs for p in r["point_ids"]}

    def pt_fn(row):
        r = _lower(row)
        # The export of 16.11.2026 names the point ID "NetzanschlusspunktMastrNummer";
        # "MastrNummer" is kept as a fallback for older or synthetic exports.
        pid = r.get("netzanschlusspunktmastrnummer") or r.get("mastrnummer")
        if pid not in wanted:
            return None
        v = r.get("spannungsebene")
        return {"point_id": pid,
                "grid_operator_id": r.get("netzbetreibermastrnummer") or r.get("netzmastrnummer"),
                "voltage_level": catalogue.get(str(v).strip(), str(v).strip()) if v else None}

    pts, rep_p = read_members(zf, "grid_connection_points", pt_fn)
    reports["grid_connection_points"] = rep_p
    if rep_p.unreadable or rep_p.members == 0:
        return empty, reports
    pt = pd.DataFrame(pts, columns=["point_id", "grid_operator_id", "voltage_level"]).drop_duplicates("point_id")
    pt = pt.set_index("point_id")
    recs = []
    for r in locs:
        sub = pt.reindex(r["point_ids"]).dropna(how="all")
        if sub.empty:
            continue
        ops = sub["grid_operator_id"].dropna().unique()
        recs.append({"location_id": r["location_id"],
                     "grid_operator_id": ops[0] if len(ops) else None,
                     "voltage_level": ";".join(sorted({str(v) for v in sub["voltage_level"].dropna()})) or None})
    return pd.DataFrame(recs, columns=empty.columns), reports


# ---------------------------------------------------------------------------------------
# Cleaning, checks, flags


def parse_dates(raw: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse ISO dates. Returns ``(date, placeholder)``; placeholders and unparseable text become NaT."""
    txt = raw.astype("string").fillna("").str.strip().str[:10].astype(object)
    parsed = pd.to_datetime(txt, format="%Y-%m-%d", errors="coerce")
    present = txt != ""
    year = parsed.dt.year
    placeholder = present & (
        txt.isin(PLACEHOLDER_STRINGS) | parsed.isna() | (year <= PLACEHOLDER_YEARS[0]) | (year >= PLACEHOLDER_YEARS[1])
    )
    parsed = parsed.mask(placeholder)
    return parsed, placeholder


def build_units(
    raw: pd.DataFrame, catalogue: dict[str, str], cfg: RegistryConfig, export_date: pd.Timestamp
) -> pd.DataFrame:
    """Typed, flagged unit table from the raw extraction (storage and PV stacked)."""
    u = raw.copy()
    for col, new in CATALOGUE_COLUMNS.items():
        if col in u:
            u[new] = u[col].map(lambda v: None if pd.isna(v) or v == "" else catalogue.get(str(v).strip(), str(v).strip()))
        else:
            u[new] = None
    u = u.rename(columns={"EinheitMastrNummer": "unit_id", "LokationMaStRNummer": "location_id",
                          "Landkreis": "landkreis", "Gemeinde": "gemeinde",
                          "Gemeindeschluessel": "gemeindeschluessel", "SpeMastrNummer": "spe_id",
                          "SpeicherAmGleichenOrt": "pv_declares_storage_same_site",
                          "GemeinsamRegistrierteSolareinheitMastrNummer": "storage_pv_unit_link"})
    u["location_id"] = u["location_id"].fillna("")
    u["gross_kw"] = u["Bruttoleistung"].map(to_float)
    u["net_kw"] = u["Nettonennleistung"].map(to_float)
    storage = u["technology"] == "battery"
    basis_gross = np.where(storage, cfg.storage_power_basis == "gross", cfg.pv_power_basis == "gross")
    u["power_kw"] = np.where(basis_gross, u["gross_kw"].fillna(u["net_kw"]), u["net_kw"].fillna(u["gross_kw"]))
    thr = np.where(storage, cfg.storage_threshold_kw, cfg.pv_threshold_kw)
    u = u[u["power_kw"] >= thr].copy()
    u["pv_class_source"] = np.where(
        u["technology"] == "ground_pv",
        np.select([u["pv_art"].fillna("").str.lower().str.startswith("freifl"),
                   u["pv_kategorie"].fillna("").str.lower().str.startswith("freifl")],
                  ["ArtDerSolaranlage", "SolaranlagenKategorie"], default="Lage"),
        "",
    )

    # coordinates
    c = classify_coordinates(u[["Breitengrad", "Laengengrad"]])
    u["coord_state"], u["coord_decimals"] = c["coord_state"], c["coord_decimals"]
    u["lat_raw"], u["lon_raw"] = c["lat"], c["lon"]
    sw = u["coord_state"] == "swapped"
    u["lat"] = u["lat_raw"].where(~sw, u["lon_raw"])
    u["lon"] = u["lon_raw"].where(~sw, u["lat_raw"])
    u.loc[~u["coord_state"].isin(["ok", "swapped"]), ["lat", "lon"]] = np.nan
    # rounding is judged on the numeric value: the export pads to 6 decimals ("54.300000")
    prec = classify_coordinate_precision(u["lat"], u["lon"])
    u["coord_precision_class"], u["coord_unc_m"] = prec["coord_precision_class"], prec["coord_unc_m"]
    u["coord_rounded"] = u["coord_precision_class"].isin(["dp1", "dp2"])

    # dates, all registry dates prefixed
    date_cols = {
        "Registrierungsdatum": "registration", "Inbetriebnahmedatum": "commissioning",
        "GeplantesInbetriebnahmedatum": "planned_commissioning",
        "DatumEndgueltigeStilllegung": "shutdown_final", "DatumBeginnVoruebergehendeStilllegung": "shutdown_temp_begin",
        "DatumWiederaufnahmeBetrieb": "resumption",
    }
    for src, name in date_cols.items():
        d, ph = parse_dates(u[src] if src in u else pd.Series("", index=u.index))
        u[f"reg_{name}_date"] = d
        u[f"reg_flag_{name}_placeholder"] = ph
    u["reg_last_update"] = pd.to_datetime(u["DatumLetzteAktualisierung"].fillna("").astype(str).str[:10],
                                          format="%Y-%m-%d", errors="coerce")
    reg, com, plan = u["reg_registration_date"], u["reg_commissioning_date"], u["reg_planned_commissioning_date"]
    status = u["reg_status"]
    u["reg_flag_commissioning_before_1990"] = com.dt.year < EARLIEST_PLAUSIBLE_YEAR
    u["reg_flag_commissioning_future"] = com > export_date
    u["reg_flag_registration_future"] = reg > export_date
    # (a) expected: the registry did not exist yet, so registration necessarily came later
    u["reg_flag_commissioned_before_registry_opened"] = com < REGISTRY_LAUNCH
    # (b) anomaly: commissioned after the registry opened, registered later than the one-month rule allows
    u["reg_flag_registration_at_launch_date"] = reg <= REGISTRY_LAUNCH
    u["reg_flag_late_registration"] = ((reg - com).dt.days > LATE_REGISTRATION_DAYS) & (com >= REGISTRY_LAUNCH)
    u["reg_flag_registered_before_commissioning"] = reg < com
    u["reg_flag_operating_without_commissioning_date"] = (status == rs.STATUS_OPERATING) & com.isna()
    u["reg_flag_planned_date_in_past"] = (status == rs.STATUS_PLANNED) & (plan < export_date)
    u["reg_flag_planned_without_date"] = (status == rs.STATUS_PLANNED) & plan.isna()
    u["reg_flag_planned_with_past_commissioning_date"] = (status == rs.STATUS_PLANNED) & (com < export_date)
    u["reg_flag_registered_in_planning_stage"] = status == rs.STATUS_PLANNED

    # range checks
    u["flag_coord_missing"] = u["coord_state"] == "missing"
    u["flag_coord_outside_germany"] = u["coord_state"] == "outside"
    u["flag_coord_swapped"] = sw
    u["flag_coord_rounded"] = u["coord_rounded"]
    u["flag_power_missing"] = u["gross_kw"].isna() | u["net_kw"].isna()
    u["flag_power_implausible"] = u["gross_kw"] > u["technology"].map(MAX_UNIT_KW)
    u["flag_net_gt_gross"] = u["net_kw"] > u["gross_kw"] * 1.001
    return u.reset_index(drop=True)


def add_storage_checks(u: pd.DataFrame) -> pd.DataFrame:
    u = u.copy()
    hours = u["usable_kwh"] / u["gross_kw"]
    lo, hi = KWH_PER_KW_RANGE
    st = u["technology"] == "battery"
    u["flag_kwh_missing"] = st & u["usable_kwh"].isna()
    u["flag_kwh_implausible_duration"] = st & hours.notna() & ((hours < lo) | (hours > hi))
    return u


def flag_duplicates(u: pd.DataFrame) -> pd.DataFrame:
    """Duplicate unit IDs, and candidate duplicate registrations.

    Candidate: same technology, coordinates equal at 5 decimals (about 1 m), same gross and net
    power, same registration and commissioning dates, but a *different* location ID. Several
    identical units under one location ID are legitimate (one per inverter) and not flagged.
    """
    u = u.copy()
    u["flag_duplicate_unit_id"] = u.duplicated("unit_id", keep=False)
    key = ["technology", "gross_kw", "net_kw", "reg_registration_date", "reg_commissioning_date"]
    have = u["lat"].notna()
    k = u.loc[have, key].assign(la=u.loc[have, "lat"].round(5), lo=u.loc[have, "lon"].round(5),
                                loc=u.loc[have, "location_id"])
    g = k.groupby(key + ["la", "lo"], dropna=False)["loc"]
    u["flag_duplicate_candidate"] = False
    u.loc[have, "flag_duplicate_candidate"] = ((g.transform("size") > 1) & (g.transform("nunique") > 1)).to_numpy()
    return u


# ---------------------------------------------------------------------------------------
# Orchestration


@dataclass
class RunResult:
    units: pd.DataFrame
    sites: pd.DataFrame
    monthly: pd.DataFrame
    meta: dict
    tables: dict[str, pd.DataFrame]


def extract_all(zip_path: Path, cfg: RegistryConfig):
    with zipfile.ZipFile(zip_path) as zf:
        catalogue = read_catalogue(zf)
        if not catalogue:
            raise SchemaError("Katalogwerte.xml is not readable; catalogue IDs cannot be resolved")
        reports: dict[str, MemberReport] = {}
        frames, classes = [], {}
        for kind in ("storage", "solar"):
            df, rep, cl, seen, allsize = extract_units(zf, kind, catalogue, cfg)
            if kind == "solar":
                pv_allsize = allsize
            check_schema(seen, kind, rep)
            df["technology"] = "battery" if kind == "storage" else "ground_pv"
            frames.append(df)
            reports[f"{kind}_units"] = rep
            classes[kind] = cl
        raw = pd.concat(frames, ignore_index=True)
        spe_ids = set(raw.loc[raw["technology"] == "battery", "SpeMastrNummer"].dropna())
        plants, reports["storage_plants"] = extract_storage_plants(zf, spe_ids)
        multi = {x for ids in plants["linked_units"] if len(ids) > 1 for x in ids} if len(plants) else set()
        linked_gross = extract_linked_gross(zf, multi) if multi else {}
        loc_ids = set(raw["LokationMaStRNummer"].dropna()) - {""}
        grid, grid_reports = extract_grid(zf, loc_ids, catalogue)
        reports.update(grid_reports)
        for t, pattern in TABLES.items():
            reports.setdefault(t, MemberReport(t, members=len(find_members(zf, pattern))))
    return catalogue, raw, plants, linked_gross, grid, reports, classes, pv_allsize


def run(zip_path: Path | None = None, cfg: RegistryConfig | None = None, write: bool = True) -> RunResult:
    from bo.data import registry_report  # local import keeps the report code out of the loader path

    cfg = cfg or RegistryConfig()
    zip_path = Path(zip_path) if zip_path else newest_export()
    export_date = export_date_from_name(zip_path)
    catalogue, raw, plants, linked_gross, grid, reports, classes, pv_allsize = extract_all(zip_path, cfg)

    units = build_units(raw.rename(columns={}), catalogue, cfg, export_date)
    units = allocate_kwh(units, plants, linked_gross)
    units = add_storage_checks(units)
    grid_ok = not grid.empty
    units = units.merge(grid, how="left", on="location_id") if grid_ok else units.assign(
        grid_operator_id=None, voltage_level=None)
    units = flag_duplicates(units)
    units = units.drop(columns=[c for c in units.columns if c in raw.columns and c not in (
        "technology",)], errors="ignore")
    units = rs.operation_intervals(units)

    units, sites = rsi.build_sites(units, cfg.site_distance_m, cfg.coloc_m, cfg.location_link_max_m)
    is_partial = any(reports[t].unreadable for t in CORE_TABLES)
    units["data_partial"] = is_partial
    sites["data_partial"] = is_partial
    sites["quantity_type"] = "observed"
    units["quantity_type"] = "observed"
    monthly = rs.monthly_capacity(units, export_date)
    comparison = rc.compare_with_statistics(units, export_date, is_partial, grid_ok, catalogue, pv_allsize)

    meta = {
        "export_file": zip_path.name, "export_date": export_date.date().isoformat(),
        "is_partial": is_partial, "grid_join_available": grid_ok, "config": asdict(cfg),
        "reports": reports, "classes": classes, "catalogue_entries": len(catalogue),
    }
    tables = registry_report.summary_tables(units, sites, monthly, comparison, meta)
    result = RunResult(units, sites, monthly, meta, tables)
    if write:
        registry_report.write_outputs(result, OUT_PROCESSED, OUT_RESULTS)
        registry_report.write_data_card(result, DATA_CARD)
    return result


def main(argv: list[str]) -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("export", nargs="?", help="path to a Gesamtdatenexport ZIP (default: newest)")
    ap.add_argument("--storage-kw", type=float, default=RegistryConfig.storage_threshold_kw)
    ap.add_argument("--pv-kw", type=float, default=RegistryConfig.pv_threshold_kw)
    ap.add_argument("--site-distance-m", type=float, default=RegistryConfig.site_distance_m)
    ap.add_argument("--colocation-distance-m", type=float, default=None,
                    help="storage/PV co-location distance (default: site distance)")
    ap.add_argument("--location-link-max-m", type=float, default=RegistryConfig.location_link_max_m)
    a = ap.parse_args(argv[1:])
    cfg = RegistryConfig(a.storage_kw, a.pv_kw, site_distance_m=a.site_distance_m, colocation_distance_m=a.colocation_distance_m,
                         location_link_max_m=a.location_link_max_m)
    path = Path(a.export) if a.export else None
    res = run(path, cfg)
    m = res.meta
    print(f"export {m['export_file']}  partial={m['is_partial']}  grid_join={m['grid_join_available']}")
    for t, r in m["reports"].items():
        print(f"  {t}: {r.note or f'{r.readable}/{r.members} members readable'}")
    print(res.tables["sites_summary"].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv)
