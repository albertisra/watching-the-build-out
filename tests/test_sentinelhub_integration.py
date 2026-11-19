"""Integration check (network, Sentinel Hub quota): run with BO_INTEGRATION=1."""

import os

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("BO_INTEGRATION") != "1",
                                reason="network integration test; set BO_INTEGRATION=1")


def test_sentinelhub_month_matches_planetary_computer_chip():
    from bo.imagery.shcheck import compare

    d = compare("P009", 2024)  # needs data/chips/v0/P009.zarr (Planetary Computer store)
    ok = d[(d.pc_mean_clear_count > 2) & (d.month != "2024-09")]
    assert (ok.B04_mean_abs_diff < 0.01).all()
    assert ((ok.B04_mean_sh - ok.B04_mean_pc).abs() < 0.005).all()
    assert ((ok.pc_mean_clear_count - ok.sh_mean_clear_count).abs() < 0.5).all()
