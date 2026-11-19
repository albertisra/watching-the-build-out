"""Spatial block bootstrap (plan Section 10, A84).

The 50 km blocks of the evaluation set are drawn with replacement (B = 2,000 by default), the statistic is recomputed
on the rows of the drawn blocks (a block drawn twice enters twice), and the interval is the percentile interval at
the requested level. Replicates where the statistic is undefined (for example recall without any positive) are
dropped and counted. Below `min_n` evaluation units no interval is given (A84).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from bo import paths

from . import design


@dataclass(frozen=True)
class BootResult:
    estimate: float
    lo: float
    hi: float
    level: float
    n_units: int
    n_blocks: int
    n_boot: int
    n_boot_valid: int


def block_indices(blocks: pd.Series) -> list[np.ndarray]:
    codes, _ = pd.factorize(blocks, sort=True)
    order = np.argsort(codes, kind="stable")
    bounds = np.flatnonzero(np.diff(codes[order])) + 1
    return np.split(order, bounds)


def replicate_draws(n_blocks: int, n_boot: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n_blocks, size=(n_boot, n_blocks))


def block_bootstrap(df: pd.DataFrame, stat: Callable[[pd.DataFrame], float], block_col: str = "block_id",
                    n_boot: int = design.N_BOOT, level: float = 0.95, seed: int = paths.SEED,
                    min_n: int = design.MIN_N_INTERVAL) -> BootResult:
    est = float(stat(df))
    if df[block_col].isna().any():
        raise ValueError("rows without a block")
    groups = block_indices(df[block_col])
    nb = len(groups)
    if len(df) < min_n or nb < 2:
        return BootResult(est, float("nan"), float("nan"), level, len(df), nb, 0, 0)
    vals = []
    for draw in replicate_draws(nb, n_boot, seed):
        idx = np.concatenate([groups[j] for j in draw])
        v = stat(df.iloc[idx])
        if v is not None and np.isfinite(v):
            vals.append(float(v))
    a = (1.0 - level) / 2.0
    if vals:
        lo, hi = np.quantile(vals, [a, 1.0 - a])
    else:
        lo = hi = float("nan")
    return BootResult(est, float(lo), float(hi), level, len(df), nb, n_boot, len(vals))
