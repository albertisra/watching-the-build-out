"""Synthetic software checks of plan 6.4. Synthetic data only; no chip, label or registry file is read.

Design (fixed before the first run, 2026-11-19):

* 3 features, unit noise SD. State means U (0,0,0), Cl (-2,0,0), UC (-2,2,0), Co (-2,2,2): every phase
  transition shifts one feature by 2 noise SDs (signal-to-noise 2).
* 72 months, month index 0 is a January. Start s ~ U{12..42}, Cl lasts U{1..4} months, UC U{3..12};
  completion e = first Co month. All events lie inside the series.
* Gap scenarios: none; 30 % of months fully missing at random; December to February fully missing every
  year (3-month winter gaps).
* HMM: supervised MAP on 200 labelled training series of the same scenario (own seed), evaluated on 200
  further series. BOCPD: grid-centre settings (beta0 1, lambda 24, lag 2, tau 0.5; S16), segments labelled
  under the same fitted HMM emissions.
* Recovery criterion (plan 6.4 [P]): S and E both detected and both within 1 month of the truth in at
  least 90 % of the 200 series.
* NPMLE: X ~ N(3, 4^2) on the real line (negative values included), n = 2,000 per scenario; criterion set
  by this task (not in the plan): sup |F_hat - F| over integer t between the true 5 % and 95 % quantiles
  at most 0.05 (the DKW 95 % band for n = 2,000 without censoring is about 0.030).

Run: ``uv run python -m bo.timeline.simulate`` writes ``results/timeline/simulation_checks.csv``.
Quantity type: all rows are simulation diagnostics (software checks), not results about sites.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import integrate, stats

from bo.paths import RESULTS, SEED
from bo.timeline import bocpd, events, hmm, npmle

MEANS = np.array([[0.0, 0, 0], [-2, 0, 0], [-2, 2, 0], [-2, 2, 2]])
NOISE_SD = 1.0
T_LEN = 72
N_SERIES = 200
RECOVERY_SHARE = 0.9  # plan 6.4 [P]
RECOVERY_TOL = 1  # months
NPMLE_N = 2000
NPMLE_MU, NPMLE_SD = 3.0, 4.0
NPMLE_MAX_SUP = 0.05  # set by this task
NPMLE_MAX_ITER = 100_000  # self-consistency is slow under truncation plus censoring
GAP_SCENARIOS = ("none", "random30", "winter3")
BOCPD_CFG = bocpd.BocpdConfig(beta0=1.0, lam=24.0, lag=2, tau=0.5)
OUT = RESULTS / "timeline" / "simulation_checks.csv"


@dataclass
class SynthSeries:
    x: np.ndarray
    z: np.ndarray
    start: int
    complete: int


def simulate_series(rng: np.random.Generator, gaps: str = "none", t_len: int = T_LEN,
                    snr: float = 2.0) -> SynthSeries:
    s = int(rng.integers(12, 43))
    cl = int(rng.integers(1, 5))
    uc = int(rng.integers(3, 13))
    z = np.zeros(t_len, int)
    z[s:] = 1
    z[s + cl:] = 2
    e = s + cl + uc
    z[e:] = 3
    x = MEANS[z] * (snr / 2.0) + rng.normal(0, NOISE_SD, (t_len, MEANS.shape[1]))
    x[gap_mask(rng, gaps, t_len)] = np.nan
    return SynthSeries(x, z, s, e)


def gap_mask(rng: np.random.Generator, gaps: str, t_len: int) -> np.ndarray:
    if gaps == "none":
        return np.zeros(t_len, bool)
    if gaps == "random30":
        return rng.random(t_len) < 0.3
    if gaps == "winter3":
        moy = np.arange(t_len) % 12  # 0 = January
        return np.isin(moy, (11, 0, 1))
    raise ValueError(gaps)


def _ok(est: events.EventEstimate, truth: int) -> bool:
    return est.status == "detected" and abs(est.median - truth) <= RECOVERY_TOL


def recovery(gaps: str, seed: int = SEED, n: int = N_SERIES) -> dict[str, dict]:
    """Recovery shares for HMM marginals, HMM Viterbi and BOCPD on one gap scenario."""
    rng_tr = np.random.default_rng([seed, 1, GAP_SCENARIOS.index(gaps)])
    rng_te = np.random.default_rng([seed, 2, GAP_SCENARIOS.index(gaps)])
    train = [simulate_series(rng_tr, gaps) for _ in range(n)]
    p = hmm.fit_supervised([s.x for s in train], [s.z for s in train])
    test = [simulate_series(rng_te, gaps) for _ in range(n)]
    out: dict[str, dict] = {m: {"ok": 0, "ok_s": 0, "ok_e": 0, "s_err": [], "e_err": []}
                            for m in ("hmm_marginal", "hmm_viterbi", "bocpd")}

    def le(x):
        return hmm.log_emission(x, p)

    for s in test:
        post = hmm.forward_backward(s.x, p)
        ests = {
            "hmm_marginal": (events.estimate_event(post.gamma, "S"),
                             events.estimate_event(post.gamma, "E")),
        }
        vp = hmm.viterbi(s.x, p)
        ests["hmm_viterbi"] = (events.estimate_from_path(vp, "S"), events.estimate_from_path(vp, "E"))
        res = bocpd.run(s.x, BOCPD_CFG)
        bp = bocpd.label_segments(s.x, bocpd.changepoints(res, BOCPD_CFG.lag, BOCPD_CFG.tau), le)
        ests["bocpd"] = (events.estimate_from_path(bp, "S"), events.estimate_from_path(bp, "E"))
        for m, (es, ee) in ests.items():
            out[m]["ok"] += int(_ok(es, s.start) and _ok(ee, s.complete))
            out[m]["ok_s"] += int(_ok(es, s.start))
            out[m]["ok_e"] += int(_ok(ee, s.complete))
            out[m]["s_err"].append(events.bracket_error(es.median, s.start, s.start))
            out[m]["e_err"].append(events.bracket_error(ee.median, s.complete, s.complete))
    for v in out.values():
        v["n"] = n
        v["params"] = p
    return out


def clopper_pearson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    a = 1 - level
    lo = 0.0 if k == 0 else stats.beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - a / 2, k + 1, n - k)
    return float(lo), float(hi)


# ------------------------------------------------------------------ NPMLE scenarios


def npmle_sample(scenario: str, rng: np.random.Generator, n: int = NPMLE_N,
                 clip_censor: bool = True):
    """Return lo, hi, trunc_lo, trunc_hi for one censoring scenario.

    ``clip_censor=False`` reproduces run 1 (2026-11-19), whose uncensored month intervals were not clipped
    at the censoring time; that breaks coarsening at random and biased the CDF upwards by about 0.015 to
    0.019 (``results/timeline/diag_npmle_seeds_run1_unclipped.csv``).
    """
    lo, hi, tl, th = [], [], [], []
    while len(lo) < n:
        x = rng.normal(NPMLE_MU, NPMLE_SD)
        a, b = math.ceil(x) - 1.0, float(math.ceil(x))
        u, v = -np.inf, np.inf
        if scenario in ("right_truncated", "combined"):
            v = float(rng.uniform(0, 16))
            if x > v:
                continue  # never enters the sample
            b = min(b, v)
        if scenario in ("right_censored", "combined"):
            c = float(rng.uniform(-4, 12))
            if x > c:
                a, b = c, (v if scenario == "combined" else np.inf)
                if not a < b:
                    continue
            elif clip_censor:
                b = min(b, c)  # x <= c is known: the month interval is clipped at the censoring bound
        lo.append(a)
        hi.append(b)
        tl.append(u)
        th.append(v)
    return np.array(lo), np.array(hi), np.array(tl), np.array(th)


def npmle_check(scenario: str, seed: int = SEED) -> dict:
    rng = np.random.default_rng([seed, 3, ("interval", "right_censored", "right_truncated",
                                           "combined").index(scenario)])
    lo, hi, tl, th = npmle_sample(scenario, rng)
    fit = npmle.fit(lo, hi, tl, th, max_iter=NPMLE_MAX_ITER)
    q05, q95 = stats.norm.ppf([0.05, 0.95], NPMLE_MU, NPMLE_SD)
    grid = np.arange(math.ceil(q05), math.floor(q95) + 1)
    est = np.array([np.mean(fit.cdf_bounds(t)) for t in grid])
    true = stats.norm.cdf(grid, NPMLE_MU, NPMLE_SD)
    sup = float(np.max(np.abs(est - true)))
    return {"sup_abs_err": sup, "converged": fit.converged, "n_iter": fit.n_iter,
            "median_hat": fit.quantile(0.5), "pass": sup <= NPMLE_MAX_SUP and fit.converged}


# ------------------------------------------------------------------ exact identities


def runlength_sum_max_dev(seed: int = SEED) -> float:
    rng = np.random.default_rng([seed, 4])
    dev = 0.0
    for gaps in GAP_SCENARIOS:
        for _ in range(20):
            s = simulate_series(rng, gaps)
            res = bocpd.run(s.x, BOCPD_CFG)
            dev = max(dev, float(np.max(np.abs(res.run_length.sum(axis=1) - 1))))
    return dev


def constant_series_check() -> bool:
    x = np.full((40, 2), 0.7)
    x[[5, 6, 7, 20], :] = np.nan
    x[30, 0] = np.nan
    res = bocpd.run(x, BOCPD_CFG)
    return bool(np.all(np.argmax(res.run_length, axis=1) == np.arange(40)))


def missing_month_evidence(seed: int = SEED) -> dict[str, float]:
    """Max abs differences in log evidence for the missing-month identities."""
    rng = np.random.default_rng([seed, 5])
    s = simulate_series(rng, "none", t_len=30)
    p = hmm.HmmParams(np.array([0.1, 0.4, 0.2]), MEANS.copy(), np.ones_like(MEANS),
                      np.array([0.7, 0.1, 0.1, 0.1]))
    # (1) BOCPD: a fully missing month adds nothing to the evidence.
    x = s.x.copy()
    x[10] = np.nan
    r = bocpd.run(x, BOCPD_CFG)
    d_bocpd = abs(r.log_evidence[10] - r.log_evidence[9])
    # (2) HMM: evidence with month t missing equals the integral of the full evidence over x_t (1-D).
    x1 = s.x[:, :1].copy()
    p1 = hmm.HmmParams(p.h, p.mu[:, :1], p.var[:, :1], p.pi)
    t = 12
    xm = x1.copy()
    xm[t] = np.nan
    ev_missing = hmm.forward_backward(xm, p1).log_evidence

    def f(v):
        xx = x1.copy()
        xx[t, 0] = v
        return math.exp(hmm.forward_backward(xx, p1).log_evidence - ev_missing)

    integral, _ = integrate.quad(f, -12, 12, limit=200)
    d_hmm_full = abs(math.log(integral))
    # (3) HMM: a partly missing month equals the integral over the missing feature (2-D series).
    x2 = s.x[:, :2].copy()
    p2 = hmm.HmmParams(p.h, p.mu[:, :2], p.var[:, :2], p.pi)
    xp = x2.copy()
    xp[t, 1] = np.nan
    ev_part = hmm.forward_backward(xp, p2).log_evidence

    def g(v):
        xx = x2.copy()
        xx[t, 1] = v
        return math.exp(hmm.forward_backward(xx, p2).log_evidence - ev_part)

    integral2, _ = integrate.quad(g, -12, 12, limit=200)
    d_hmm_part = abs(math.log(integral2))
    # (4) Trailing missing months leave the HMM evidence unchanged.
    xt = np.vstack([x1, np.full((5, 1), np.nan)])
    d_trail = abs(hmm.forward_backward(xt, p1).log_evidence - hmm.forward_backward(x1, p1).log_evidence)
    return {"bocpd_missing_month": d_bocpd, "hmm_missing_month_quadrature": d_hmm_full,
            "hmm_partial_month_quadrature": d_hmm_part, "hmm_trailing_missing": d_trail}


def zero_pattern_checks(seed: int = SEED) -> dict[str, float]:
    rng = np.random.default_rng([seed, 6])
    lab = [simulate_series(rng, "random30") for _ in range(30)]
    unl = [simulate_series(rng, "random30").x for _ in range(30)]
    p_sup = hmm.fit_supervised([s.x for s in lab], [s.z for s in lab])
    p_em, trace = hmm.fit_map_em([(s.x, s.z) for s in lab], unl, n_iter=50)
    p_em0, _ = hmm.fit_map_em([], unl, n_iter=50)
    off = ~hmm.ALLOWED
    jump = np.array([0] * 5 + [3] * 5)
    return {
        "max_forbidden_entry_supervised": float(np.abs(p_sup.transmat[off]).max()),
        "max_forbidden_entry_em": float(np.abs(p_em.transmat[off]).max()),
        "max_forbidden_entry_em_unlabelled_only": float(np.abs(p_em0.transmat[off]).max()),
        "em_trace_min_increment": float(np.min(np.diff(trace))) if len(trace) > 1 else 0.0,
        "u_to_co_path_prob": float(math.exp(hmm.path_log_prob(jump, p_em))),
    }


def run_all(seed: int = SEED) -> pd.DataFrame:
    rows = []

    def add(check, scenario, method, value, threshold, passed, n="", ci_lo="", ci_hi="", note=""):
        rows.append({"check": check, "scenario": scenario, "method": method, "value": value,
                     "threshold": threshold, "pass": bool(passed), "n": n, "ci95_lo": ci_lo,
                     "ci95_hi": ci_hi, "note": note})

    for gaps in GAP_SCENARIOS:
        rec = recovery(gaps, seed)
        for m, r in rec.items():
            share = r["ok"] / r["n"]
            lo, hi = clopper_pearson(r["ok"], r["n"])
            primary = "primary (plan 6.3)" if m == "hmm_marginal" else "secondary/sensitivity"
            add("recovery_S_and_E_within_1_month", gaps, m, round(share, 4),
                f">= {RECOVERY_SHARE}", share >= RECOVERY_SHARE, r["n"], round(lo, 4), round(hi, 4),
                f"{primary}; Clopper-Pearson interval")
            for ev, key in (("S", "ok_s"), ("E", "ok_e")):
                sh = r[key] / r["n"]
                lo, hi = clopper_pearson(r[key], r["n"])
                add(f"recovery_{ev}_within_1_month", gaps, m, round(sh, 4), "", True, r["n"],
                    round(lo, 4), round(hi, 4), "descriptive breakdown of the joint criterion")
            for ev, key in (("S", "s_err"), ("E", "e_err")):
                e = np.array(r[key], float)
                fin = np.isfinite(e)
                add(f"median_abs_error_{ev}_months", gaps, m,
                    float(np.median(np.abs(e))) if fin.any() else math.inf, "", True, r["n"],
                    note=f"misses {int((~fin).sum())}; descriptive")
    rl_dev = runlength_sum_max_dev(seed)
    add("runlength_posterior_sums_to_1", "all", "bocpd", rl_dev, "<= 1e-9", rl_dev <= 1e-9, 60,
        note="max abs deviation over months and series")
    add("constant_series_runlength_grows_per_month", "gaps incl. partial", "bocpd",
        int(constant_series_check()), "== 1", constant_series_check(), 40)
    for k, v in missing_month_evidence(seed).items():
        tol = 1e-9 if "quadrature" not in k else 1e-6
        add(f"evidence_unchanged_{k}", "one missing month", k.split("_")[0], v, f"<= {tol}", v <= tol,
            note="abs difference in log evidence")
    for k, v in zero_pattern_checks(seed).items():
        if k == "em_trace_min_increment":
            add(k, "MAP-EM", "hmm", v, ">= -1e-6", v >= -1e-6, note="log posterior must not decrease")
        else:
            add(k, "fit on 30 labelled + 30 unlabelled", "hmm", v, "== 0", v == 0.0)
    for sc in ("interval", "right_censored", "right_truncated", "combined"):
        r = npmle_check(sc, seed)
        add("npmle_sup_abs_cdf_error", sc, "npmle", round(r["sup_abs_err"], 4), f"<= {NPMLE_MAX_SUP}",
            r["pass"], NPMLE_N, note=f"true N({NPMLE_MU}, {NPMLE_SD}^2); converged {r['converged']} "
            f"in {r['n_iter']} iterations; median_hat {r['median_hat']}; threshold set by this task")
    errs = [npmle_check("combined", seed=k)["sup_abs_err"] for k in range(5)]
    add("npmle_sup_abs_cdf_error_seeds_0_to_4", "combined", "npmle", round(max(errs), 4), "", True,
        NPMLE_N, note="descriptive, added after the registered-seed combined row failed: range "
        f"{min(errs):.4f} to {max(errs):.4f} over seeds 0 to 4; not a pass criterion")
    df = pd.DataFrame(rows)
    df["seed"] = seed
    df["quantity_type"] = "simulation diagnostic (synthetic data)"
    return df


def main() -> int:
    df = run_all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(df[["check", "scenario", "method", "value", "threshold", "pass"]].to_string(index=False))
    return 0 if df["pass"].all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
