"""Blindness of the signature figures (review M4): no registry overlay for sites in the labelling queue."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import pandas as pd

from bo.features import signatures as S
from bo.labelling.exposure import match_to_queue


def test_overlay_rule():
    hidden = {"Q015"}
    assert not S.registry_overlay_allowed("Q015", hidden)
    assert S.registry_overlay_allowed("P009", hidden)


def test_match_radius_floor_100m():
    # 0.0009 deg latitude is about 100 m: 80 m matches, 150 m does not (no coordinate uncertainty)
    q = pd.DataFrame({"queue_id": ["L1-1", "L1-2"], "site_id": [None, None],
                      "lat": [50.0, 51.0], "lon": [10.0, 10.0]})
    p = pd.DataFrame({"pilot_id": ["A", "B"], "site_key": ["x", "y"],
                      "lat": [50.0 + 80 / 111_195, 51.0 + 150 / 111_195], "lon": [10.0, 10.0]})
    m = match_to_queue(p, q)
    assert list(m.pilot_id) == ["A"]
    m2 = match_to_queue(p, q, unc_m={"L1-2": 200.0})
    assert set(m2.pilot_id) == {"A", "B"}


def test_platform_conventions_declared():
    assert S.PLATFORMS["sh_pc"]["s1_convention"] == "gamma0"
    assert S.PLATFORMS["ee_r1"]["s1_convention"] == "sigma0"
    assert S.PLATFORMS["sh_pc"]["out"] != S.PLATFORMS["ee_r1"]["out"]
    df = S.tag(pd.DataFrame({"a": [1]}), "ee_r1")
    assert df.loc[0, "s1_convention"] == "sigma0" and df.loc[0, "platform"] == "ee_r1"


def test_aligned_figure_skips_when_all_hidden(tmp_path, monkeypatch):
    monkeypatch.setitem(S.PLATFORMS, "ee_r1", {**S.PLATFORMS["ee_r1"], "fig": tmp_path})
    sites = pd.DataFrame({"pilot_id": ["Q1", "Q2"], "subtype": ["battery", "ground-mounted"],
                          "reg_commissioning_date": ["2024-01-01", "2024-01-01"]})

    def loader(_):  # must never be called for hidden sites
        raise AssertionError("hidden site was loaded for the aligned figure")

    assert S.aligned_figure(sites, "ee_r1", {"Q1", "Q2"}, loader) is False
    assert not (tmp_path / "aligned_yoy.png").exists()
