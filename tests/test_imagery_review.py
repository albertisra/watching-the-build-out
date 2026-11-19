"""Tests for the review fixes: quality flags, registry context, per-request quota rows, refetch plan."""

import json

import numpy as np
import pandas as pd
import pytest

from bo.imagery import qc, quota, regcontext, shcost, shrefetch
from bo.imagery.geo import chip_grid


def test_bright_flag_marks_snow_like_months_only():
    refl = np.full((3, 2, 4, 4), 0.08, np.float32)  # bands B02, B03
    refl[1] = 0.55  # snow-like month
    refl[2] = np.nan  # no clear pixel
    count = np.ones((3, 4, 4), np.uint16)
    count[2] = 0
    assert qc.flag_bright(refl, count, ["B02", "B03"]).tolist() == [False, True, False]
    # falls back to B03 without B02, and a few bright pixels do not move the median
    r2 = np.full((1, 1, 4, 4), 0.1, np.float32)
    r2[0, 0, 0, :2] = 0.9
    assert not qc.flag_bright(r2, np.ones((1, 4, 4), np.uint16), ["B03"])[0]
    assert qc.flag_bright(r2, np.ones((1, 4, 4), np.uint16), ["B04"]).tolist() == [False]


def test_cld_disagree_flag():
    c = np.full((2, 4, 4), 4, np.uint16)
    d = np.stack([np.full((4, 4), 4), np.full((4, 4), 1)]).astype(np.uint16)
    assert qc.flag_cld_disagree(c, d).tolist() == [False, True]


def test_other_sites_in_chip_counts_by_technology_and_excludes_own_site():
    g = chip_grid(11.0, 48.0)
    sites = pd.DataFrame({
        "site_id": ["own", "b1", "pv_in", "pv_out"], "technology": ["ground_pv", "battery", "ground_pv", "ground_pv"],
        "lon": [11.0, 11.001, 11.002, 11.1], "lat": [48.0, 48.001, 48.0, 48.0]})
    assert regcontext.other_sites_in_chip(g, "own", sites) == {"battery": 1, "ground_pv": 1}
    assert regcontext.other_sites_in_chip(g, None, sites)["ground_pv"] == 2
    assert json.loads(regcontext.attr_value(g, "own")) == regcontext.other_sites_in_chip(g, "own")


def test_quota_request_rows_are_written_immediately_and_counted(tmp_path):
    log = tmp_path / "q.csv"
    quota.append_request_row("sh_x_req", 1.5, "a", log)
    quota.append_request_row("sh_x_req", 2.5, "b", log)
    q = pd.read_csv(log)
    assert len(q) == 2 and q.sentinel_hub_pu.sum() == pytest.approx(4.0)
    month = pd.Timestamp.now("UTC").strftime("%Y-%m")
    assert shcost.used_this_month(log, month) == (4.0, 2)


def test_refetch_windows_cover_s1b_and_s1d_eras_and_estimate_scales_by_months():
    ws = {w[0]: w for w in shrefetch.WINDOWS}
    assert ws[2016] == (2016, 9, 12) and ws[2021] == (2021, 1, 12) and 2022 not in ws and ws[2026][1] == 4
    plan = pd.DataFrame({"site_id": ["a"] * 2, "year": [2016, 2017], "s1_dates": [31, 31]})
    e = shrefetch.estimate(plan, ["a"]).set_index("window")
    assert e.loc["2017-01..2017-12", "pu"] == pytest.approx(31 * shcost.S1_PU_PER_DATE)
    assert e.loc["2016-09..2016-12", "pu"] == pytest.approx(31 * shcost.S1_PU_PER_DATE / 3)


def test_group_passes_prefers_native_zone_tiles():
    from types import SimpleNamespace

    from bo.imagery.s2pipe import group_passes

    def it(i, tile, dt):
        return SimpleNamespace(id=i, datetime=pd.Timestamp("2024-05-03", tz="UTC"),
                               properties={"s2:mgrs_tile": tile, "s2:datatake_id": dt})

    items = [it("a", "32UQU", "d1"), it("b", "33UUQ", "d1"), it("c", "33UUQ", "d2")]
    g = {tuple(sorted(i.id for i in p)) for p in group_passes(items, 32632)}
    assert g == {("a",), ("c",)}  # d1 keeps the native tile only; d2 has no native tile and stays warped
    assert len(group_passes(items)[0]) == 2  # without a grid nothing is filtered
