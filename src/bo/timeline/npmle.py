"""Self-consistency NPMLE for interval-censored, right-censored and truncated data on the real line (plan 7.3).

Each observation i has a censoring interval A_i = (l_i, r_i] that contains the true value (r_i = +inf for
right censoring) and a truncation interval B_i = (u_i, v_i] that contains A_i: the observation entered the
sample only because its value fell in B_i. Right truncation (registry sites satisfy R <= T_x, so
L <= T_x - S) is B_i = (-inf, tau_i].

Support: Turnbull's innermost intervals of the censoring intervals {A_i}, i.e. elementary intervals
(e_k, e_k+1] whose left end is some l_i and whose right end is some r_i. Following Frydman (1994; cited
as SECONDARY in ``docs/research/bocpd.md`` row 24), the support is built from the A_i only, not from the
truncation bounds. Values may be negative: nothing assumes positive support.

Update (Turnbull 1976): with alpha_ij = 1[q_j in A_i], beta_ij = 1[q_j in B_i],
  p_j <- sum_i [ alpha_ij p_j / sum_k alpha_ik p_k + (1 - beta_ij) p_j / sum_k beta_ik p_k ] / M,
where M normalises. The second term adds the "ghost" observations lost to truncation.
Mass in a support interval that no B_i contains is not identified; ``identified`` flags it and the
caller must report such tail quantities as bounds.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np


@dataclass
class Npmle:
    left: np.ndarray  # support interval left ends
    right: np.ndarray  # support interval right ends
    p: np.ndarray  # mass per support interval
    identified: np.ndarray  # bool, support interval lies in at least one truncation interval
    n_iter: int
    converged: bool
    log_lik: float

    def cdf_bounds(self, t: float) -> tuple[float, float]:
        """Lower and upper bounds of F(t): mass inside an interval straddling t is undetermined."""
        lo = float(self.p[self.right <= t].sum())
        hi = float(self.p[self.left < t].sum())
        return lo, hi

    def cdf(self, t: float) -> float:
        """F(t) with each interval's mass placed at its right end (the lower bound)."""
        return self.cdf_bounds(t)[0]

    def quantile(self, q: float) -> float:
        """Smallest right end with F >= q (right end convention); inf if not reached."""
        c = np.cumsum(self.p)
        idx = np.flatnonzero(c >= q - 1e-12)
        return float(self.right[idx[0]]) if idx.size else float("inf")


def innermost_intervals(lo: np.ndarray, hi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lset = set(np.asarray(lo, float).tolist())
    rset = set(np.asarray(hi, float).tolist())
    pts = np.array(sorted(lset | rset))
    keep_l, keep_r = [], []
    for a, b in itertools.pairwise(pts):
        if a in lset and b in rset:
            keep_l.append(a)
            keep_r.append(b)
    return np.array(keep_l), np.array(keep_r)


def _em_map(a_f: np.ndarray, b_f: np.ndarray, truncated: bool):
    """Return the self-consistency map p -> F(p) and the log-likelihood for fixed design matrices."""

    def em(p: np.ndarray) -> np.ndarray:
        da = a_f @ p
        num = (a_f / da[:, None]).sum(axis=0) * p
        if truncated:
            db = b_f @ p
            num = num + ((1.0 - b_f) / db[:, None]).sum(axis=0) * p
        return num / num.sum()

    def loglik(p: np.ndarray) -> float:
        with np.errstate(divide="ignore"):
            return float(np.sum(np.log(a_f @ p)) - np.sum(np.log(b_f @ p)))

    return em, loglik


def fit(lo, hi, trunc_lo=None, trunc_hi=None, max_iter: int = 20000, tol: float = 1e-9,
        method: str = "em") -> Npmle:
    """NPMLE of the distribution of a real-valued variable from (lo, hi] intervals.

    ``trunc_lo`` / ``trunc_hi`` give (u_i, v_i]; default (-inf, +inf), i.e. no truncation.

    ``method="em"`` (default, analysis plan v1.0 Section 7.3): plain self-consistency, stopped when
    max |p_new - p| < tol. ``method="squarem"``: SQUAREM acceleration (Varadhan and Roland 2008, scheme
    SqS3) of the same map, offered as an option only (proposed deviation P4, awaiting the author). Each
    SQUAREM cycle uses two map evaluations for the extrapolation and one stabilising evaluation; the step
    is backtracked towards alpha = -1 (two plain EM steps) until it stays in the simplex, and falls back
    to two plain EM steps if the log-likelihood would fall. It stops when the plain-EM residual
    max |F(p) - p| < tol, i.e. the same fixed-point criterion as ``em``. ``n_iter`` counts map
    evaluations for both methods, so the two are comparable.
    """
    if method not in ("em", "squarem"):
        raise ValueError("method must be 'em' or 'squarem'")
    lo = np.asarray(lo, float)
    hi = np.asarray(hi, float)
    n = lo.size
    u = np.full(n, -np.inf) if trunc_lo is None else np.asarray(trunc_lo, float)
    v = np.full(n, np.inf) if trunc_hi is None else np.asarray(trunc_hi, float)
    if np.any(~(lo < hi)):
        raise ValueError("every censoring interval needs lo < hi")
    if np.any(lo < u) or np.any(hi > v):
        raise ValueError("censoring interval outside its truncation interval")
    ql, qr = innermost_intervals(lo, hi)
    alpha = (lo[:, None] <= ql[None, :]) & (qr[None, :] <= hi[:, None])
    beta = (u[:, None] <= ql[None, :]) & (qr[None, :] <= v[:, None])
    if not alpha.any(axis=1).all():
        raise ValueError("an observation contains no support interval")
    a_f, b_f = alpha.astype(float), beta.astype(float)
    p = np.full(ql.size, 1.0 / ql.size)
    truncated = not beta.all()
    em, loglik = _em_map(a_f, b_f, truncated)
    if method == "em":
        p, it, converged = _run_em(em, p, max_iter, tol)
    else:
        p, it, converged = _run_squarem(em, loglik, p, max_iter, tol)
    return Npmle(ql, qr, p, beta.any(axis=0), it, converged, loglik(p))


def _run_em(em, p, max_iter, tol):
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        p_new = em(p)
        if np.max(np.abs(p_new - p)) < tol:
            p = p_new
            converged = True
            break
        p = p_new
    return p, it, converged


def _run_squarem(em, loglik, p, max_iter, tol, max_backtrack: int = 20):
    evals = 0
    ll = loglik(p)
    while evals < max_iter:
        p1 = em(p)
        evals += 1
        r = p1 - p
        if np.max(np.abs(r)) < tol:
            return p1, evals, True
        p2 = em(p1)
        evals += 1
        v = p2 - 2.0 * p1 + p
        nv = np.sqrt(np.sum(v * v))
        if nv == 0.0:
            p, ll = p2, loglik(p2)
            continue
        a = min(-np.sqrt(np.sum(r * r)) / nv, -1.0)
        cand = None
        for _ in range(max_backtrack):
            q = p - 2.0 * a * r + a * a * v
            if np.all(q >= 0.0) and q.sum() > 0:
                cand = q / q.sum()
                break
            a = (a - 1.0) / 2.0
        if cand is None:
            cand = p2
        q = em(cand)  # stabilising step
        evals += 1
        ll_q = loglik(q)
        if not np.isfinite(ll_q) or ll_q < ll - 1e-12 * max(1.0, abs(ll)):
            p, ll = p2, loglik(p2)
        else:
            p, ll = q, ll_q
    return p, evals, False
