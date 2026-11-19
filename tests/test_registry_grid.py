"""Grid join (Lokationen -> Netzanschlusspunkte) on field names taken from the real export of 16.11.2026."""

import zipfile

from bo.data import registry


def _xml(root: str, element: str, rows: list[dict]) -> bytes:
    body = "".join(
        f"<{element}>" + "".join(f"<{k}>{v}</{k}>" for k, v in r.items()) + f"</{element}>"
        for r in rows
    )
    return f'<?xml version="1.0" encoding="UTF-16"?><{root}>{body}</{root}>'.encode("utf-16")


def test_grid_join_uses_real_field_names(tmp_path):
    locations = [
        {"MastrNummer": "SEL1", "Lokationtyp": "1", "VerknuepfteEinheitenMaStRNummern": "SEE1",
         "NetzanschlusspunkteMaStRNummern": "SAN1"},
        {"MastrNummer": "SEL2", "NetzanschlusspunkteMaStRNummern": "SAN2, SAN3"},
        {"MastrNummer": "SEL9", "NetzanschlusspunkteMaStRNummern": "SAN9"},  # not wanted
    ]
    points = [
        {"NetzanschlusspunktMastrNummer": "SAN1", "LokationMaStRNummer": "SEL1",
         "Spannungsebene": "354", "NetzbetreiberMaStRNummer": "SNB1"},
        {"NetzanschlusspunktMastrNummer": "SAN2", "Spannungsebene": "351",
         "NetzbetreiberMaStRNummer": "SNB2"},
        {"NetzanschlusspunktMastrNummer": "SAN3", "Spannungsebene": "354",
         "NetzbetreiberMaStRNummer": "SNB2"},
        {"NetzanschlusspunktMastrNummer": "SAN9", "Spannungsebene": "351",
         "NetzbetreiberMaStRNummer": "SNB9"},
    ]
    path = tmp_path / "Gesamtdatenexport_20261116_26.2.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Lokationen_1.xml", _xml("Lokationen", "Lokation", locations))
        zf.writestr("Netzanschlusspunkte_1.xml", _xml("Netzanschlusspunkte", "Netzanschlusspunkt", points))
    catalogue = {"354": "Mittelspannung", "351": "Höchstspannung"}
    with zipfile.ZipFile(path) as zf:
        grid, _reports = registry.extract_grid(zf, {"SEL1", "SEL2"}, catalogue)
    g = grid.set_index("location_id")
    assert set(g.index) == {"SEL1", "SEL2"}
    assert g.loc["SEL1", "grid_operator_id"] == "SNB1"
    assert g.loc["SEL1", "voltage_level"] == "Mittelspannung"
    assert g.loc["SEL2", "voltage_level"] == "Höchstspannung;Mittelspannung"
