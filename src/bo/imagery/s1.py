"""Sentinel-1 helpers: orbit selection, dB conversion, optional speckle filter."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .config import S1_NODATA


@dataclass(frozen=True)
class OrbitChoice:
    relative_orbit: int
    direction: str  # "ascending" or "descending"
    n_dates: int
    candidates: tuple[tuple[int, str, int], ...]  # (orbit, direction, n_dates), all that cover


def select_orbit(records: list[dict]) -> OrbitChoice | None:
    """Choose the single (relative orbit, direction) series for a site.

    ``records`` hold ``relative_orbit``, ``direction``, ``date`` (acquisition day) and ``covers``
    (the scene footprint contains the whole chip). Only covering scenes count. The group with the
    most distinct acquisition dates wins; ties go to the lower relative orbit number, then to
    ascending, so the choice is deterministic. Registry fields play no role. Rule A7.
    """
    groups: dict[tuple[int, str], set] = {}
    for r in records:
        if not r.get("covers", False):
            continue
        groups.setdefault((int(r["relative_orbit"]), str(r["direction"])), set()).add(r["date"])
    if not groups:
        return None
    ranked = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]))
    (orb, direc), dates = ranked[0]
    cands = tuple((o, d, len(s)) for (o, d), s in ranked)
    return OrbitChoice(orb, direc, len(dates), cands)


# Validity window for Sentinel-1 sigma0/gamma0 in dB (assumption A42). Values outside are fill or border
# noise, not backscatter; they become NaN and the pixel count becomes 0.
S1_DB_FLOOR = {"vv": -30.0, "vh": -35.0}
S1_DB_CEIL = 25.0


def mask_s1_db(vv: np.ndarray, vh: np.ndarray | None = None, count: np.ndarray | None = None):
    """Mask out-of-range dB values to NaN (never interpolated). Returns (vv, vh, count, n_masked_vv, n_masked_vh).

    A pixel whose VV is masked gets count 0 (count follows VV, as in the feature build)."""
    def one(a, floor):
        a = np.array(a, dtype=np.float32, copy=True)
        with np.errstate(invalid="ignore"):
            bad = np.isfinite(a) & ((a < floor) | (a > S1_DB_CEIL))
        a[bad] = np.nan
        return a, bad

    vv2, bad_v = one(vv, S1_DB_FLOOR["vv"])
    vh2, bad_h = (one(vh, S1_DB_FLOOR["vh"]) if vh is not None else (None, np.zeros_like(bad_v)))
    cnt = None
    if count is not None:
        cnt = np.array(count, copy=True)
        cnt[bad_v] = 0
    return vv2, vh2, cnt, bad_v, bad_h


def to_db(linear: np.ndarray, nodata: float = S1_NODATA) -> np.ndarray:
    """Linear power to dB. Nodata, non-finite and non-positive values become NaN."""
    a = np.asarray(linear, dtype=np.float32)
    bad = ~np.isfinite(a) | (a <= 0) | (a == nodata)
    out = np.full(a.shape, np.nan, np.float32)
    np.log10(a, out=out, where=~bad)
    out = np.where(bad, np.nan, 10.0 * out).astype(np.float32)
    return out


def speckle_filter(linear: np.ndarray, method: str | None) -> np.ndarray:
    """Optional speckle filter on linear power (NaN-aware). ``None`` returns the input.

    "boxcar3": 3 x 3 mean. "lee5": Lee filter in a 5 x 5 window with the equivalent number of
    looks fixed to 4.4, the IW GRD HR value in docs/research/sentinel1.md fact 15.
    """
    if method is None:
        return linear
    a = np.asarray(linear, dtype=np.float32)
    ok = np.isfinite(a) & (a > 0)
    filled = np.where(ok, a, 0.0)
    if method == "boxcar3":
        size = 3
    elif method == "lee5":
        size = 5
    else:
        raise ValueError(f"unknown speckle filter {method!r}")
    w = ndimage.uniform_filter(ok.astype(np.float32), size=size)
    s1 = ndimage.uniform_filter(filled, size=size)
    mean = np.where(w > 0, s1 / np.maximum(w, 1e-9), np.nan)
    if method == "boxcar3":
        out = mean
    else:
        s2 = ndimage.uniform_filter(filled**2, size=size)
        var = np.maximum(np.where(w > 0, s2 / np.maximum(w, 1e-9), np.nan) - mean**2, 0.0)
        cu2 = 1.0 / 4.4
        ci2 = var / np.maximum(mean**2, 1e-12)
        k = np.clip(1.0 - cu2 / np.maximum(ci2, 1e-12), 0.0, 1.0)
        out = mean + k * (a - mean)
    return np.where(ok, out, np.nan).astype(np.float32)
