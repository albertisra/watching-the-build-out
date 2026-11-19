"""Pure-numpy compositing. Missing months stay NaN with count zero; nothing is interpolated."""

from __future__ import annotations

import warnings

import numpy as np


def masked_median(values: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Median over the first axis of ``values`` using only ``valid`` observations.

    values: (N, ..., H, W) with the observation axis first. valid: (N, H, W) bool, broadcast over
    any band axis in between. Returns (median with NaN where no valid observation, count (H, W)
    as uint16).
    """
    values = np.asarray(values, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    if values.shape[0] == 0:
        shp = values.shape[1:]
        return np.full(shp, np.nan, np.float32), np.zeros(shp[-2:], np.uint16)
    v = valid.reshape((valid.shape[0],) + (1,) * (values.ndim - valid.ndim) + valid.shape[1:])
    v = v & np.isfinite(values) if values.ndim == valid.ndim else v
    masked = np.where(v, values, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        med = np.nanmedian(masked, axis=0)
    return med.astype(np.float32), valid.sum(axis=0).astype(np.uint16)


def month_index(start: str, end: str) -> np.ndarray:
    """Month starts (datetime64[M]) from the month of ``start`` to the month of ``end``."""
    return np.arange(np.datetime64(start, "M"), np.datetime64(end, "M") + np.timedelta64(1, "M"))


def to_month(dt64: np.datetime64 | str) -> np.datetime64:
    return np.datetime64(dt64, "M")
