"""Bayesian online change-point detection for monthly multivariate series with missing months (plan 6.2).

Adams and MacKay (2007), recursion as in ``docs/research/bocpd.md`` rows 2 to 6, with these choices:

* Observation model: one Normal-Inverse-Gamma prior per feature (independent features), Student-t
  predictive per feature, multiplied over the features observed in that month.
* Constant hazard H = 1/lambda per calendar month.
* Missing month (all features NaN): predictive factor 1 for every run length, the hazard step still
  applies, sufficient statistics are not updated. A partly missing vector uses its observed features.
* Exact recursion, no pruning.

Convention: ``r_t = 0`` means month t is the first month of a new segment; the predictive of x_t under
``r_t = 0`` is the prior predictive. With this convention the run length of a series without change grows
by one per calendar month, and the change-point score of month t is c_t = P(r_{t+k} = k | x_{1:t+k}).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln, logsumexp

# Plan 6.2 / A75 fixed prior values; beta0, lambda, k and tau are tuned on development folds.
MU0, KAPPA0, ALPHA0 = 0.0, 1.0, 2.0
BETA0_GRID = (0.5, 1.0, 2.0)
LAMBDA_GRID = (12, 24, 48, 96)
LAG_GRID = (1, 2, 3)
TAU_GRID = (0.3, 0.5, 0.7)


@dataclass(frozen=True)
class BocpdConfig:
    beta0: float = 1.0
    lam: float = 24.0
    lag: int = 2
    tau: float = 0.5
    mu0: float = MU0
    kappa0: float = KAPPA0
    alpha0: float = ALPHA0


@dataclass
class BocpdResult:
    run_length: np.ndarray  # (T, T) posterior P(r_t = r | x_1:t); rows t, columns r (r <= t)
    log_evidence: np.ndarray  # (T,) log p(x_1:t)
    log_pred: np.ndarray  # (T,) log p(x_t | x_1:t-1); 0 for fully missing months


def _student_t_logpdf(x, mu, kappa, alpha, beta):
    """Log Student-t predictive of an NIG(mu, kappa, alpha, beta) prior. Arrays broadcast."""
    nu = 2.0 * alpha
    scale2 = beta * (kappa + 1.0) / (alpha * kappa)
    z2 = (x - mu) ** 2 / scale2
    return (gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(nu * np.pi * scale2)
            - (nu + 1) / 2 * np.log1p(z2 / nu))


def run(x: np.ndarray, cfg: BocpdConfig = BocpdConfig()) -> BocpdResult:
    """Exact BOCPD on ``x`` (T, d); NaN marks a missing feature-month."""
    x = np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    t_len, d = x.shape
    h = 1.0 / cfg.lam
    log_h, log_1mh = np.log(h), np.log1p(-h)
    # Sufficient statistics per run length r = 0..t (row index r), per feature.
    mu = np.full((1, d), cfg.mu0)
    kap = np.full((1, d), cfg.kappa0)
    alp = np.full((1, d), cfg.alpha0)
    bet = np.full((1, d), cfg.beta0)
    prior = (np.full((1, d), cfg.mu0), np.full((1, d), cfg.kappa0),
             np.full((1, d), cfg.alpha0), np.full((1, d), cfg.beta0))
    rl = np.zeros((t_len, t_len))
    log_ev = np.zeros(t_len)
    log_pred = np.zeros(t_len)
    log_joint_prev = None  # log P(r_{t-1}, x_1:t-1), length t
    for t in range(t_len):
        obs = ~np.isnan(x[t])
        if obs.any():
            xo = x[t, obs]
            lp_prior = float(_student_t_logpdf(xo, *(p[0, obs] for p in prior)).sum())
            lp_runs = (_student_t_logpdf(xo[None, :], mu[:, obs], kap[:, obs], alp[:, obs],
                                         bet[:, obs]).sum(axis=1) if t > 0 else np.zeros(0))
        else:
            lp_prior, lp_runs = 0.0, np.zeros(mu.shape[0] if t > 0 else 0)
        if t == 0:
            log_joint = np.array([lp_prior])
            prev_total = 0.0
        else:
            prev_total = logsumexp(log_joint_prev)
            grow = log_joint_prev + log_1mh + lp_runs  # r_t = r_{t-1} + 1
            cp = prev_total + log_h + lp_prior  # r_t = 0
            log_joint = np.concatenate([[cp], grow])
        total = logsumexp(log_joint)
        log_ev[t] = total
        log_pred[t] = total - prev_total
        rl[t, : t + 1] = np.exp(log_joint - total)
        # Update statistics: row 0 is a fresh run that has seen x_t; row r+1 extends row r.
        new = tuple(np.vstack([p, q]) for p, q in zip(prior, (mu, kap, alp, bet), strict=True)) \
            if t > 0 else prior
        mu_n, kap_n, alp_n, bet_n = (a.copy() for a in new)
        if obs.any():
            xo = x[t, obs]
            m, k, a, b = mu_n[:, obs], kap_n[:, obs], alp_n[:, obs], bet_n[:, obs]
            bet_n[:, obs] = b + k * (xo - m) ** 2 / (2 * (k + 1))
            mu_n[:, obs] = (k * m + xo) / (k + 1)
            kap_n[:, obs] = k + 1
            alp_n[:, obs] = a + 0.5
        mu, kap, alp, bet = mu_n, kap_n, alp_n, bet_n
        log_joint_prev = log_joint
    return BocpdResult(rl, log_ev, log_pred)


def changepoint_scores(res: BocpdResult, lag: int) -> np.ndarray:
    """c_t = P(r_{t+lag} = lag | x_1:t+lag); NaN where t + lag is beyond the series."""
    t_len = res.run_length.shape[0]
    c = np.full(t_len, np.nan)
    for t in range(t_len - lag):
        c[t] = res.run_length[t + lag, lag]
    return c


def changepoints(res: BocpdResult, lag: int, tau: float) -> list[int]:
    """Months t >= 1 that are local maxima of c_t with c_t >= tau (month 0 starts the series)."""
    c = changepoint_scores(res, lag)
    out = []
    for t in range(1, len(c)):
        if np.isnan(c[t]) or c[t] < tau:
            continue
        left = c[t - 1] if not np.isnan(c[t - 1]) else -np.inf
        right = c[t + 1] if t + 1 < len(c) and not np.isnan(c[t + 1]) else -np.inf
        if c[t] >= left and c[t] > right:
            out.append(t)
    return out


def label_segments(x: np.ndarray, cps: list[int], log_emission) -> np.ndarray:
    """Monotone U, Cl, UC, Co labels per month for the segments between change points (plan 6.2).

    ``log_emission(x)`` returns the (T, K) per-month log emission under the frozen HMM, with 0 in
    missing months. Labels are non-decreasing over segments and maximise the summed log likelihood
    (dynamic programming). Returns a length-T state path.
    """
    x = np.asarray(x, float)
    t_len = x.shape[0]
    le = log_emission(x)
    n_k = le.shape[1]
    bounds = [0, *sorted(c for c in cps if 0 < c < t_len), t_len]
    segs = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    seg_ll = np.array([le[a:b].sum(axis=0) for a, b in segs])  # (S, K)
    n_s = len(segs)
    score = np.full((n_s, n_k), -np.inf)
    back = np.zeros((n_s, n_k), int)
    score[0] = seg_ll[0]
    for s in range(1, n_s):
        best = np.maximum.accumulate(score[s - 1])
        arg = np.array([int(np.argmax(score[s - 1][: k + 1])) for k in range(n_k)])
        score[s] = best + seg_ll[s]
        back[s] = arg
    lab = np.zeros(n_s, int)
    lab[-1] = int(np.argmax(score[-1]))
    for s in range(n_s - 1, 0, -1):
        lab[s - 1] = back[s, lab[s]]
    path = np.zeros(t_len, int)
    for (a, b), k in zip(segs, lab, strict=True):
        path[a:b] = k
    return path


def alert_month(res: BocpdResult, lag: int, tau: float) -> int | None:
    """Online alert: first month at which a change point is confirmed (c_t >= tau seen at t + lag)."""
    c = changepoint_scores(res, lag)
    for t in range(1, len(c)):
        if not np.isnan(c[t]) and c[t] >= tau:
            return t + lag
    return None
