"""Loader, schema and range checks of the registry pipeline on a synthetic UTF-16 export."""

import zipfile

import numpy as np
import pandas as pd
import pytest

from bo.data import registry as rg


def _xml(root, element, rows):
    body = "".join(
        f"<{element}>" + "".join(f"<{k}>{v}</{k}>" for k, v in r.items()) + f"</{element}>" for r in rows
    )
    return f'<?xml version="1.0" encoding="UTF-16"?><{root}>{body}</{root}>'.encode("utf-16")


def _storage(uid, gross, **kw):
    r = {"EinheitMastrNummer": uid, "LokationMaStRNummer": "SELA", "Bruttoleistung": gross,
         "Nettonennleistung": gross, "EinheitBetriebsstatus": "35", "Technologie": "524",
         "Registrierungsdatum": "2022-03-01", "Inbetriebnahmedatum": "2022-06-15",
         "Bundesland": "1403", "DatumLetzteAktualisierung": "2025-01-01T10:00:00.123"}
    r.update(kw)
    return r


def _solar(uid, net, **kw):
    r = {"EinheitMastrNummer": uid, "LokationMaStRNummer": "SELB", "Bruttoleistung": net,
         "Nettonennleistung": net, "EinheitBetriebsstatus": "35", "ArtDerSolaranlage": "852",
         "Registrierungsdatum": "2023-01-02", "Inbetriebnahmedatum": "2023-02-10",
         "Bundesland": "1403", "DatumLetzteAktualisierung": "2025-01-01T10:00:00"}
    r.update(kw)
    return r


@pytest.fixture
def export_zip(tmp_path):
    s1 = [
        _storage("SEES1", "10000", SpeMastrNummer="SSE1", Breitengrad="51.0", Laengengrad="10.0"),
        _storage("SEES2", "5000", SpeMastrNummer="SSE1", Breitengrad="51.0005", Laengengrad="10.0"),
        _storage("SEES3", "2000", SpeMastrNummer="SSE3", EinheitBetriebsstatus="31",
                 GeplantesInbetriebnahmedatum="2025-01-01", Inbetriebnahmedatum="2024-01-01"),
        _storage("SEES4", "100000", Technologie="1537", Breitengrad="48", Laengengrad="9"),  # pumped hydro
        _storage("SEES5", "500", SpeMastrNummer="SSE5"),  # below threshold
        _storage("SEES6", "3.500", SpeMastrNummer="SSE6", Bruttoleistung_="x"),  # kW with point decimals
    ]
    s2_broken = b"\xff\xfe<\x00?\x00xml"  # not parseable: stands for a hole in a partial export
    solar = [
        _solar("SEEP1", "3000", Breitengrad="51.001", Laengengrad="10.0", SpeicherAmGleichenOrt="1"),
        _solar("SEEP2", "9000", ArtDerSolaranlage="853", Breitengrad="50", Laengengrad="10"),  # roof
        _solar("SEEP3", "2000", Breitengrad="10.5", Laengengrad="51.5", Inbetriebnahmedatum="1900-01-01"),
        _solar("SEEP4", "1500", Breitengrad="52.0", Laengengrad="11.0", EinheitBetriebsstatus="38",
               DatumEndgueltigeStilllegung="2025-02-01", Inbetriebnahmedatum="2010-05-01"),
        _solar("SEEP5", "1200", Breitengrad="0.0", Laengengrad="0.0", Inbetriebnahmedatum="2999-12-31"),
        _solar("SEEP6", "1100", Registrierungsdatum="2023-06-01", Inbetriebnahmedatum="2022-01-01"),
    ]
    plants = [
        {"MaStRNummer": "SSE1", "NutzbareSpeicherkapazitaet": "30000",
         "VerknuepfteEinheitenMaStRNummern": "SEES1, SEES2", "AnlageBetriebsstatus": "35"},
        {"MaStRNummer": "SSE3", "NutzbareSpeicherkapazitaet": "4000",
         "VerknuepfteEinheitenMaStRNummern": "SEES3", "AnlageBetriebsstatus": "31"},
    ]
    cat = [{"Id": "35", "Wert": "In Betrieb"}, {"Id": "31", "Wert": "In Planung"},
           {"Id": "38", "Wert": "Endgültig stillgelegt"}, {"Id": "524", "Wert": "Batterie"},
           {"Id": "1537", "Wert": "Pumpspeicher"}, {"Id": "852", "Wert": "Freiflächensolaranlage"},
           {"Id": "853", "Wert": "Gebäudesolaranlage"}, {"Id": "1403", "Wert": "Bayern"}]
    path = tmp_path / "Gesamtdatenexport_20261116_26.2.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("EinheitenStromSpeicher_1.xml", _xml("EinheitenStromSpeicher", "EinheitStromSpeicher", s1))
        zf.writestr("EinheitenStromSpeicher_2.xml", s2_broken)
        zf.writestr("EinheitenSolar_1.xml", _xml("EinheitenSolar", "EinheitSolar", solar))
        zf.writestr("AnlagenStromSpeicher_1.xml", _xml("AnlagenStromSpeicher", "AnlageStromSpeicher", plants))
        zf.writestr("Katalogwerte.xml", _xml("Katalogwerte", "Katalogwert", cat))
        zf.writestr("Lokationen_1.xml", s2_broken)  # unreadable
    return path


def test_run_on_partial_export(export_zip):
    res = rg.run(export_zip, write=False)
    u, m = res.units.set_index("unit_id"), res.meta
    assert m["is_partial"] and not m["grid_join_available"]
    assert m["reports"]["storage_units"].members == 2 and m["reports"]["storage_units"].readable == 1
    assert m["reports"]["locations"].unreadable == ["Lokationen_1.xml"]
    # technology and threshold filters
    assert set(u.index) == {"SEES1", "SEES2", "SEES3", "SEEP1", "SEEP3", "SEEP4", "SEEP5", "SEEP6"}
    # status and catalogue resolution
    assert u.loc["SEES3", "reg_status"] == "In Planung" and u.loc["SEEP4", "reg_status"] == "Endgültig stillgelegt"
    assert u.loc["SEES1", "bundesland"] == "Bayern"
    # kWh: plant 30 MWh split 2:1 by gross power over the two linked units
    assert u.loc["SEES1", "usable_kwh_alloc"] == pytest.approx(20000)
    assert u.loc["SEES2", "usable_kwh_alloc"] == pytest.approx(10000)
    assert u.loc["SEES3", "usable_kwh"] == pytest.approx(4000)
    assert u.loc["SEES1", "storage_plant_n_linked"] == 2
    # coordinates
    assert u.loc["SEEP3", "coord_state"] == "swapped" and u.loc["SEEP3", "lat"] == pytest.approx(51.5)
    assert u.loc["SEEP5", "coord_state"] == "outside" and np.isnan(u.loc["SEEP5", "lat"])
    assert u.loc["SEES3", "coord_state"] == "missing"
    # grid columns degrade to empty
    assert u["grid_operator_id"].isna().all() and u["voltage_level"].isna().all()


def test_date_flags(export_zip):
    u = rg.run(export_zip, write=False).units.set_index("unit_id")
    assert u.loc["SEEP3", "reg_flag_commissioning_placeholder"] and pd.isna(u.loc["SEEP3", "reg_commissioning_date"])
    assert u.loc["SEEP5", "reg_flag_commissioning_placeholder"]
    assert u.loc["SEEP4", "reg_flag_commissioned_before_registry_opened"]
    assert not u.loc["SEEP4", "reg_flag_late_registration"]  # expected, not an anomaly
    assert u.loc["SEEP6", "reg_flag_late_registration"] and not u.loc["SEEP6", "reg_flag_commissioned_before_registry_opened"]
    assert u.loc["SEEP1", "reg_flag_registered_before_commissioning"]
    assert u.loc["SEES3", "reg_flag_planned_date_in_past"]
    assert u.loc["SEES3", "reg_flag_planned_with_past_commissioning_date"]
    assert u.loc["SEEP3", "reg_flag_operating_without_commissioning_date"]
    assert not u.loc["SEES1", "reg_flag_commissioning_future"]


def test_sites_and_colocation_from_run(export_zip):
    res = rg.run(export_zip, write=False)
    s = res.sites.set_index("site_id")
    assert s.loc["BESS-SEES1", "n_units"] == 3  # same location ID; SEES3 has no coordinates
    assert s.loc["BESS-SEES1", "colocated_pv"]  # SEEP1 is about 110 m away
    assert s.loc["PV-SEEP1", "colocated_bess"]
    assert not s.loc["PV-SEEP4", "colocated_bess"]


def test_registry_columns_are_prefixed(export_zip):
    res = rg.run(export_zip, write=False)
    regcols = rg.registry_columns(res.units)
    for c in res.units.columns:
        if "_date" in c or c in ("reg_status", "reg_last_update"):
            assert c in regcols, c
    assert "operator" not in " ".join(res.units.columns).lower().replace("grid_operator_id", "")


def test_write_outputs_keep_coordinates_out_of_results(export_zip, tmp_path):
    from bo.data import registry_report as rr

    res = rg.run(export_zip, write=False)
    rr.write_outputs(res, tmp_path / "proc", tmp_path / "res")
    rr.write_data_card(res, tmp_path / "card.md")
    import geopandas as gpd

    sites = gpd.read_parquet(tmp_path / "proc" / rr.SITE_FILE)
    assert sites.geometry.notna().sum() > 0
    for f in (tmp_path / "res").glob("*.csv"):
        cols = pd.read_csv(f, nrows=0).columns
        assert not {"lat", "lon", "geometry", "unit_ids", "unit_id"} & set(cols), f.name
    card = (tmp_path / "card.md").read_text()
    assert "PARTIAL RUN" in card and "pending full export" in card


def test_schema_error_when_required_field_missing(tmp_path):
    path = tmp_path / "Gesamtdatenexport_20261116_26.2.zip"
    row = _storage("SEES1", "2000")
    del row["Bruttoleistung"]
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("EinheitenStromSpeicher_1.xml", _xml("E", "EinheitStromSpeicher", [row]))
        zf.writestr("EinheitenSolar_1.xml", _xml("E", "EinheitSolar", [_solar("P", "2000")]))
        zf.writestr("Katalogwerte.xml", _xml("K", "Katalogwert", [{"Id": "524", "Wert": "Batterie"}]))
    with pytest.raises(rg.SchemaError):
        rg.run(path, write=False)


def test_no_readable_unit_member_fails_loudly(tmp_path):
    path = tmp_path / "Gesamtdatenexport_20261116_26.2.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("EinheitenStromSpeicher_1.xml", b"\xff\xfe<")
        zf.writestr("EinheitenSolar_1.xml", _xml("E", "EinheitSolar", [_solar("P", "2000")]))
        zf.writestr("Katalogwerte.xml", _xml("K", "Katalogwert", [{"Id": "524", "Wert": "Batterie"}]))
    with pytest.raises(rg.SchemaError):
        rg.run(path, write=False)


def test_parse_dates_placeholders_and_garbage():
    d, ph = rg.parse_dates(pd.Series(["2020-05-04", "1900-01-01", "9999-12-31", "", None, "abc", "2020-05-04T10:00:00"]))
    assert list(ph) == [False, True, True, False, False, True, False]
    assert d.notna().tolist() == [True, False, False, False, False, False, True]


def test_newest_export_prefers_complete_over_preview(tmp_path):
    for p in ("20261116/Gesamtdatenexport_20261116_26.2.zip", "preview/Gesamtdatenexport_20261117_26.2_preview.zip",
              "20261001/Gesamtdatenexport_20261001_26.1.zip"):
        f = tmp_path / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    assert rg.newest_export(tmp_path).name == "Gesamtdatenexport_20261116_26.2.zip"
    only = tmp_path / "only"
    (only / "preview").mkdir(parents=True)
    (only / "preview" / "Gesamtdatenexport_20261117_26.2_preview.zip").write_bytes(b"x")
    assert "preview" in rg.newest_export(only).name


def test_duplicate_candidates_need_different_location_ids():
    base = {"technology": "battery", "gross_kw": 2000.0, "net_kw": 2000.0, "lat": 50.0, "lon": 10.0,
                "reg_registration_date": pd.Timestamp("2022-01-01"), "reg_commissioning_date": pd.Timestamp("2022-06-01")}
    u = pd.DataFrame([
        {**base, "unit_id": "A", "location_id": "L1"}, {**base, "unit_id": "B", "location_id": "L2"},
        {**base, "unit_id": "C", "location_id": "L3", "lat": 51.0},
        {**base, "unit_id": "D", "location_id": "L4", "lat": 52.0}, {**base, "unit_id": "E", "location_id": "L4", "lat": 52.0},
        {**base, "unit_id": "A", "location_id": "L5", "lat": 53.0},
    ])
    out = rg.flag_duplicates(u)
    assert list(out["flag_duplicate_candidate"]) == [True, True, False, False, False, False]
    assert list(out["flag_duplicate_unit_id"]) == [True, False, False, False, False, True]
