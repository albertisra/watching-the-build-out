"""Four-state left-to-right hidden Markov model for construction phases (plan 6.3).

States 0 U (undisturbed), 1 Cl (cleared), 2 UC (under construction), 3 Co (complete, absorbing).

* Transitions: a_kk = 1 - h_k and a_k,k+1 = h_k for k = 0, 1, 2; a_33 = 1. Every other entry is a
  structural zero. Only the three exit probabilities h_k are parameters, so no estimation step can make
  a structural zero positive. A path from U straight to Co has probability 0.
* Priors (A72): h_0 ~ Beta(1, 59), h_1 ~ Beta(1, 2), h_2 ~ Beta(1, 5); initial ~ Dirichlet(1, 1, 1, 1).
* Emissions (A73): diagonal Gaussian per state; mu ~ N(0, 2^2), sigma^2 ~ InvGamma(3, 2).
* Missing months: emission factor 1; a partly missing vector uses the exact marginal of its observed
  features (for a diagonal Gaussian, the product over observed features).
* Estimation: supervised MAP from labelled phase sequences; MAP-EM with the same zero pattern, mixing
  labelled sequences (fixed states) and unlabelled sequences (posterior responsibilities). Labels may hold
  -1 (undetermined month, marginalised by a label-constrained forward-backward) and skips between adjacent
  months (counted as one exit per state passed, see ``split_labels``); decoding never allows a skip.
* Decoding: forward-backward marginals (primary), Viterbi (sensitivity). Computed in log space.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from scipy.special import logsumexp

N_STATES = 4
STATE_NAMES = ("U", "Cl", "UC", "Co")
EXIT_PRIOR = ((1.0, 59.0), (1.0, 2.0), (1.0, 5.0))  # Beta(a, b) on h_0, h_1, h_2
INIT_PRIOR = (1.0, 1.0, 1.0, 1.0)  # Dirichlet
MU_PRIOR_SD = 2.0
VAR_PRIOR = (3.0, 2.0)  # InvGamma(shape, scale)
ALLOWED = np.array([[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [0, 0, 0, 1]], bool)


def _prior_mode(a: float, b: float) -> float:
    return (a - 1) / (a + b - 2) if a + b > 2 else a / (a + b)


@dataclass
class HmmParams:
    h: np.ndarray  # (3,) exit probabilities
    mu: np.ndarray  # (K, d)
    var: np.ndarray  # (K, d)
    pi: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0]))

    @property
    def transmat(self) -> np.ndarray:
        return transition_matrix(self.h)

    @classmethod
    def prior_default(cls, d: int) -> HmmParams:
        """Parameters at the prior modes, a starting point for EM only."""
        h = np.array([_prior_mode(a, b) for a, b in EXIT_PRIOR])
        h = np.where(h <= 0, [a / (a + b) for a, b in EXIT_PRIOR], h)
        a, b = VAR_PRIOR
        return cls(h, np.zeros((N_STATES, d)), np.full((N_STATES, d), b / (a + 1)),
                   np.full(N_STATES, 0.25))


def transition_matrix(h) -> np.ndarray:
    h = np.asarray(h, float)
    if h.shape != (3,) or np.any(h < 0) or np.any(h > 1):
        raise ValueError("h must be three probabilities")
    a = np.zeros((N_STATES, N_STATES))
    for k in range(3):
        a[k, k], a[k, k + 1] = 1 - h[k], h[k]
    a[3, 3] = 1.0
    assert not np.any(a[~ALLOWED]), "structural zero violated"
    return a


def _log(a):
    with np.errstate(divide="ignore"):
        return np.log(a)


def log_emission(x: np.ndarray, p: HmmParams) -> np.ndarray:
    """(T, K) log emission densities; 0 in fully missing months, observed-feature marginal otherwise."""
    x = np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    obs = ~np.isnan(x)
    xz = np.where(obs, x, 0.0)
    ll = -0.5 * (np.log(2 * np.pi * p.var)[None] + (xz[:, None, :] - p.mu[None]) ** 2 / p.var[None])
    return np.where(obs[:, None, :], ll, 0.0).sum(axis=2)


@dataclass
class Posterior:
    gamma: np.ndarray  # (T, K) smoothed marginals P(z_t | x_1:T)
    filtered: np.ndarray  # (T, K) P(z_t | x_1:t)
    xi_counts: np.ndarray  # (K, K) expected transition counts
    log_evidence: float


def forward_backward(x: np.ndarray, p: HmmParams, allowed: np.ndarray | None = None,
                     use_pi: bool = True) -> Posterior:
    """Smoothed and filtered marginals. ``allowed`` (T, K) restricts states per month (label constraints);
    ``use_pi=False`` replaces the initial distribution by a flat one (a series segment that does not start
    at the first month)."""
    le = log_emission(x, p)
    if allowed is not None:
        le = np.where(allowed, le, -np.inf)
    t_len = le.shape[0]
    la = _log(p.transmat)
    lpi = _log(p.pi) if use_pi else np.zeros(N_STATES)
    alpha = np.empty((t_len, N_STATES))
    alpha[0] = lpi + le[0]
    for t in range(1, t_len):
        alpha[t] = logsumexp(alpha[t - 1][:, None] + la, axis=0) + le[t]
    beta = np.zeros((t_len, N_STATES))
    for t in range(t_len - 2, -1, -1):
        beta[t] = logsumexp(la + (le[t + 1] + beta[t + 1])[None, :], axis=1)
    log_ev = float(logsumexp(alpha[-1]))
    gamma = np.exp(alpha + beta - log_ev)
    filt = np.exp(alpha - logsumexp(alpha, axis=1, keepdims=True))
    xi = np.zeros((N_STATES, N_STATES))
    for t in range(t_len - 1):
        lx = alpha[t][:, None] + la + (le[t + 1] + beta[t + 1])[None, :] - log_ev
        xi += np.exp(lx)
    return Posterior(gamma, filt, xi, log_ev)


def viterbi(x: np.ndarray, p: HmmParams) -> np.ndarray:
    le = log_emission(x, p)
    t_len = le.shape[0]
    la = _log(p.transmat)
    delta = _log(p.pi) + le[0]
    back = np.zeros((t_len, N_STATES), int)
    for t in range(1, t_len):
        cand = delta[:, None] + la
        back[t] = np.argmax(cand, axis=0)
        delta = cand[back[t], np.arange(N_STATES)] + le[t]
    path = np.zeros(t_len, int)
    path[-1] = int(np.argmax(delta))
    for t in range(t_len - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def path_log_prob(path, p: HmmParams) -> float:
    """Prior log probability of a state path (no emissions); -inf for forbidden jumps."""
    path = np.asarray(path, int)
    la = _log(p.transmat)
    return float(_log(p.pi)[path[0]] + la[path[:-1], path[1:]].sum())


# ------------------------------------------------------------------ estimation


@dataclass
class _Stats:
    """Weighted sufficient statistics accumulated over sequences."""

    d: int
    trans: np.ndarray = None
    init: np.ndarray = None
    w: np.ndarray = None  # (K, d) weights of observed values
    sx: np.ndarray = None
    sxx: np.ndarray = None

    def __post_init__(self):
        self.trans = np.zeros((N_STATES, N_STATES))
        self.init = np.zeros(N_STATES)
        self.w = np.zeros((N_STATES, self.d))
        self.sx = np.zeros((N_STATES, self.d))
        self.sxx = np.zeros((N_STATES, self.d))

    def add(self, x: np.ndarray, resp: np.ndarray, trans: np.ndarray, init: bool = True) -> None:
        obs = ~np.isnan(x)
        xz = np.where(obs, x, 0.0)
        if init:
            self.init += resp[0]
        self.trans += trans
        self.w += resp.T @ obs.astype(float)
        self.sx += resp.T @ xz
        self.sxx += resp.T @ (xz ** 2)


def _as2d(x):
    x = np.asarray(x, float)
    return x[:, None] if x.ndim == 1 else x


UNDETERMINED = -1  # month whose phase the label cannot fix (labelling schema v2, ``phase_sequence``)


def _onehot(states: np.ndarray) -> np.ndarray:
    """One-hot responsibilities of a fully determined state sequence.

    Refuses negative states (e.g. ``UNDETERMINED``), which numpy indexing would otherwise wrap to state 3,
    and states >= N_STATES. Undetermined months are marginalised before this point (``fit_supervised``).
    """
    states = np.asarray(states)
    if states.ndim != 1 or (states.size and not np.issubdtype(states.dtype, np.integer)):
        raise ValueError("states must be a 1-d integer sequence")
    if np.any((states < 0) | (states >= N_STATES)):
        raise ValueError(f"states must be 0..{N_STATES - 1}; undetermined (-1) months are not one-hot encoded")
    states = states.astype(int)
    r = np.zeros((len(states), N_STATES))
    r[np.arange(len(states)), states] = 1.0
    return r


def _hard_trans(states: np.ndarray) -> np.ndarray:
    """Transition counts of a determined sequence whose consecutive months differ by at most 1."""
    c = np.zeros((N_STATES, N_STATES))
    np.add.at(c, (states[:-1], states[1:]), 1.0)
    return c


@dataclass
class LabelSplit:
    """A labelled sequence split where the strict chain cannot bridge two determined months."""

    segments: list[tuple[int, int]]  # [start, end) month ranges fitted as chains
    bridges: list[tuple[int, int]]  # (from_state, to_state) counted as one exit per state passed
    n_dropped: int  # undetermined months inside a bridge (no emission used)


def split_labels(z) -> LabelSplit:
    """Validate a label sequence (0..3, -1 undetermined) and split it at infeasible bridges.

    Determined months must be non-decreasing. Two consecutive determined months a < b with states i <= j
    need j - i <= b - a under the strict left-to-right chain. Otherwise (for example 0 then 2 in adjacent
    months: clearing not visible, or clearing and structures in the same month) the sequence is split
    there, the skip is counted as one exit from each state passed (no dwell month and no emission for a
    skipped state), and undetermined months between a and b are dropped.
    """
    z = np.asarray(z, int)
    if np.any((z < UNDETERMINED) | (z >= N_STATES)):
        raise ValueError("labels must be 0..3 or -1 (undetermined)")
    det = np.flatnonzero(z != UNDETERMINED)
    if det.size == 0:
        raise ValueError("label sequence without a determined month; fit it as unlabelled")
    if np.any(np.diff(z[det]) < 0):
        raise ValueError("labelled phase sequence violates the left-to-right order")
    segments, bridges, dropped, start = [], [], 0, 0
    for a, b in itertools.pairwise(det):
        i, j = int(z[a]), int(z[b])
        if j - i > b - a:
            segments.append((start, a + 1))
            bridges.append((i, j))
            dropped += b - a - 1
            start = b
    segments.append((start, len(z)))
    return LabelSplit(segments, bridges, dropped)


def _bridge_counts(bridges) -> np.ndarray:
    c = np.zeros((N_STATES, N_STATES))
    for i, j in bridges:
        for k in range(i, j):
            c[k, k + 1] += 1.0
    return c


def _add_labelled(s: _Stats, x: np.ndarray, z: np.ndarray, p: HmmParams | None) -> float:
    """Add the sufficient statistics of one labelled sequence; return its log likelihood under ``p``.

    Segments without undetermined months use hard counts. Segments with undetermined months use a
    label-constrained forward-backward under ``p`` (EM); with ``p`` None they contribute only their
    determined months as hard emissions (initialisation).
    """
    sp = split_labels(z)
    s.trans += _bridge_counts(sp.bridges)
    ll = 0.0
    if p is not None:
        ll += sum(float(np.sum(_log(p.h[i:j]))) for i, j in sp.bridges)
    for a, b in sp.segments:
        xs, zs = x[a:b], z[a:b]
        first = a == 0
        if np.all(zs != UNDETERMINED):
            s.add(xs, _onehot(zs), _hard_trans(zs), init=first)
            if p is not None:
                ll += float((log_emission(xs, p) * _onehot(zs)).sum())
                ll += float(_log(p.transmat)[zs[:-1], zs[1:]].sum())
                ll += float(_log(p.pi)[zs[0]]) if first else 0.0
        elif p is None:
            m = zs != UNDETERMINED
            r = np.zeros((len(zs), N_STATES))
            r[np.flatnonzero(m), zs[m]] = 1.0
            s.w += r.T @ (~np.isnan(xs)).astype(float)
            xz = np.where(np.isnan(xs), 0.0, xs)
            s.sx += r.T @ xz
            s.sxx += r.T @ xz ** 2
        else:
            allowed = np.ones((len(zs), N_STATES), bool)
            det = zs != UNDETERMINED
            allowed[det] = False
            allowed[np.flatnonzero(det), zs[det]] = True
            post = forward_backward(xs, p, allowed=allowed, use_pi=first)
            if not np.isfinite(post.log_evidence):
                raise ValueError("label constraints infeasible under the current parameters")
            s.add(xs, post.gamma, post.xi_counts, init=first)
            ll += post.log_evidence
    return ll


def _m_step(s: _Stats, n_iter_var: int = 50) -> HmmParams:
    h = np.empty(3)
    for k, (a, b) in enumerate(EXIT_PRIOR):
        n_exit, n_stay = s.trans[k, k + 1], s.trans[k, k]
        h[k] = (n_exit + a - 1) / (n_exit + n_stay + a + b - 2)
    h = np.clip(h, 0.0, 1.0)
    alpha = np.asarray(INIT_PRIOR)
    pi = (s.init + alpha - 1)
    pi = pi / pi.sum() if pi.sum() > 0 else np.full(N_STATES, 1 / N_STATES)
    a0, b0 = VAR_PRIOR
    tau0 = 1.0 / MU_PRIOR_SD ** 2
    var = np.full_like(s.w, b0 / (a0 + 1))
    mu = np.zeros_like(s.w)
    for _ in range(n_iter_var):  # coordinate ascent on the joint posterior mode of (mu, var)
        mu = (s.sx / var) / (s.w / var + tau0)
        ss = s.sxx - 2 * mu * s.sx + s.w * mu ** 2
        var_new = (b0 + 0.5 * ss) / (a0 + 1 + 0.5 * s.w)
        if np.allclose(var_new, var, rtol=1e-10, atol=1e-12):
            var = var_new
            break
        var = var_new
    return HmmParams(h, mu, var, pi)


def fit_supervised(series: list[np.ndarray], states: list[np.ndarray], n_iter: int = 100,
                   tol: float = 1e-8) -> HmmParams:
    """Supervised MAP from labelled monthly phase sequences (one label per calendar month).

    Labels are 0..3 or -1 (undetermined). Fully determined sequences give the closed-form MAP. Undetermined
    months are marginalised: EM with a label-constrained forward-backward, started from the determined
    months only. Skips between adjacent determined months are handled by ``split_labels``. The fitted
    model keeps the strict left-to-right zero pattern.
    """
    if not series:
        raise ValueError("no labelled series")
    data = []
    for x, z in zip(series, states, strict=True):
        x, z = _as2d(x), np.asarray(z, int)
        if len(x) != len(z):
            raise ValueError("series and labels differ in length")
        data.append((x, z))
    d = data[0][0].shape[1]
    s = _Stats(d)
    for x, z in data:
        _add_labelled(s, x, z, None)
    p = _m_step(s)
    if not any(np.any(z == UNDETERMINED) for _, z in data):
        return p
    for _ in range(n_iter):
        s = _Stats(d)
        for x, z in data:
            _add_labelled(s, x, z, p)
        p_new = _m_step(s)
        delta = max(np.max(np.abs(p_new.h - p.h)), np.max(np.abs(p_new.mu - p.mu)),
                    np.max(np.abs(p_new.var - p.var)), np.max(np.abs(p_new.pi - p.pi)))
        p = p_new
        if delta < tol:
            break
    return p


def log_prior(p: HmmParams) -> float:
    from scipy import stats

    lp = sum(stats.beta.logpdf(p.h[k], a, b) for k, (a, b) in enumerate(EXIT_PRIOR))
    lp += stats.norm.logpdf(p.mu, 0, MU_PRIOR_SD).sum()
    a0, b0 = VAR_PRIOR
    lp += stats.invgamma.logpdf(p.var, a0, scale=b0).sum()
    lp += stats.dirichlet.logpdf(np.clip(p.pi, 1e-300, None) / np.clip(p.pi, 1e-300, None).sum(),
                                 INIT_PRIOR)
    return float(lp)


def fit_map_em(labelled: list[tuple[np.ndarray, np.ndarray]], unlabelled: list[np.ndarray],
               init: HmmParams | None = None, n_iter: int = 200, tol: float = 1e-6
               ) -> tuple[HmmParams, list[float]]:
    """MAP-EM with the fixed zero pattern. Returns parameters and the log-posterior trace."""
    seqs = [_as2d(x) for x in unlabelled]
    lab = [(_as2d(x), np.asarray(z, int)) for x, z in labelled]
    d = (lab[0][0] if lab else seqs[0]).shape[1]
    if init is None:
        init = fit_supervised([x for x, _ in lab], [z for _, z in lab]) if lab \
            else HmmParams.prior_default(d)
    p = init
    trace: list[float] = []
    for _ in range(n_iter):
        s = _Stats(d)
        ll = 0.0
        for x, z in lab:
            ll += _add_labelled(s, x, z, p)
        for x in seqs:
            post = forward_backward(x, p)
            s.add(x, post.gamma, post.xi_counts)
            ll += post.log_evidence
        trace.append(ll + log_prior(p))
        p_new = _m_step(s)
        assert not np.any(p_new.transmat[~ALLOWED]), "structural zero violated in EM"
        p = p_new
        if len(trace) > 1 and abs(trace[-1] - trace[-2]) < tol * (1 + abs(trace[-1])):
            break
    return p, trace
