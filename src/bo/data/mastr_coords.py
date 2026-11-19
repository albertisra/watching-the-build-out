"""Coordinate completeness of large units in the MaStR bulk export (risk R1).

Reads the ``Gesamtdatenexport`` ZIP as downloaded by hand from the MaStR download
portal, streams the storage and solar unit files, keeps only units at or above a
power threshold, and reports how many of them carry usable coordinates.

All quantities produced here are *observed* (registry data).

Usage::

    uv run python -m bo.data.mastr_coords            # newest ZIP in data/raw/mastr/
    uv run python -m bo.data.mastr_coords path/to/Gesamtdatenexport_....zip

Field names follow ``docs/research/mastr.md``. Catalogue IDs are resolved through
``Katalogwerte.xml``; nothing is assumed about their numeric values.
"""

from __future__ import annotations

import math
import re
import sys
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from bo import paths

MASTR_RAW = paths.RAW / "mastr"
OUT_DIR = paths.RESULTS / "registry"
UNITS_OUT = paths.PROCESSED / "registry"

THRESHOLD_KW = 1000.0  # assumptions A1, A2
SIZE_BINS_KW = [1_000, 5_000, 10_000, 50_000, 100_000, float("inf")]
SIZE_LABELS = ["1-5 MW", "5-10 MW", "10-50 MW", "50-100 MW", ">=100 MW"]

# Generous bounding box for Germany, used only as a sanity check.
LAT_RANGE = (47.0, 55.2)
LON_RANGE = (5.5, 15.5)

UNIT_FILES = {
    "storage": re.compile(r"^EinheitenStromSpeicher(_\d+)?\.xml$", re.IGNORECASE),
    "solar": re.compile(r"^EinheitenSolar(_\d+)?\.xml$", re.IGNORECASE),
}
CATALOGUE_FILE = re.compile(r"^Katalogwerte(_\d+)?\.xml$", re.IGNORECASE)

FIELDS = [
    "EinheitMastrNummer",
    "LokationMaStRNummer",
    "Bruttoleistung",
    "Nettonennleistung",
    "EinheitBetriebsstatus",
    "Registrierungsdatum",
    "Inbetriebnahmedatum",
    "GeplantesInbetriebnahmedatum",
    "Bundesland",
    "Breitengrad",
    "Laengengrad",
    "Technologie",  # storage only
    "ArtDerSolaranlage",  # solar only (current schema)
    "Lage",  # solar only (schema before 01.10.2025, kept in case it is still exported)
]
CATALOGUE_FIELDS = ["EinheitBetriebsstatus", "Bundesland", "Technologie", "ArtDerSolaranlage", "Lage"]


def to_float(text: str | None) -> float | None:
    """Parse a decimal that may use a comma or a point. Empty or invalid gives None."""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return None
    s = str(text).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def iter_rows(fh) -> Iterator[dict[str, str]]:
    """Yield one dict per record: the direct children of the XML root.

    Streams with ``iterparse`` and frees each record, so memory stays flat on
    files with millions of rows. The XML declaration carries the encoding (UTF-16).
    """
    depth = 0
    for event, elem in ET.iterparse(fh, events=("start", "end")):
        if event == "start":
            depth += 1
        else:
            depth -= 1
            if depth == 1:
                yield {child.tag: (child.text or "") for child in elem}
                elem.clear()


def find_members(zf: zipfile.ZipFile, pattern: re.Pattern) -> list[str]:
    return sorted(n for n in zf.namelist() if pattern.match(Path(n).name))


def read_catalogue(zf: zipfile.ZipFile) -> dict[str, str]:
    """Map catalogue value ID to its text. Empty if the file is absent."""
    out: dict[str, str] = {}
    for name in find_members(zf, CATALOGUE_FILE):
        with zf.open(name) as fh:
            for row in iter_rows(fh):
                if row.get("Id") and "Wert" in row:
                    out[row["Id"].strip()] = row["Wert"].strip()
    return out


READ_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, ET.ParseError)


def read_large_units(
    zf: zipfile.ZipFile, kind: str, threshold_kw: float = THRESHOLD_KW
) -> tuple[pd.DataFrame, int, list[str]]:
    """Return units of ``kind`` with gross or net power >= threshold, the row count read,
    and the members that could not be read.

    A member that fails to read (for example a part of a partially downloaded archive
    that is still missing) contributes no rows at all, never a truncated part, and is
    listed so the result can be reported as incomplete.
    """
    rows, total, unreadable = [], 0, []
    for name in find_members(zf, UNIT_FILES[kind]):
        member_rows, member_total = [], 0
        try:
            with zf.open(name) as fh:
                for row in iter_rows(fh):
                    member_total += 1
                    gross = to_float(row.get("Bruttoleistung"))
                    net = to_float(row.get("Nettonennleistung"))
                    if max(gross or 0.0, net or 0.0) >= threshold_kw:
                        member_rows.append({f: row.get(f) for f in FIELDS})
        except READ_ERRORS:
            unreadable.append(name)
            continue
        rows.extend(member_rows)
        total += member_total
    df = pd.DataFrame(rows, columns=FIELDS)
    df.insert(0, "kind", kind)
    return df, total, unreadable


def classify_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Add numeric coordinates and a ``coord_state`` column.

    States: ``ok`` (inside the Germany box), ``swapped`` (inside the box only after
    swapping latitude and longitude), ``outside`` (present but implausible), ``missing``.
    Also adds ``coord_decimals``: the number of decimals of the coarser coordinate as
    exported, a rough indicator of rounding.
    """
    df = df.copy()
    lat = df["Breitengrad"].map(to_float)
    lon = df["Laengengrad"].map(to_float)
    df["lat"], df["lon"] = lat, lon

    def in_box(a, b):
        return a.between(*LAT_RANGE) & b.between(*LON_RANGE)

    state = pd.Series("outside", index=df.index)
    state[in_box(lon, lat)] = "swapped"
    state[in_box(lat, lon)] = "ok"
    state[lat.isna() | lon.isna()] = "missing"
    df["coord_state"] = state

    def decimals(text):
        if to_float(text) is None:
            return None
        s = str(text).strip().replace(",", ".")
        return len(s.split(".")[1]) if "." in s else 0

    d = pd.concat([df["Breitengrad"].map(decimals), df["Laengengrad"].map(decimals)], axis=1)
    df["coord_decimals"] = d.min(axis=1)
    return df


PRECISION_CLASSES = ["dp1", "dp2", "dp3", "dp4plus"]  # coarsest to finest
PRECISION_TOL_DEG = 5e-7  # export text has 6 decimals, so a rounded value is exact to within 5e-7
_DEG_M = 111_320.0


def _step_decimals(x: pd.Series, tol: float) -> pd.Series:
    """Smallest d in 1..4 with |x - round(x, d)| <= tol; 5 if none. NaN stays NaN."""
    out = pd.Series(5.0, index=x.index)
    for d in (4, 3, 2, 1):  # coarser decimals overwrite finer ones
        out[(x - x.round(d)).abs() <= tol] = float(d)
    out[x.isna()] = float("nan")
    return out


def classify_coordinate_precision(lat: pd.Series, lon: pd.Series, tol: float = PRECISION_TOL_DEG) -> pd.DataFrame:
    """Precision class from the numeric value, not from the export text.

    A coordinate has at most d real decimals when it equals its d-decimal rounding within ``tol``
    (the export pads to 6 decimals, so ``54.300000`` is a 1-decimal value). The class is set by the
    coarser of latitude and longitude: ``dp1`` (step 0.1 deg), ``dp2`` (0.01), ``dp3`` (0.001),
    ``dp4plus`` (finer than 0.001). Missing coordinates give NaN class.

    ``coord_unc_m`` is the half-diagonal of the rounding cell, 0.5 * 10**-d deg in latitude and
    scaled by cos(lat) in longitude; for ``dp4plus`` it is the 4-decimal value (about 8 m) as a
    floor, not a measurement. A round value can also be a genuinely precise coordinate by chance
    (1 in 10**k), so this is an upper bound on the rounding error, flagged as likely, not proven.
    """
    lat, lon = pd.to_numeric(lat, errors="coerce"), pd.to_numeric(lon, errors="coerce")
    d = pd.concat([_step_decimals(lat, tol), _step_decimals(lon, tol)], axis=1).min(axis=1, skipna=False)
    d = d.clip(upper=4)
    cls = d.map({1.0: "dp1", 2.0: "dp2", 3.0: "dp3", 4.0: "dp4plus"})
    half = 0.5 * 10.0 ** (-d)
    unc = _DEG_M * half * np.sqrt(1.0 + np.cos(np.radians(lat)) ** 2)
    return pd.DataFrame({"coord_precision_class": cls, "coord_unc_m": unc.round(0)})


def add_classes(df: pd.DataFrame, catalogue: dict[str, str]) -> pd.DataFrame:
    """Resolve catalogue IDs to text and add power and size-class columns."""
    df = df.copy()
    for col in CATALOGUE_FIELDS:
        df[col + "_text"] = df[col].map(
            lambda v: None if pd.isna(v) else catalogue.get(str(v).strip(), str(v).strip())
        )
    gross = df["Bruttoleistung"].map(to_float)
    net = df["Nettonennleistung"].map(to_float)
    df["gross_kw"], df["net_kw"] = gross, net
    # Storage is classed by gross power (BNetzA convention), solar by net power; see mastr.md.
    power = gross.where(df["kind"] == "storage", net.fillna(gross)).fillna(gross)
    df["power_kw"] = power
    df["size_class"] = pd.cut(power, bins=SIZE_BINS_KW, labels=SIZE_LABELS, right=False)
    art = df["ArtDerSolaranlage_text"].fillna("").str.lower()
    lage = df["Lage_text"].fillna("").str.lower()
    tech = df["Technologie_text"].fillna("").str.lower()
    sub = pd.Series("other", index=df.index)
    sub[(df["kind"] == "solar") & (art.str.startswith("freifl") | lage.str.startswith("freifl"))] = (
        "ground-mounted"
    )
    sub[(df["kind"] == "storage") & tech.str.contains("batterie")] = "battery"
    df["subtype"] = sub
    return df


def completeness(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Counts and capacity by coordinate state for each group in ``by``."""
    g = df.groupby(by, observed=True)
    out = g.agg(
        units=("EinheitMastrNummer", "size"),
        capacity_mw=("power_kw", lambda s: s.sum() / 1000.0),
    )
    for st in ("ok", "swapped", "outside", "missing"):
        mask = df["coord_state"] == st
        out[f"units_{st}"] = df[mask].groupby(by, observed=True).size()
        out[f"mw_{st}"] = df[mask].groupby(by, observed=True)["power_kw"].sum() / 1000.0
    out = out.fillna(0)
    out["share_units_ok"] = out["units_ok"] / out["units"]
    out["share_mw_ok"] = out["mw_ok"] / out["capacity_mw"]
    return out.reset_index()


def newest_zip(folder: Path = MASTR_RAW) -> Path:
    zips = sorted(folder.glob("**/Gesamtdatenexport*.zip"))
    if not zips:
        raise FileNotFoundError(
            f"No Gesamtdatenexport*.zip under {folder}. Download it by hand from "
            "https://www.marktstammdatenregister.de/MaStR/Datendownload and put it there."
        )
    return zips[-1]


def run(zip_path: Path | None = None) -> dict[str, pd.DataFrame]:
    zip_path = Path(zip_path) if zip_path else newest_zip()
    with zipfile.ZipFile(zip_path) as zf:
        catalogue = read_catalogue(zf)
        frames, totals, unreadable, members = [], {}, {}, {}
        for kind, pattern in UNIT_FILES.items():
            df, totals[kind], unreadable[kind] = read_large_units(zf, kind)
            members[kind] = len(find_members(zf, pattern))
            frames.append(df)
    units = add_classes(classify_coordinates(pd.concat(frames, ignore_index=True)), catalogue)

    tables = {
        "coordinate_completeness_by_subtype": completeness(units, ["kind", "subtype"]),
        "coordinate_completeness_by_size": completeness(units, ["kind", "subtype", "size_class"]),
        "coordinate_completeness_by_status": completeness(
            units, ["kind", "subtype", "EinheitBetriebsstatus_text"]
        ),
        "coordinate_decimals": (
            units[units["coord_state"] == "ok"]
            .groupby(["kind", "subtype", "coord_decimals"], observed=True)
            .size()
            .rename("units")
            .reset_index()
        ),
    }
    meta = pd.DataFrame(
        [
            {"key": "export_file", "value": zip_path.name},
            {"key": "threshold_kw", "value": THRESHOLD_KW},
            {"key": "catalogue_entries", "value": len(catalogue)},
            *[{"key": f"total_rows_{k}", "value": v} for k, v in totals.items()],
            *[{"key": f"files_{k}", "value": v} for k, v in members.items()],
            *[{"key": f"files_unreadable_{k}", "value": len(v)} for k, v in unreadable.items()],
            *[
                {"key": f"unreadable_{k}", "value": ";".join(v)}
                for k, v in unreadable.items()
                if v
            ],
            *[
                {"key": f"rows_ge_threshold_{k}", "value": int((units["kind"] == k).sum())}
                for k in UNIT_FILES
            ],
        ]
    )
    tables["coordinate_completeness_meta"] = meta

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(OUT_DIR / f"{name}.csv", index=False)
    UNITS_OUT.mkdir(parents=True, exist_ok=True)
    units.to_parquet(UNITS_OUT / "units_ge_threshold.parquet", index=False)
    return tables


def main(argv: list[str]) -> None:
    tables = run(Path(argv[1]) if len(argv) > 1 else None)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    for name, table in tables.items():
        print(f"\n== {name} ==\n{table.to_string(index=False)}")


if __name__ == "__main__":
    main(sys.argv)
