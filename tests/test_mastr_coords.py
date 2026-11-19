"""Tests for the MaStR coordinate completeness check on a synthetic UTF-16 export."""

import zipfile

import numpy as np
import pandas as pd
import pytest

from bo.data import mastr_coords as mc


def _xml(root: str, element: str, rows: list[dict]) -> bytes:
    body = "".join(
        f"<{element}>" + "".join(f"<{k}>{v}</{k}>" for k, v in r.items()) + f"</{element}>"
        for r in rows
    )
    return f'<?xml version="1.0" encoding="UTF-16"?><{root}>{body}</{root}>'.encode("utf-16")


@pytest.fixture
def export_zip(tmp_path):
    storage = [
        # large battery with good coordinates
        {"EinheitMastrNummer": "SEE1", "Bruttoleistung": "10000", "Nettonennleistung": "10000",
             "EinheitBetriebsstatus": "35", "Technologie": "524", "Breitengrad": "51.25", "Laengengrad": "12.59"},
        # large battery without coordinates
        {"EinheitMastrNummer": "SEE2", "Bruttoleistung": "2000,5", "EinheitBetriebsstatus": "31",
             "Technologie": "524"},
        # large battery with swapped coordinates
        {"EinheitMastrNummer": "SEE3", "Bruttoleistung": "60000", "EinheitBetriebsstatus": "35",
             "Technologie": "524", "Breitengrad": "12.597", "Laengengrad": "51.254"},
        # home storage, below threshold
        {"EinheitMastrNummer": "SEE4", "Bruttoleistung": "5", "Technologie": "524"},
        # pumped hydro, large
        {"EinheitMastrNummer": "SEE5", "Bruttoleistung": "100000", "Technologie": "1537",
             "Breitengrad": "48.0", "Laengengrad": "9.0"},
    ]
    solar1 = [
        {"EinheitMastrNummer": "SEE6", "Bruttoleistung": "1200", "Nettonennleistung": "1000",
             "ArtDerSolaranlage": "3", "Breitengrad": "52.123456", "Laengengrad": "13.1"},
        {"EinheitMastrNummer": "SEE7", "Bruttoleistung": "9", "Nettonennleistung": "8",
             "ArtDerSolaranlage": "2"},
    ]
    solar2 = [
        {"EinheitMastrNummer": "SEE8", "Bruttoleistung": "2000", "Nettonennleistung": "1800",
             "ArtDerSolaranlage": "2", "Breitengrad": "0.0", "Laengengrad": "0.0"},
    ]
    catalogue = [
        {"Id": "35", "Wert": "In Betrieb"}, {"Id": "31", "Wert": "In Planung"},
        {"Id": "524", "Wert": "Batterie"}, {"Id": "1537", "Wert": "Pumpspeicher"},
        {"Id": "3", "Wert": "Freiflächensolaranlage"}, {"Id": "2", "Wert": "Gebäudesolaranlage"},
    ]
    path = tmp_path / "Gesamtdatenexport_20260101_99.9.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("EinheitenStromSpeicher_1.xml", _xml("EinheitenStromSpeicher", "EinheitStromSpeicher", storage))
        zf.writestr("EinheitenSolar_1.xml", _xml("EinheitenSolar", "EinheitSolar", solar1))
        zf.writestr("EinheitenSolar_2.xml", _xml("EinheitenSolar", "EinheitSolar", solar2))
        zf.writestr("Katalogwerte.xml", _xml("Katalogwerte", "Katalogwert", catalogue))
        zf.writestr("AnlagenEegSolar_1.xml", _xml("AnlagenEegSolar", "AnlageEegSolar", []))
    return path


def test_to_float_handles_comma_point_and_empty():
    assert mc.to_float("2000,5") == 2000.5
    assert mc.to_float("51.25") == 51.25
    assert mc.to_float("") is None and mc.to_float(None) is None and mc.to_float("x") is None


def test_threshold_and_split_files(export_zip):
    with zipfile.ZipFile(export_zip) as zf:
        storage, n_storage, bad_storage = mc.read_large_units(zf, "storage")
        solar, n_solar, bad_solar = mc.read_large_units(zf, "solar")
    assert n_storage == 5 and n_solar == 3
    assert bad_storage == [] and bad_solar == []
    assert set(storage["EinheitMastrNummer"]) == {"SEE1", "SEE2", "SEE3", "SEE5"}
    assert set(solar["EinheitMastrNummer"]) == {"SEE6", "SEE8"}  # read across both split files


def test_coordinate_states_and_classes(export_zip, tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "OUT_DIR", tmp_path / "results")
    monkeypatch.setattr(mc, "UNITS_OUT", tmp_path / "processed")
    mc.run(export_zip)
    units = pd.read_parquet(tmp_path / "processed" / "units_ge_threshold.parquet")
    u = units.set_index("EinheitMastrNummer")
    assert u.loc["SEE1", "coord_state"] == "ok"
    assert u.loc["SEE2", "coord_state"] == "missing"
    assert u.loc["SEE3", "coord_state"] == "swapped"
    assert u.loc["SEE8", "coord_state"] == "outside"
    assert u.loc["SEE1", "subtype"] == "battery" and u.loc["SEE5", "subtype"] == "other"
    assert u.loc["SEE6", "subtype"] == "ground-mounted" and u.loc["SEE8", "subtype"] == "other"
    assert u.loc["SEE1", "size_class"] == "10-50 MW" and u.loc["SEE3", "size_class"] == "50-100 MW"
    assert u.loc["SEE6", "size_class"] == "1-5 MW"  # solar classed by net power (1000 kW)
    assert u.loc["SEE1", "EinheitBetriebsstatus_text"] == "In Betrieb"
    assert u.loc["SEE6", "coord_decimals"] == 1  # coarser of the two coordinates

    table = pd.read_csv(tmp_path / "results" / "coordinate_completeness_by_subtype.csv")
    bat = table[(table.kind == "storage") & (table.subtype == "battery")].iloc[0]
    assert bat.units == 3 and bat.units_ok == 1 and bat.units_missing == 1 and bat.units_swapped == 1
    assert bat.share_units_ok == pytest.approx(1 / 3)
    assert bat.share_mw_ok == pytest.approx(10000 / 72000.5)


def test_missing_export_gives_instruction(tmp_path):
    with pytest.raises(FileNotFoundError, match="by hand"):
        mc.newest_zip(tmp_path)


def test_unreadable_member_is_skipped_whole_and_reported(export_zip, tmp_path):
    """Simulate a partial download: zero out the bytes of one solar member."""
    data = bytearray(export_zip.read_bytes())
    with zipfile.ZipFile(export_zip) as zf:
        info = zf.getinfo("EinheitenSolar_2.xml")
    start = info.header_offset
    data[start:start + 30 + len(info.filename) + info.compress_size] = bytes(
        30 + len(info.filename) + info.compress_size
    )
    broken = tmp_path / "broken.zip"
    broken.write_bytes(bytes(data))
    with zipfile.ZipFile(broken) as zf:
        solar, n_solar, bad = mc.read_large_units(zf, "solar")
    assert bad == ["EinheitenSolar_2.xml"]
    assert n_solar == 2 and list(solar["EinheitMastrNummer"]) == ["SEE6"]


def test_precision_class_uses_numeric_value_not_export_text():
    from bo.data.mastr_coords import classify_coordinate_precision, classify_coordinates

    raw = pd.DataFrame({"Breitengrad": ["54.300000", "52.350000", "51.123000", "51.123456", None],
                        "Laengengrad": ["12.900000", "9.612345", "8.456000", "8.456789", "9.0"]})
    c = classify_coordinates(raw)
    assert c["coord_decimals"].iloc[0] == 6  # text count is useless: always padded
    p = classify_coordinate_precision(c["lat"], c["lon"])
    # the coarser axis decides: row 1 has a full-precision lon but lat 52.35 has 2 decimals
    assert list(p["coord_precision_class"].iloc[:4]) == ["dp1", "dp2", "dp3", "dp4plus"]
    assert np.isnan(p["coord_unc_m"].iloc[4]) and pd.isna(p["coord_precision_class"].iloc[4])
    # dp1 is about 5.6 km half-step in latitude, dp3 about 56 m (times sqrt(1 + cos^2(lat)), about 1.2 at 54 N)
    assert 6_000 < p["coord_unc_m"].iloc[0] < 7_000
    assert 55 < p["coord_unc_m"].iloc[2] < 75


def test_precision_class_two_decimals_and_site_rule():
    from bo.data.mastr_coords import classify_coordinate_precision

    p = classify_coordinate_precision(pd.Series([52.35, 52.35]), pd.Series([9.61, 9.6]))
    assert list(p["coord_precision_class"]) == ["dp2", "dp1"]
    assert (p["coord_unc_m"].iloc[0] * 10 - p["coord_unc_m"].iloc[1]) < 20  # factor 10 apart


def test_coord_quality_columns_excluded_from_features():
    from bo.data.registry import registry_columns

    cols = ["coord_precision_class", "coord_unc_m", "coord_rounded", "flag_coord_rounded",
            "flag_coord_rounded_any", "s2_ndvi_mean"]
    assert registry_columns(pd.DataFrame(columns=cols)) == cols[:5]


def test_coarse_queue_items_matches_by_site_id():
    from bo.data.queue_coarse import coarse_queue_items

    q = pd.DataFrame({"queue_id": ["L1-1", "L1-2", "L1-3", "L1-4"], "site_id": ["a", "b", None, "d"]})
    s = pd.DataFrame({"site_id": ["a", "b", "d"], "coord_precision_class": ["dp1", "dp4plus", "dp3"],
                      "coord_unc_m": [6444.0, 8.0, 64.0]})
    out = coarse_queue_items(q, s)
    assert list(out["queue_id"]) == ["L1-1", "L1-4"]
    assert list(out["precision_class"]) == ["dp1", "dp3"]
