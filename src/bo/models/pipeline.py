"""Development run (folds 1 to 4) and the locked test run (fold 0) of the monthly detector.

`develop` joins features, targets and folds, drops fold 0 before anything else, produces out-of-fold monthly
probabilities on the development folds (months up to DEV_END), selects theta_c on out-of-fold site scores over the
development window (the 12 months ending DEV_END, assumption M3), and returns site-level detections, thresholds and
metrics with block-bootstrap intervals.

`evaluate_test` is the only entry point that touches fold 0. It refuses to run unless the configuration is frozen
(`bo.models.freeze`). Nothing in this repository calls it before the freeze.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import design
from .assemble import usable_month
from .detector import Detector, DetectorConfig, oof_predictions
from .freeze import guard_test_fold
from .guards import assert_no_test_fold
from .metrics import prf_table
from .splits import attach_folds
from .threshold import ThresholdResult, select_threshold, site_scores

KEY_EXTRA = ("block_id", "fold", "open_dop")


def join_inputs(features: pd.DataFrame, targets: pd.DataFrame, splits: pd.DataFrame, key: str = "queue_id"
                ) -> pd.DataFrame:
    """Long table: one row per (site, month, technology) with features, ``usable``, ``y`` and folds."""
    f = features.copy()
    f["usable"] = usable_month(f)
    f = attach_folds(f, splits, key)
    t = targets[["site_id", "month", "technology", "y"]]
    return t.merge(f, on=["site_id", "month"], how="inner", validate="many_to_one")


@dataclass
class DevResult:
    oof: pd.DataFrame
    sites: pd.DataFrame
    thresholds: dict[str, ThresholdResult]
    metrics: pd.DataFrame


def site_table(pred: pd.DataFrame, data: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Per target: k-th largest usable p in the window, truth (plan 2.4) and block."""
    from .targets import site_truth

    sc = site_scores(pred, start, end)
    tr = site_truth(data, start, end)
    blk = data[["site_id", "block_id", "fold"]].drop_duplicates("site_id")
    return sc.merge(tr, on=["site_id", "technology"], how="left").merge(blk, on="site_id", how="left")


def develop(data: pd.DataFrame, configs: Sequence[DetectorConfig], n_boot: int = design.N_BOOT
            ) -> DevResult:
    dev = data[data["fold"] != design.TEST_FOLD]
    assert_no_test_fold(dev["fold"], "development run")
    start, end = design.dev_window()
    oofs, sites, thresholds = [], [], {}
    for cfg in configs:
        p = oof_predictions(dev, cfg)
        p["technology"] = cfg.technology
        oofs.append(p)
        st = site_table(p, dev[dev["technology"] == cfg.technology], start, end)
        st = st[st["truth"].notna()]
        th = select_threshold(st["truth"].to_numpy(), st["score"].to_numpy())
        st["detected"] = st["score"] >= th.theta
        st["theta"] = th.theta
        thresholds[cfg.technology] = th
        sites.append(st)
    sites_df = pd.concat(sites, ignore_index=True)
    met = prf_table(sites_df, by=["technology"], n_boot=n_boot)
    met["evaluation"] = "development folds, out of fold (theta selected on the same scores: optimistic)"
    return DevResult(pd.concat(oofs, ignore_index=True), sites_df, thresholds, met)


def evaluate_test(data: pd.DataFrame, cfg: DetectorConfig, theta: float, freeze_path: Path | None = None
                  ) -> pd.DataFrame:
    """Fit on folds 1 to 4 (months up to DEV_END), score fold 0 over H. Refuses to run without a matching freeze."""
    frozen_cfg = {**cfg.as_dict(), "theta": theta}
    guard_test_fold([design.TEST_FOLD], cfg.component(), frozen_cfg, freeze_path)
    tech = data[data["technology"] == cfg.technology]
    train = tech[tech["fold"].isin(design.DEV_FOLDS) & (tech["month"] <= design.DEV_END)]
    test = tech[tech["fold"] == design.TEST_FOLD]
    det = Detector(cfg).fit(train)
    p = det.predict(test)
    p["technology"] = cfg.technology
    st = site_table(p, test, *design.holdout_window())
    st["detected"] = st["score"] >= theta
    return st
