"""Site-level detection rule and threshold selection (plan 2.4, A81).

A target is detected if p_c,t >= theta_c in at least ``k`` (= 2) usable months of the evaluation window. This equals
"the k-th largest usable monthly p is >= theta", so each target gets one score s_k and detection is s_k >= theta.
A target with fewer than k usable months cannot be detected (score -inf).

theta_c maximises F1 over development targets from out-of-fold scores. Candidates are the distinct finite scores
(the F1 of any other theta equals that of the next candidate above it). Ties in F1 go to the largest theta, the
most conservative choice for a national scan (assumption M5).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .design import MIN_DETECTED_MONTHS


def kth_largest(p: np.ndarray, k: int) -> float:
    p = np.asarray(p, dtype="float64")
    p = p[np.isfinite(p)]
    if len(p) < k:
        return float("-inf")
    return float(np.sort(p)[-k])


def site_scores(pred: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, k: int = MIN_DETECTED_MONTHS,
                usable_col: str = "usable") -> pd.DataFrame:
    """Per (site, technology): k-th largest p over usable months in [start, end], and the usable month count."""
    w = pred[(pred["month"] >= start) & (pred["month"] <= end)]
    w = w[w[usable_col].astype(bool)] if usable_col in w else w
    g = w.groupby(["site_id", "technology"])
    out = g["p"].agg(lambda s: kth_largest(s.to_numpy(), k)).rename("score").to_frame()
    out["n_usable"] = g["p"].count()
    # sites with no usable month in the window still need a row (they count as not detected)
    allsites = pred[["site_id", "technology"]].drop_duplicates().set_index(["site_id", "technology"])
    out = allsites.join(out, how="left")
    out["score"] = out["score"].fillna(float("-inf"))
    out["n_usable"] = out["n_usable"].fillna(0).astype(int)
    return out.reset_index()


@dataclass(frozen=True)
class ThresholdResult:
    theta: float
    f1: float
    precision: float
    recall: float
    n_pos: int
    n_neg: int


def f1_at(y: np.ndarray, score: np.ndarray, theta: float) -> tuple[float, float, float]:
    y = np.asarray(y, bool)
    det = np.asarray(score, dtype="float64") >= theta
    tp = int((det & y).sum())
    fp = int((det & ~y).sum())
    fn = int((~det & y).sum())
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")
    return f1, prec, rec


def select_threshold(y: np.ndarray, score: np.ndarray) -> ThresholdResult:
    """theta maximising F1 of ``score >= theta``; ties to the largest theta."""
    y = np.asarray(y, dtype="float64")
    s = np.asarray(score, dtype="float64")
    keep = ~np.isnan(y)
    y, s = y[keep].astype(bool), s[keep]
    if not y.any():
        raise ValueError("threshold selection needs at least one positive target")
    cand = np.unique(s[np.isfinite(s)])
    if len(cand) == 0:
        raise ValueError("no finite score")
    # vectorised: detection matrix (candidates x targets)
    det = s[None, :] >= cand[:, None]
    tp = (det & y[None, :]).sum(1)
    fp = (det & ~y[None, :]).sum(1)
    fn = y.sum() - tp
    f1 = 2 * tp / np.maximum(2 * tp + fp + fn, 1)
    best = np.flatnonzero(f1 == f1.max()).max()
    theta = float(cand[best])
    f, p, r = f1_at(y, s, theta)
    return ThresholdResult(theta=theta, f1=f, precision=p, recall=r, n_pos=int(y.sum()), n_neg=int((~y).sum()))
