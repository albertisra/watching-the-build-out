"""Recall as a smooth function of site size (plan 7.1, A82).

Among positive targets, P(detected | size) = logistic(b0 + b1 * log10 size), fitted by maximum likelihood with a
tiny ridge (1e-6) that only matters under complete separation. The minimum detectable size is the size where the
fitted recall reaches 0.8: 10 ** ((logit(0.8) - b0) / b1), defined only for b1 > 0. Intervals: spatial block
bootstrap of the whole fit (curve band and minimum size). Size may be MW, MWh or m2 (any positive column).

Sizes are observed (MW, MWh from the registry) or detected (m2 from Track B outlines); recall is detected. Size is
used here for stratified evaluation only, never as a model input.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bo import paths

from . import design
from .bootstrap import block_indices, replicate_draws

RIDGE = 1e-6


def fit_logistic(x: np.ndarray, y: np.ndarray, max_iter: int = 100, tol: float = 1e-10) -> tuple[float, float]:
    """Newton-Raphson for logit P(y=1) = b0 + b1 x. Returns (b0, b1)."""
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    for _ in range(max_iter):
        eta = np.clip(X @ b, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = mu * (1 - mu)
        grad = X.T @ (y - mu) - RIDGE * b
        hess = (X * w[:, None]).T @ X + RIDGE * np.eye(2)
        step = np.linalg.solve(hess, grad)
        b = b + step
        if np.max(np.abs(step)) < tol:
            break
    return float(b[0]), float(b[1])


def predict_recall(b0: float, b1: float, size: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(b0 + b1 * np.log10(np.asarray(size, dtype="float64")))))


def size_at_recall(b0: float, b1: float, target: float = design.RECALL_TARGET) -> float:
    if not b1 > 0:
        return float("nan")
    return float(10 ** ((np.log(target / (1 - target)) - b0) / b1))


def recall_curve(df: pd.DataFrame, size_col: str, det_col: str = "detected", block_col: str = "block_id",
                 grid: np.ndarray | None = None, n_boot: int = design.N_BOOT, level: float = 0.95,
                 seed: int = paths.SEED, target: float = design.RECALL_TARGET
                 ) -> tuple[pd.DataFrame, dict]:
    """(curve, summary). `df`: positive targets with a size, a detection flag and a block.

    The summary states whether the minimum detectable size lies inside the observed size range; outside it, the
    value is an extrapolation and is flagged.
    """
    d = df[df[size_col].notna() & (df[size_col] > 0)]
    x = np.log10(d[size_col].to_numpy(dtype="float64"))
    y = d[det_col].astype(float).to_numpy()
    if grid is None:
        grid = np.logspace(x.min(), x.max(), 50) if len(x) else np.array([])
    b0, b1 = fit_logistic(x, y)
    mds = size_at_recall(b0, b1, target)
    groups = block_indices(d[block_col])
    curves, sizes = [], []
    if len(d) >= design.MIN_N_INTERVAL and len(groups) >= 2:
        for draw in replicate_draws(len(groups), n_boot, seed):
            idx = np.concatenate([groups[j] for j in draw])
            yy = y[idx]
            if yy.min() == yy.max():
                continue  # one class only: slope not identified
            c0, c1 = fit_logistic(x[idx], yy)
            curves.append(predict_recall(c0, c1, grid))
            sizes.append(size_at_recall(c0, c1, target))
    a = (1 - level) / 2
    est = predict_recall(b0, b1, grid)
    if curves:
        band = np.quantile(np.vstack(curves), [a, 1 - a], axis=0)
        s = np.array(sizes)
        s = np.where(np.isnan(s), np.inf, s)  # no increasing curve: minimum size not reached
        mlo, mhi = np.quantile(s, [a, 1 - a])
    else:
        band = np.full((2, len(grid)), np.nan)
        mlo = mhi = float("nan")
    curve = pd.DataFrame({"size": grid, "recall": est, "lo": band[0], "hi": band[1], "size_col": size_col,
                          "level": level, "quantity_type": "detected"})
    lo_obs, hi_obs = (float(10 ** x.min()), float(10 ** x.max())) if len(x) else (np.nan, np.nan)
    summary = {
        "size_col": size_col, "n": len(d), "n_detected": int(y.sum()), "n_blocks": len(groups), "b0": b0, "b1": b1,
        "recall_target": target, "min_detectable_size": mds, "mds_lo": float(mlo), "mds_hi": float(mhi),
        "level": level, "n_boot": n_boot, "n_boot_valid": len(curves), "size_min_observed": lo_obs,
        "size_max_observed": hi_obs,
        "mds_in_observed_range": bool(np.isfinite(mds) and lo_obs <= mds <= hi_obs),
        "interval": "spatial block bootstrap, percentile", "quantity_type": "detected",
    }
    return curve, summary
