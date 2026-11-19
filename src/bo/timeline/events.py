"""Event dates from state posteriors (plan 2.3) and the bracket error (plan 7.2).

With left-to-right transitions the smoothed marginals give event CDFs over month indices 0..T-1:

* construction start S: F_S(t) = P(z_t >= 1 | x)
* start of structures S': F_S'(t) = P(z_t >= 2 | x)
* completion E: F_E(t) = P(z_t = 3 | x)

Point estimate: posterior median month (first t with F(t) >= 0.5). Interval: 5 % and 95 % quantiles.
Status: ``before_series`` if F(0) >= 0.5 (left-censored), ``not_detected`` if F(T-1) < 0.5, else
``detected``. A quantile that the series does not reach is returned as None (beyond the series).
Quantity type of every output: detected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

EVENTS = {"S": 1, "S_prime": 2, "E": 3}
Q_LO, Q_MED, Q_HI = 0.05, 0.5, 0.95
_TOL = 1e-9


@dataclass(frozen=True)
class EventEstimate:
    event: str
    status: str  # detected | not_detected | before_series
    median: int | None
    lo: int | None
    hi: int | None


def event_cdf(gamma: np.ndarray, event: str) -> np.ndarray:
    """P(event month <= t | x) from smoothed marginals (T, 4); non-decreasing up to rounding."""
    k = EVENTS[event]
    f = np.asarray(gamma)[:, k:].sum(axis=1)
    if np.any(np.diff(f) < -1e-6):
        raise ValueError("event CDF decreases: marginals are not from a left-to-right model")
    return np.clip(np.maximum.accumulate(f), 0.0, 1.0)


def cdf_quantile(f: np.ndarray, q: float) -> int | None:
    idx = np.flatnonzero(f >= q - _TOL)
    return int(idx[0]) if idx.size else None


def estimate_event(gamma: np.ndarray, event: str) -> EventEstimate:
    f = event_cdf(gamma, event)
    if f[0] >= Q_MED - _TOL:
        status = "before_series"
    elif f[-1] < Q_MED - _TOL:
        status = "not_detected"
    else:
        status = "detected"
    med = cdf_quantile(f, Q_MED) if status == "detected" else None
    return EventEstimate(event, status, med, cdf_quantile(f, Q_LO), cdf_quantile(f, Q_HI))


def estimate_from_path(path: np.ndarray, event: str) -> EventEstimate:
    """Same rules for a hard state path (Viterbi or BOCPD segment labels); no interval."""
    k = EVENTS[event]
    idx = np.flatnonzero(np.asarray(path) >= k)
    if idx.size == 0:
        return EventEstimate(event, "not_detected", None, None, None)
    if idx[0] == 0:
        return EventEstimate(event, "before_series", None, None, None)
    return EventEstimate(event, "detected", int(idx[0]), int(idx[0]), int(idx[0]))


def alert_month(filtered: np.ndarray, threshold: float = 0.5) -> int | None:
    """First t with filtered P(z_t >= 1 | x_1:t) >= threshold (plan 2.3, operational lead only)."""
    p = np.asarray(filtered)[:, 1:].sum(axis=1)
    idx = np.flatnonzero(p >= threshold - _TOL)
    return int(idx[0]) if idx.size else None


def bracket_error(detected: float | None, a: float, b: float) -> float:
    """Signed bracket error in months (plan 7.2).

    0 if ``detected`` lies in [a, b]; otherwise the signed distance to the nearer end (negative when the
    detection is early). A miss (``None``) is +inf, outside every tolerance.
    """
    if a > b:
        raise ValueError("bracket with a > b")
    if detected is None or (isinstance(detected, float) and math.isnan(detected)):
        return math.inf
    if detected < a:
        return float(detected - a)
    if detected > b:
        return float(detected - b)
    return 0.0


def capped_abs_error(e: float, cap: float = 12.0) -> float:
    """Tuning loss term of plan 4.4: min(|e|, 12), a miss counts as 12."""
    return cap if not math.isfinite(e) else min(abs(e), cap)
