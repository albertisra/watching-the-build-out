"""Precision, recall, F1 with block-bootstrap intervals, strata, calibration table, false positives per area.

All outputs are detected quantities (model output scored against author labels). Every table carries n, the interval
method and ``quantity_type``. Sample precision depends on the positive-to-negative ratio of the evaluation set; the
ratio is written next to every precision (plan 7.1).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from bo import paths

from . import design
from .bootstrap import block_bootstrap


def _counts(df: pd.DataFrame, y: str = "truth", det: str = "detected") -> tuple[int, int, int, int]:
    t = df[y].astype(bool).to_numpy()
    d = df[det].astype(bool).to_numpy()
    if "dop_contradicted" in df:
        # KICKOFF 6.0: a Track A detection the DOP contradicts is an error, never a true positive.
        c = df["dop_contradicted"].fillna(False).astype(bool).to_numpy()
        tp = int((d & t & ~c).sum())
        fp = int((d & (~t | c)).sum())
        fn = int((t & (~d | c)).sum())
    else:
        tp, fp, fn = int((d & t).sum()), int((d & ~t).sum()), int((~d & t).sum())
    tn = len(df) - int((d | t).sum())
    return tp, fp, fn, tn


def precision(df: pd.DataFrame) -> float:
    tp, fp, _, _ = _counts(df)
    return tp / (tp + fp) if tp + fp else float("nan")


def recall(df: pd.DataFrame) -> float:
    tp, _, fn, _ = _counts(df)
    return tp / (tp + fn) if tp + fn else float("nan")


def f1(df: pd.DataFrame) -> float:
    tp, fp, fn, _ = _counts(df)
    return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")


METRICS = {"precision": precision, "recall": recall, "f1": f1}


def prf_table(df: pd.DataFrame, by: Sequence[str] = (), n_boot: int = design.N_BOOT, level: float = 0.95,
              seed: int = paths.SEED, block_col: str = "block_id") -> pd.DataFrame:
    """One row per stratum and metric: estimate, block-bootstrap interval, counts. `df` has one row per evaluated
    target (or target-month) with ``truth``, ``detected`` and the block column."""
    d = df[df["truth"].notna()]
    groups = d.groupby(list(by), dropna=False) if by else [((), d)]
    rows = []
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        tp, fp, fn, tn = _counts(g)
        for name, fn_ in METRICS.items():
            r = block_bootstrap(g, fn_, block_col, n_boot, level, seed)
            rows.append({**dict(zip(by, key, strict=True)), "metric": name, "estimate": r.estimate, "lo": r.lo,
                         "hi": r.hi, "level": level, "n": r.n_units, "n_pos": tp + fn, "n_neg": fp + tn,
                         "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n_blocks": r.n_blocks,
                         "n_boot_valid": r.n_boot_valid, "interval": "spatial block bootstrap, percentile",
                         "quantity_type": "detected"})
    return pd.DataFrame(rows)


def size_class(mw: pd.Series) -> pd.Series:
    return pd.cut(mw, bins=[*design.SIZE_CLASS_EDGES[:-1], np.inf], labels=list(design.SIZE_CLASS_LABELS),
                  right=False).astype("object")


def region(bundesland: pd.Series) -> pd.Series:
    return bundesland.map(design.REGION_OF_STATE)


def season(month: pd.Series) -> pd.Series:
    return pd.DatetimeIndex(month).month.map(design.SEASON_OF_MONTH).to_series(index=month.index)


def calibration_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Reliability table with quantile bins: mean predicted p, observed rate, count per bin."""
    y = np.asarray(y, dtype="float64")
    p = np.asarray(p, dtype="float64")
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    b = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, max(len(edges) - 2, 0))
    out = pd.DataFrame({"bin": b, "p": p, "y": y}).groupby("bin").agg(
        p_mean=("p", "mean"), y_rate=("y", "mean"), n=("y", "size")).reset_index()
    out["quantity_type"] = "detected"
    return out


def brier(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype="float64")
    p = np.asarray(p, dtype="float64")
    ok = np.isfinite(y) & np.isfinite(p)
    return float(np.mean((p[ok] - y[ok]) ** 2))


def fp_per_1000km2(n_false_positive: int, area_km2: float) -> float:
    """False positives per 1,000 km2 scanned (Phase 5 discovery; plan 7.1)."""
    if area_km2 <= 0:
        raise ValueError("scanned area must be positive")
    return 1000.0 * n_false_positive / area_km2
