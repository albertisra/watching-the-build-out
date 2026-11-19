"""Plan 6.4 software tests for the timeline models. Synthetic data only."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest
from scipy.special import logsumexp

from bo.paths import SEED
from bo.timeline import bocpd, events, hmm, npmle
from bo.timeline import simulate as sim

# ------------------------------------------------------------------ BOCPD


def _seg_ll(x, cfg):
    tot = 0.0
    for j in range(x.shape[1]):
        m, k, a, b = cfg.mu0, cfg.kappa0, cfg.alpha0, cfg.beta0
        for v in x[:, j]:
            if np.isnan(v):
                continue
            tot += float(bocpd._student_t_logpdf(v, m, k, a, b))
            b = b + k * (v - m) ** 2 / (2 * (k + 1))
            m = (k * m + v) / (k + 1)
            k += 1
            a += 0.5
    return tot


def test_bocpd_evidence_matches_brute_force_with_gaps():
    cfg = bocpd.BocpdConfig(beta0=1.0, lam=4.0)
    rng = np.random.default_rng(SEED)
    t_len = 7
    x = rng.normal(0, 1, (t_len, 2))
    x[2] = np.nan
    x[4, 1] = np.nan
    x[5:] += 3
    h = 1 / cfg.lam
    terms = []
    for cp in itertools.product([0, 1], repeat=t_len - 1):
        b = [0] + [i + 1 for i, c in enumerate(cp) if c] + [t_len]
        lp = sum(math.log(h) if c else math.log1p(-h) for c in cp)
        lp += sum(_seg_ll(x[b[i]:b[i + 1]], cfg) for i in range(len(b) - 1))
        terms.append(lp)
    assert bocpd.run(x, cfg).log_evidence[-1] == pytest.approx(logsumexp(terms), abs=1e-10)


def test_runlength_probabilities_sum_to_one():
    assert sim.runlength_sum_max_dev() <= 1e-9


def test_constant_series_runlength_grows_per_calendar_month():
    assert sim.constant_series_check()


def test_missing_month_leaves_evidence_unchanged():
    d = sim.missing_month_evidence()
    assert d["bocpd_missing_month"] <= 1e-9
    assert d["hmm_trailing_missing"] <= 1e-9
    assert d["hmm_missing_month_quadrature"] <= 1e-6
    assert d["hmm_partial_month_quadrature"] <= 1e-6


def test_bocpd_finds_large_step():
    rng = np.random.default_rng(SEED)
    x = rng.normal(0, 0.3, (40, 2))
    x[20:, 0] += 3.0
    res = bocpd.run(x, bocpd.BocpdConfig(beta0=0.5, lam=24))
    assert 20 in bocpd.changepoints(res, lag=2, tau=0.5)


def test_bocpd_segment_labels_are_monotone():
    rng = np.random.default_rng(SEED)
    s = sim.simulate_series(rng)
    p = hmm.fit_supervised([s.x], [s.z])
    path = bocpd.label_segments(s.x, [10, 20, 30, 40], lambda x: hmm.log_emission(x, p))
    assert np.all(np.diff(path) >= 0)


# ------------------------------------------------------------------ HMM


def _params():
    return hmm.HmmParams(np.array([0.2, 0.5, 0.3]), sim.MEANS.copy(), np.ones((4, 3)),
                         np.array([0.4, 0.3, 0.2, 0.1]))


def test_hmm_forward_backward_and_viterbi_match_enumeration():
    p = _params()
    rng = np.random.default_rng(SEED)
    t_len = 6
    x = rng.normal(0, 1, (t_len, 3))
    x[2] = np.nan
    x[3, 0] = np.nan
    le = hmm.log_emission(x, p)
    paths = list(itertools.product(range(4), repeat=t_len))
    lp = np.array([hmm.path_log_prob(np.array(z), p) + le[np.arange(t_len), z].sum() for z in paths])
    ev = logsumexp(lp)
    post = hmm.forward_backward(x, p)
    assert post.log_evidence == pytest.approx(ev, abs=1e-10)
    marg = np.zeros((t_len, 4))
    w = np.exp(lp - ev)
    for z, wi in zip(paths, w, strict=True):
        marg[np.arange(t_len), z] += wi
    np.testing.assert_allclose(post.gamma, marg, atol=1e-10)
    assert list(hmm.viterbi(x, p)) == list(paths[int(np.argmax(lp))])


def test_hmm_zero_pattern_survives_estimation():
    d = sim.zero_pattern_checks()
    assert d["max_forbidden_entry_supervised"] == 0.0
    assert d["max_forbidden_entry_em"] == 0.0
    assert d["max_forbidden_entry_em_unlabelled_only"] == 0.0
    assert d["em_trace_min_increment"] >= -1e-6


def test_u_to_co_path_has_zero_probability():
    p = _params()
    assert hmm.path_log_prob(np.array([0, 0, 3, 3]), p) == -np.inf
    assert hmm.path_log_prob(np.array([0, 2, 3]), p) == -np.inf
    assert hmm.path_log_prob(np.array([0, 1, 2, 3]), p) > -np.inf
    # Even with emissions that scream "complete", the posterior never puts U then Co adjacent.
    x = np.vstack([np.tile(sim.MEANS[0], (5, 1)), np.tile(sim.MEANS[3], (5, 1))])
    post = hmm.forward_backward(x, p)
    assert post.xi_counts[0, 3] == 0.0 and post.xi_counts[0, 2] == 0.0


def test_transition_matrix_rejects_bad_h():
    with pytest.raises(ValueError):
        hmm.transition_matrix([0.1, 1.2, 0.1])


def test_supervised_fit_rejects_backward_labels():
    with pytest.raises(ValueError):
        hmm.fit_supervised([np.zeros((3, 1))], [np.array([0, 2, 1])])
    with pytest.raises(ValueError):
        hmm.fit_supervised([np.zeros((3, 1))], [np.array([-1, -1, -1])])
    with pytest.raises(ValueError):
        hmm.fit_supervised([np.zeros((3, 1))], [np.array([0, 4, 4])])


# ------------------------------------------------------------------ labels with skips and -1 (review N1)


def _labelled_set(seed=SEED, n=40):
    rng = np.random.default_rng(seed)
    out = [sim.simulate_series(rng) for _ in range(n)]
    return [s.x for s in out], [s.z.copy() for s in out]


def test_split_labels():
    sp = hmm.split_labels([0, 0, 2, 2, 3])
    assert sp.segments == [(0, 2), (2, 5)] and sp.bridges == [(0, 2)] and sp.n_dropped == 0
    sp = hmm.split_labels([0, -1, 3, 3])
    assert sp.bridges == [(0, 3)] and sp.n_dropped == 1
    sp = hmm.split_labels([-1, 0, -1, -1, 2, 3])  # feasible bridge: 2 steps in 3 months
    assert sp.segments == [(0, 6)] and sp.bridges == []


def test_skip_labels_are_fitted_and_zero_pattern_kept():
    xs, zs = _labelled_set()
    for z in zs[:10]:  # clearing not visible: U straight to UC
        z[z == 1] = 2
    p = hmm.fit_supervised(xs, zs)
    assert not np.any(p.transmat[~hmm.ALLOWED])
    assert 0 < p.h[1] <= 1


def test_skip_counts_one_exit_per_state_passed():
    x = np.zeros((4, 1))
    p_skip = hmm.fit_supervised([x], [np.array([0, 0, 2, 2])])
    # Cl had one exit and no stay: MAP under Beta(1, 2) is 1 / (1 + 1) = 0.5.
    assert p_skip.h[1] == pytest.approx(0.5)
    # U had one stay and one exit: (1) / (2 + 58).
    assert p_skip.h[0] == pytest.approx(1 / 60)


def test_leading_undetermined_months_are_not_state_3():
    xs, zs = _labelled_set()
    z_unk = [z.copy() for z in zs]
    z_zero = [z.copy() for z in zs]
    for zu, zz in zip(z_unk[:10], z_zero[:10], strict=True):
        zu[:3] = -1  # leading undetermined months; monotonicity forces them to U
        zz[:3] = 0
    p_unk = hmm.fit_supervised(xs, z_unk)
    p_zero = hmm.fit_supervised(xs, z_zero)
    np.testing.assert_allclose(p_unk.mu, p_zero.mu, atol=1e-8)
    np.testing.assert_allclose(p_unk.h, p_zero.h, atol=1e-8)


def test_undetermined_months_are_marginalised():
    xs, zs = _labelled_set()
    z_unk = [z.copy() for z in zs]
    for z in z_unk[:20]:
        s = int(np.argmax(z >= 1))
        z[s - 1:s + 2] = -1  # bracket around the start
    p = hmm.fit_supervised(xs, z_unk)
    p_full = hmm.fit_supervised(xs, zs)
    assert not np.any(p.transmat[~hmm.ALLOWED])
    np.testing.assert_allclose(p.mu, p_full.mu, atol=0.2)
    # An infeasible bridge (U, undetermined, Co) is split and its undetermined month dropped.
    p2 = hmm.fit_supervised([np.zeros((4, 1))], [np.array([0, -1, 3, 3])])
    assert np.all(np.isfinite(p2.mu))


def test_map_em_accepts_skips_and_undetermined():
    xs, zs = _labelled_set(n=20)
    for z in zs[:5]:
        z[z == 1] = 2
    zs[6][:2] = -1
    rng = np.random.default_rng(SEED + 1)
    unl = [sim.simulate_series(rng).x for _ in range(10)]
    p, trace = hmm.fit_map_em(list(zip(xs, zs, strict=True)), unl, n_iter=30)
    assert not np.any(p.transmat[~hmm.ALLOWED])
    assert np.min(np.diff(trace)) >= -1e-6


# ------------------------------------------------------------------ events


def test_event_rules():
    g = np.zeros((6, 4))
    g[:, 0] = [1, 1, 0.6, 0.2, 0, 0]
    g[:, 1] = [0, 0, 0.4, 0.5, 0.3, 0]
    g[:, 2] = [0, 0, 0, 0.3, 0.6, 0.4]
    g[:, 3] = [0, 0, 0, 0, 0.1, 0.6]
    s = events.estimate_event(g, "S")
    assert (s.status, s.median, s.lo, s.hi) == ("detected", 3, 2, 4)
    e = events.estimate_event(g, "E")
    assert (e.status, e.median) == ("detected", 5)
    assert events.estimate_event(np.tile([0.2, 0.8, 0, 0], (4, 1)), "S").status == "before_series"
    assert events.estimate_event(np.tile([0.9, 0.1, 0, 0], (4, 1)), "S").status == "not_detected"
    assert events.estimate_from_path(np.array([0, 0, 1, 2, 3]), "S_prime").median == 3
    assert events.alert_month(np.array([[1, 0, 0, 0], [0.6, 0.4, 0, 0], [0.3, 0.7, 0, 0]])) == 2


def test_bracket_error():
    assert events.bracket_error(5, 4, 6) == 0
    assert events.bracket_error(2, 4, 6) == -2
    assert events.bracket_error(9, 4, 6) == 3
    assert events.bracket_error(None, 4, 6) == math.inf
    assert events.capped_abs_error(math.inf) == 12
    assert events.capped_abs_error(-20) == 12
    with pytest.raises(ValueError):
        events.bracket_error(1, 3, 2)


# ------------------------------------------------------------------ recovery (plan 6.4 [P])


# Known failures at the registered seed (results/timeline/simulation_checks.csv, 2026-11-19). The plan
# threshold is not changed; strict xfail turns the suite red if a scenario starts to pass unexpectedly.
_HMM_FAIL = pytest.mark.xfail(strict=True, reason="plan 6.4 recovery threshold not met; see CSV")


@pytest.mark.parametrize("gaps", [pytest.param(g, marks=_HMM_FAIL) for g in sim.GAP_SCENARIOS])
def test_hmm_recovery_threshold(gaps):
    """Plan 6.4: S and E within 1 month in >= 90 % of 200 series at SNR 2. Threshold not changed."""
    r = sim.recovery(gaps)["hmm_marginal"]
    assert r["ok"] / r["n"] >= sim.RECOVERY_SHARE


# ------------------------------------------------------------------ NPMLE


def test_npmle_exact_data_is_ecdf():
    x = np.array([-2.0, 0.0, 1.0, 1.0, 3.0])
    fit = npmle.fit(x - 0.5, x)
    assert fit.cdf(1.0) == pytest.approx(0.8)
    assert fit.cdf(-1.0) == pytest.approx(0.2)


def test_npmle_rejects_interval_outside_truncation():
    with pytest.raises(ValueError):
        npmle.fit([0.0], [2.0], [-np.inf], [1.0])


@pytest.mark.parametrize("scenario", [
    "interval", "right_censored", "right_truncated",
    pytest.param("combined", marks=pytest.mark.xfail(
        strict=True, reason="sup error 0.057 > 0.05 at the registered seed (run 2); see simulation_diagnosis.md")),
])
def test_npmle_recovery(scenario):
    r = sim.npmle_check(scenario)
    assert r["converged"]
    assert r["sup_abs_err"] <= sim.NPMLE_MAX_SUP


def test_onehot_rejects_negative_and_out_of_range_states():
    """Review N1 residual: -1 must not wrap to state 3 inside ``_onehot``."""
    with pytest.raises(ValueError):
        hmm._onehot(np.array([-1, 0, 1, 2, 3]))
    with pytest.raises(ValueError):
        hmm._onehot(np.array([0, 4]))
    with pytest.raises(ValueError):
        hmm._onehot(np.array([0.0, 1.0]))
    r = hmm._onehot(np.array([0, 1, 1, 3]))
    np.testing.assert_array_equal(r.argmax(axis=1), [0, 1, 1, 3])
    assert r.sum() == 4


def test_npmle_squarem_matches_em():
    """SQUAREM option (proposed deviation P4) reaches the plain-EM fixed point with fewer map evaluations."""
    rng = np.random.default_rng(SEED)
    lo, hi, tl, th = sim.npmle_sample("combined", rng, n=300)
    f_em = npmle.fit(lo, hi, tl, th, max_iter=100_000, tol=1e-10)
    f_sq = npmle.fit(lo, hi, tl, th, max_iter=100_000, tol=1e-10, method="squarem")
    assert f_em.converged and f_sq.converged
    assert f_sq.n_iter < f_em.n_iter
    assert f_sq.log_lik >= f_em.log_lik - 1e-6
    assert np.all(f_sq.p >= 0) and f_sq.p.sum() == pytest.approx(1.0)
    for t in (-2.0, 0.0, 3.0, 6.0, 9.0):
        assert f_sq.cdf(t) == pytest.approx(f_em.cdf(t), abs=1e-4)
    with pytest.raises(ValueError):
        npmle.fit(lo, hi, method="newton")
