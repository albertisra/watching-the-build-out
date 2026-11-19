"""Temporal features on monthly series. Missing months stay NaN and are counted, never interpolated.

- ``yoy``: value minus the value of the same calendar month one year earlier (A8). NaN if either is missing.
- ``trailing_std`` and ``trailing_count``: spread and number of valid months in the trailing window
  (default 12 months including the current one); the spread is NaN below ``min_valid`` months (F4).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 12
MIN_VALID = 6


def regular_months(months) -> pd.DatetimeIndex:
    m = pd.DatetimeIndex(months).to_period("M").to_timestamp()
    return pd.date_range(m.min(), m.max(), freq="MS")


def to_regular(s: pd.Series) -> pd.Series:
    """Reindex a month-indexed series to a gap-free monthly axis; absent months become NaN (not filled)."""
    idx = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
    s = pd.Series(s.values, index=idx)
    s = s[~s.index.duplicated()]
    return s.reindex(regular_months(idx))


def yoy(s: pd.Series, lag: int = 12) -> pd.Series:
    r = to_regular(s)
    out = r - r.shift(lag)
    return out.reindex(pd.DatetimeIndex(s.index).to_period("M").to_timestamp()).set_axis(s.index)


def trailing_count(s: pd.Series, window: int = WINDOW) -> pd.Series:
    r = to_regular(s)
    out = r.notna().astype(float).rolling(window, min_periods=1).sum()
    return out.reindex(pd.DatetimeIndex(s.index).to_period("M").to_timestamp()).set_axis(s.index)


def trailing_std(s: pd.Series, window: int = WINDOW, min_valid: int = MIN_VALID) -> pd.Series:
    r = to_regular(s)
    out = r.rolling(window, min_periods=min_valid).std(ddof=1)
    return out.reindex(pd.DatetimeIndex(s.index).to_period("M").to_timestamp()).set_axis(s.index)


def trailing_cv_linear_db(s_db: pd.Series, window: int = WINDOW, min_valid: int = MIN_VALID) -> pd.Series:
    """Coefficient of variation of a dB series computed in linear power units."""
    r = to_regular(s_db)
    lin = 10.0 ** (r / 10.0)
    m = lin.rolling(window, min_periods=min_valid).mean()
    sd = lin.rolling(window, min_periods=min_valid).std(ddof=1)
    out = sd / m
    return out.reindex(pd.DatetimeIndex(s_db.index).to_period("M").to_timestamp()).set_axis(s_db.index)


def nan_safe(x) -> np.ndarray:
    return np.asarray(x, dtype="float64")
