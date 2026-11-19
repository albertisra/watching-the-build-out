"""OSM feature code: query, parsing, cache and matching, without network access."""

import json

import pandas as pd
import pytest

from bo.data import osm_features as osm

RESPONSE = {"elements": [
    {"type": "way", "id": 1, "center": {"lat": 51.0, "lon": 10.0},
     "tags": {"power": "plant", "plant:source": "solar", "plant:output:electricity": "24 MW", "name": "X"}},
    {"type": "relation", "id": 2, "center": {"lat": 52.0, "lon": 11.0},
     "tags": {"power": "plant", "plant:source": "battery", "plant:storage": "40 MWh"}},
    {"type": "node", "id": 3, "lat": 53.0, "lon": 12.0,
     "tags": {"power": "generator", "generator:source": "solar;battery"}},
    {"type": "way", "id": 4, "center": {"lat": 51.1, "lon": 10.1},
     "tags": {"power": "substation", "substation": "transmission", "voltage": "380000"}},
    {"type": "way", "id": 5, "center": {"lat": 51.2, "lon": 10.2},
     "tags": {"power": "plant", "plant:source": "wind"}},
    {"type": "way", "id": 6, "tags": {"power": "plant", "plant:source": "solar"}},  # no centre
]}


def test_query_covers_plants_generators_and_substations():
    q = osm.build_query((51.0, 10.0, 51.1, 10.1))
    assert '"plant:source"~"solar|battery"' in q and '"generator:source"~"solar|battery"' in q
    assert '"power"="substation"' in q and "(51.0,10.0,51.1,10.1)" in q and "out center tags" in q


def test_parse_keeps_solar_battery_and_substations_only_and_no_names():
    g = osm.parse_elements(RESPONSE)
    assert sorted(g["osm_id"]) == [1, 2, 3, 4]
    cat = g.set_index("osm_id")["category"]
    assert cat[1] == "solar" and cat[2] == "battery" and cat[3] == "battery" and cat[4] == "substation_context"
    assert g.set_index("osm_id").loc[3, "source"] == "solar;battery"
    assert not {"name", "operator"} & set(g.columns)
    assert str(g.crs) == "EPSG:4326"


def test_fetch_uses_cache_and_posts_once(tmp_path):
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return RESPONSE

    class Sess:
        def post(self, url, data, headers, timeout):
            calls.append((url, headers["User-Agent"]))
            return Resp()

    q = osm.build_query((51.0, 10.0, 51.1, 10.1))
    d1, c1 = osm.fetch(q, tmp_path, Sess())
    d2, c2 = osm.fetch(q, tmp_path, Sess())
    assert (c1, c2) == (False, True) and len(calls) == 1 and d1 == d2
    assert json.loads(osm.cache_path(q, tmp_path).read_text()) == RESPONSE
    assert "@" not in calls[0][1]  # no contact details in the user agent


def test_match_to_sites_by_technology_and_distance():
    g = osm.parse_elements(RESPONSE)
    sites = pd.DataFrame({
        "site_id": ["PV-A", "PV-B", "BESS-C", "BESS-D"],
        "technology": ["ground_pv", "ground_pv", "battery", "battery"],
        "lat": [51.0003, 51.5, 52.0002, 51.0],  # last: battery near the solar plant only
        "lon": [10.0, 10.0, 11.0, 10.0]})
    m = osm.match_to_sites(sites, g, 500).set_index("site_id")
    assert m.loc["PV-A", "osm_match"] and not m.loc["PV-B", "osm_match"]
    assert m.loc["BESS-C", "osm_match"] and not m.loc["BESS-D", "osm_match"]
    assert m.loc["PV-A", "osm_distance_m"] == pytest.approx(33, abs=3)


def test_germany_tiles_cover_the_box_and_are_not_fetched_by_default():
    tiles = osm.germany_tiles(1.0)
    assert min(t[0] for t in tiles) <= 47.2 and max(t[2] for t in tiles) >= 55.0
    assert len(tiles) == 8 * 10
