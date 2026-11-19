"""Diagnosis of the three plan 6.4 simulation failures (2026-11-19). Synthetic data only.

Writes to ``results/timeline/``:

* ``diag_hmm_recovery.csv``: recovery of S and E at tolerances 0 to 3 months for the fitted HMM
  (200 and 2,000 training series), the HMM with the true emission parameters, and the Bayes-optimal
  decoders under the true generating model (exact enumeration of every start, Cl and UC duration), by gap
  scenario and signal-to-noise 2, 3, 4.
* ``diag_hmm_errors.csv``: signed error distribution of S and E (bias check) for the same decoders.
* ``diag_hmm_by_cl.csv``: recovery by true Cl duration at SNR 2 (ambiguity of a short Cl phase).
* ``diag_bocpd_steps.csv``: step tests of the BOCPD pipeline on noiseless and noisy series.
* ``diag_bocpd_recovery.csv``: BOCPD recovery with the plan prior and a data-scaled prior, and with the
  true change points fed to the labelling step.
* ``diag_npmle_seeds.csv``: NPMLE sup error and signed CDF error per seed, 20 seeds per scenario, and at
  n = 8,000 for the combined scenario.
* ``diag_npmle_accel.csv`` and ``diag_npmle_accel_summary.csv`` (added 2026-11-19, review phase-3-prep
  open NPMLE item, proposed deviation P4): the same samples fitted with plain self-consistency (the plan
  default) and with the SQUAREM option at tol 1e-9 and 1e-12; bias, Monte Carlo SE and map evaluations.

Run: ``uv run python -m bo.timeline.diagnose``. Every number is synthetic (simulation diagnostic).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from bo.paths import RESULTS, SEED
from bo.timeline import bocpd, events, hmm, npmle
from bo.timeline import simulate as sim

OUT = RESULTS / "timeline"
QT = "synthetic (simulation diagnostic)"
TOLS = (0, 1, 2, 3)
SNRS = (2.0, 3.0, 4.0)
S_RANGE = range(12, 43)
CL_RANGE = range(1, 5)
UC_RANGE = range(3, 13)


# ------------------------------------------------------------------ Bayes-optimal decoders


def _combos(t_len: int = sim.T_LEN):
    c = np.array([(s, s + cl, s + cl + uc) for s in S_RANGE for cl in CL_RANGE for uc in UC_RANGE])
    assert np.all(c[:, 2] < t_len)
    return c  # columns: start S, UC entry S', completion E


COMBOS = _combos()


def bayes_posterior(x: np.ndarray, snr: float) -> np.ndarray:
    """Posterior weights over COMBOS under the true generator (uniform prior on every combination)."""
    p = hmm.HmmParams(np.array([0.5, 0.5, 0.5]), sim.MEANS * snr / 2, np.ones_like(sim.MEANS))
    le = hmm.log_emission(x, p)
    cum = np.vstack([np.zeros(4), np.cumsum(le, axis=0)])  # cum[t, k] = sum_{u<t} le[u, k]
    s, sp, e = COMBOS.T
    ll = (cum[s, 0] + (cum[sp, 1] - cum[s, 1]) + (cum[e, 2] - cum[sp, 2])
          + (cum[-1, 3] - cum[e, 3]))
    w = np.exp(ll - ll.max())
    return w / w.sum()


def _median(values: np.ndarray, w: np.ndarray) -> int:
    order = np.argsort(values, kind="stable")
    c = np.cumsum(w[order])
    return int(values[order][np.searchsorted(c, 0.5 - 1e-12)])


def bayes_median(x, snr) -> tuple[int, int]:
    w = bayes_posterior(x, snr)
    return _median(COMBOS[:, 0], w), _median(COMBOS[:, 2], w)


def bayes_window(x, snr, tol: int = 1) -> tuple[int, int]:
    """Point pair maximising P(|S - a| <= tol and |E - b| <= tol | x): optimal for the joint criterion."""
    w = bayes_posterior(x, snr)
    t_len = x.shape[0]
    joint = np.zeros((t_len, t_len))
    np.add.at(joint, (COMBOS[:, 0], COMBOS[:, 2]), w)
    k = 2 * tol + 1
    # Box sum over a (2 tol + 1)^2 window centred on (a, b).
    pad = np.pad(joint, tol)
    cs = pad.cumsum(0).cumsum(1)
    cs = np.pad(cs, ((1, 0), (1, 0)))
    box = cs[k:, k:] - cs[:-k, k:] - cs[k:, :-k] + cs[:-k, :-k]
    a, b = np.unravel_index(int(np.argmax(box)), box.shape)
    return int(a), int(b)


# ------------------------------------------------------------------ HMM diagnosis


def _hmm_points(x, p):
    g = hmm.forward_backward(x, p).gamma
    es, ee = events.estimate_event(g, "S"), events.estimate_event(g, "E")
    return (es.median if es.status == "detected" else None,
            ee.median if ee.status == "detected" else None)


def _decoders(train_small, train_large, snr):
    p200 = hmm.fit_supervised([s.x for s in train_small], [s.z for s in train_small])
    p2000 = hmm.fit_supervised([s.x for s in train_large], [s.z for s in train_large])
    p_true = hmm.HmmParams(p2000.h.copy(), sim.MEANS * snr / 2, np.ones_like(sim.MEANS), p2000.pi)
    return {
        "hmm_fit_200": lambda x: _hmm_points(x, p200),
        "hmm_fit_2000": lambda x: _hmm_points(x, p2000),
        "hmm_true_emissions": lambda x: _hmm_points(x, p_true),
        "bayes_posterior_median": lambda x: bayes_median(x, snr),
        "bayes_joint_window_1": lambda x: bayes_window(x, snr, 1),
    }


def hmm_diagnosis(seed: int = SEED):
    rec_rows, err_rows, cl_rows = [], [], []
    for snr in SNRS:
        for gi, gaps in enumerate(sim.GAP_SCENARIOS):
            tag = int(snr * 10)
            # SNR 2 reuses the streams of simulation_checks.csv, so hmm_fit_200 reproduces it.
            rtr = np.random.default_rng([seed, 1, gi] if snr == 2 else [seed, 1, gi, tag])
            rte = np.random.default_rng([seed, 2, gi] if snr == 2 else [seed, 2, gi, tag])
            rbig = np.random.default_rng([seed, 7, gi, tag])
            train = [sim.simulate_series(rtr, gaps, snr=snr) for _ in range(sim.N_SERIES)]
            big = [sim.simulate_series(rbig, gaps, snr=snr) for _ in range(2000)]
            test = [sim.simulate_series(rte, gaps, snr=snr) for _ in range(sim.N_SERIES)]
            for name, dec in _decoders(train, big, snr).items():
                es, ee, cl = [], [], []
                for s in test:
                    a, b = dec(s.x)
                    es.append(math.inf if a is None else a - s.start)
                    ee.append(math.inf if b is None else b - s.complete)
                    cl.append(int(np.sum(s.z == 1)))
                es, ee, cl = np.array(es, float), np.array(ee, float), np.array(cl)
                for tol in TOLS:
                    ok = (np.abs(es) <= tol) & (np.abs(ee) <= tol)
                    lo, hi = sim.clopper_pearson(int(ok.sum()), len(ok))
                    rec_rows.append({"snr": snr, "gaps": gaps, "decoder": name, "tolerance_months": tol,
                                     "share_S_and_E": ok.mean(), "ci95_lo": lo, "ci95_hi": hi,
                                     "share_S": float(np.mean(np.abs(es) <= tol)),
                                     "share_E": float(np.mean(np.abs(ee) <= tol)), "n": len(ok)})
                for ev, e in (("S", es), ("E", ee)):
                    fin = e[np.isfinite(e)]
                    err_rows.append({
                        "snr": snr, "gaps": gaps, "decoder": name, "event": ev, "n": len(e),
                        "misses": int((~np.isfinite(e)).sum()), "mean_signed": fin.mean(),
                        "mc_se_mean": fin.std(ddof=1) / math.sqrt(len(fin)),
                        "share_early": float(np.mean(fin < 0)), "share_exact": float(np.mean(fin == 0)),
                        "share_late": float(np.mean(fin > 0)),
                        **{f"n_err_{k}": int(np.sum(np.clip(fin, -4, 4) == k)) for k in range(-4, 5)}})
                if snr == 2:
                    for c in CL_RANGE:
                        m = cl == c
                        cl_rows.append({"snr": snr, "gaps": gaps, "decoder": name, "cl_months": c,
                                        "n": int(m.sum()),
                                        "share_S_within_1": float(np.mean(np.abs(es[m]) <= 1)),
                                        "share_E_within_1": float(np.mean(np.abs(ee[m]) <= 1)),
                                        "share_S_and_E_within_1": float(np.mean(
                                            (np.abs(es[m]) <= 1) & (np.abs(ee[m]) <= 1)))})
    return pd.DataFrame(rec_rows), pd.DataFrame(err_rows), pd.DataFrame(cl_rows)


# ------------------------------------------------------------------ BOCPD diagnosis

PLAN_PRIOR = sim.BOCPD_CFG


def scaled_prior(within_var: float) -> bocpd.BocpdConfig:
    """Data-scaled prior: vague mean (kappa0 0.01) and E[sigma^2] equal to the within-state variance."""
    alpha0 = 2.0
    return bocpd.BocpdConfig(beta0=(alpha0 - 1) * within_var, lam=24.0, lag=2, tau=0.5,
                             mu0=0.0, kappa0=0.01, alpha0=alpha0)


def _noiseless(snr=2.0, s=20, cl=3, uc=6, t_len=48):
    z = np.zeros(t_len, int)
    z[s:], z[s + cl:], z[s + cl + uc:] = 1, 2, 3
    return sim.MEANS[z] * snr / 2, z


def bocpd_steps(seed: int = SEED) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng([seed, 8])
    train = [sim.simulate_series(rng) for _ in range(200)]
    p = hmm.fit_supervised([s.x for s in train], [s.z for s in train])
    wv = float(np.mean(p.var))

    def le(x):
        return hmm.log_emission(x, p)

    def add(step, cfg_name, expected, found, note=""):
        rows.append({"step": step, "prior": cfg_name, "expected": str(expected), "found": str(found),
                     "pass": str(expected) == str(found), "note": note})

    # Step A: single step in a feature whose other features sit at the prior mean.
    x = np.zeros((40, 3))
    x[20:, 0] = -2.0
    for name, cfg in (("plan", PLAN_PRIOR), ("scaled", scaled_prior(wv))):
        r = bocpd.run(x, cfg)
        add("A one noiseless step at 20, other features at 0", name, [20],
            bocpd.changepoints(r, cfg.lag, cfg.tau))
    # Step B: four phases, noiseless; features already shifted stay away from 0.
    x, _ = _noiseless()
    truth = [20, 23, 29]
    for name, cfg in (("plan", PLAN_PRIOR), ("scaled", scaled_prior(wv))):
        r = bocpd.run(x, cfg)
        c = bocpd.changepoint_scores(r, cfg.lag)
        add("B noiseless 4 phases, change points", name, truth, bocpd.changepoints(r, cfg.lag, cfg.tau),
            "c_t at truth " + ", ".join(f"{c[t]:.3f}" for t in truth))
    # Step C: indexing of c_t: the score of the true first month must beat its neighbours (scaled prior).
    cfg = scaled_prior(wv)
    r = bocpd.run(x, cfg)
    c = bocpd.changepoint_scores(r, cfg.lag)
    add("C argmax of c_t within +-1 of 20 is 20", "scaled", 20, int(18 + np.argmax(c[18:23])))
    # Step D: labelling with the true change points on the noiseless series.
    path = bocpd.label_segments(x, truth, le)
    add("D labels of true segments (noiseless)", "n/a", [0, 1, 2, 3],
        [int(path[t]) for t in (0, 20, 23, 29)])
    # Step E: labelling with a spurious extra change point keeps S and E.
    path = bocpd.label_segments(x, [10, *truth, 40], le)
    add("E spurious change points do not move S, E", "n/a", (20, 29),
        (events.estimate_from_path(path, "S").median, events.estimate_from_path(path, "E").median))
    # Step F: missing months between the change points (scaled prior), noiseless.
    xm = x.copy()
    xm[[21, 22, 25]] = np.nan
    r = bocpd.run(xm, cfg)
    add("F noiseless with missing months 21, 22, 25", "scaled", truth,
        bocpd.changepoints(r, cfg.lag, cfg.tau))
    # Step G: noiseless series with a prior whose noise scale matches the data (E[sigma^2] = 0.1).
    # A 1-month Cl gives change points in adjacent months; the local-maximum rule returns one of them.
    for cl in (1, 2, 3, 6):
        xg, _ = _noiseless(s=20, cl=cl, uc=6, t_len=60)
        cg = scaled_prior(0.1)
        r = bocpd.run(xg, cg)
        add(f"G noiseless, Cl {cl} months, noise-matched prior", "scaled(0.1)",
            [20, 20 + cl, 26 + cl], bocpd.changepoints(r, cg.lag, cg.tau),
            "c_t at truth " + ", ".join(f"{bocpd.changepoint_scores(r, cg.lag)[t]:.3f}"
                                        for t in (20, 20 + cl, 26 + cl)))
    return pd.DataFrame(rows)


def bocpd_recovery(seed: int = SEED) -> pd.DataFrame:
    rows = []
    for gi, gaps in enumerate(sim.GAP_SCENARIOS):
        rtr = np.random.default_rng([seed, 1, gi])
        rte = np.random.default_rng([seed, 2, gi])
        train = [sim.simulate_series(rtr, gaps) for _ in range(sim.N_SERIES)]
        p = hmm.fit_supervised([s.x for s in train], [s.z for s in train])
        # Within-state variance from the labelled training series (development data in real use).
        wv = float(np.mean(p.var))
        test = [sim.simulate_series(rte, gaps) for _ in range(sim.N_SERIES)]

        def le(x, p=p):
            return hmm.log_emission(x, p)

        variants = {"plan_prior_grid_centre": PLAN_PRIOR, "scaled_prior_grid_centre": scaled_prior(wv)}
        for lag in bocpd.LAG_GRID:
            for tau in bocpd.TAU_GRID:
                for lam in bocpd.LAMBDA_GRID:
                    c = scaled_prior(wv)
                    variants[f"scaled_lag{lag}_tau{tau}_lam{lam}"] = bocpd.BocpdConfig(
                        beta0=c.beta0, lam=lam, lag=lag, tau=tau, kappa0=c.kappa0, alpha0=c.alpha0)
        res_cache = {}
        for name, cfg in [*variants.items(), ("true_changepoints_labelling", None)]:
            ok = ok_s = ok_e = 0
            ncp = []
            for i, s in enumerate(test):
                if cfg is None:
                    cps = [int(t) for t in np.flatnonzero(np.diff(s.z)) + 1]
                else:
                    key = (i, cfg.beta0, cfg.kappa0, cfg.lam)
                    if key not in res_cache:
                        res_cache[key] = bocpd.run(s.x, cfg)
                    cps = bocpd.changepoints(res_cache[key], cfg.lag, cfg.tau)
                ncp.append(len(cps))
                path = bocpd.label_segments(s.x, cps, le)
                es, ee = events.estimate_from_path(path, "S"), events.estimate_from_path(path, "E")
                a = es.status == "detected" and abs(es.median - s.start) <= 1
                b = ee.status == "detected" and abs(ee.median - s.complete) <= 1
                ok, ok_s, ok_e = ok + (a and b), ok_s + a, ok_e + b
            rows.append({"gaps": gaps, "variant": name, "n": len(test), "share_S_and_E_within_1": ok / 200,
                         "share_S_within_1": ok_s / 200, "share_E_within_1": ok_e / 200,
                         "mean_changepoints": float(np.mean(ncp)), "true_changepoints": 3,
                         "within_var": wv})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ NPMLE diagnosis


def npmle_seeds(n_seeds: int = 20, n: int = sim.NPMLE_N) -> pd.DataFrame:
    rows = []
    grid = np.arange(-3, 10)
    true = stats.norm.cdf(grid, sim.NPMLE_MU, sim.NPMLE_SD)
    scen = ("interval", "right_censored", "right_truncated", "combined")
    jobs = [(sc, k, n) for sc in scen for k in range(n_seeds)]
    jobs += [("combined", k, 4 * n) for k in range(5)]
    for sc, k, nn in jobs:
        rng = np.random.default_rng([k, 3, scen.index(sc), nn])
        lo, hi, tl, th = sim.npmle_sample(sc, rng, n=nn)
        f = npmle.fit(lo, hi, tl, th, max_iter=sim.NPMLE_MAX_ITER)
        est = np.array([np.mean(f.cdf_bounds(t)) for t in grid])
        rows.append({"scenario": sc, "seed": k, "n": nn, "converged": f.converged, "n_iter": f.n_iter,
                     "sup_abs_err": float(np.max(np.abs(est - true))),
                     **{f"err_t{t}": float(v) for t, v in zip(grid, est - true, strict=True)}})
    return pd.DataFrame(rows)


ACCEL_FITS = (("em", 1e-9), ("squarem", 1e-9), ("squarem", 1e-12))
NPMLE_SCENARIOS = ("interval", "right_censored", "right_truncated", "combined")


def _accel_job(job):
    sc, k, nn = job
    grid = np.arange(-3, 10)
    true = stats.norm.cdf(grid, sim.NPMLE_MU, sim.NPMLE_SD)
    rng = np.random.default_rng([k, 3, NPMLE_SCENARIOS.index(sc), nn])  # same samples as npmle_seeds
    lo, hi, tl, th = sim.npmle_sample(sc, rng, n=nn)
    rows = []
    for method, tol in ACCEL_FITS:
        f = npmle.fit(lo, hi, tl, th, max_iter=sim.NPMLE_MAX_ITER, tol=tol, method=method)
        est = np.array([np.mean(f.cdf_bounds(t)) for t in grid])
        rows.append({"scenario": sc, "seed": k, "n": nn, "method": method, "tol": tol,
                     "converged": f.converged, "map_evals": f.n_iter, "log_lik": f.log_lik,
                     "sup_abs_err": float(np.max(np.abs(est - true))),
                     **{f"err_t{t}": float(v) for t, v in zip(grid, est - true, strict=True)}})
    return rows


def npmle_accel(n_seeds: int = 20, n: int = sim.NPMLE_N, n_big_seeds: int = 5, workers: int = 6
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Plain EM versus SQUAREM on identical samples (per fit, and a summary per configuration).

    Bias criterion of proposed deviation P4 (a): at each grid point t in -3..9 the mean signed CDF error
    over seeds, its Monte Carlo SE (SD / sqrt(seeds)), and whether |mean| > max(3 SE, 0.005).
    """
    from concurrent.futures import ProcessPoolExecutor

    jobs = [("combined", k, 4 * n) for k in range(n_big_seeds)]  # slowest first
    jobs += [(sc, k, n) for sc in NPMLE_SCENARIOS for k in range(n_seeds)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = [r for part in ex.map(_accel_job, jobs) for r in part]
    per = pd.DataFrame(rows)
    em = per[per["method"] == "em"].set_index(["scenario", "seed", "n"])["log_lik"]
    per["log_lik_minus_em"] = per["log_lik"].to_numpy() - em.reindex(
        pd.MultiIndex.from_frame(per[["scenario", "seed", "n"]])).to_numpy()
    errc = [c for c in per.columns if c.startswith("err_t")]
    summ = []
    for (sc, nn, method, tol), g in per.groupby(["scenario", "n", "method", "tol"], sort=False):
        mean = g[errc].mean()
        se = g[errc].std(ddof=1) / math.sqrt(len(g))
        worst = mean.abs().idxmax()
        flag = mean.abs() > np.maximum(3 * se, 0.005)
        summ.append({
            "scenario": sc, "n": nn, "method": method, "tol": tol, "n_seeds": len(g),
            "n_converged": int(g["converged"].sum()),
            "map_evals_mean": float(g["map_evals"].mean()), "map_evals_median": float(g["map_evals"].median()),
            "map_evals_max": int(g["map_evals"].max()),
            "sup_abs_err_mean": float(g["sup_abs_err"].mean()),
            "bias_max_abs_grid_t": int(worst.removeprefix("err_t")),
            "bias_at_worst": float(mean[worst]), "mc_se_at_worst": float(se[worst]),
            "bias_over_se_at_worst": float(mean[worst] / se[worst]) if se[worst] > 0 else float("nan"),
            "n_grid_points_failing_p4a": int(flag.sum()),
            "max_abs_log_lik_minus_em": float(g["log_lik_minus_em"].abs().max()),
            "min_log_lik_minus_em": float(g["log_lik_minus_em"].min()),
        })
    return per, pd.DataFrame(summ)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["hmm", "bocpd_steps", "bocpd_recovery", "npmle", "npmle_accel"], default=None)
    only = ap.parse_args(argv).only
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    if only in (None, "hmm"):
        rec, err, bycl = hmm_diagnosis()
        jobs += [(rec, "diag_hmm_recovery"), (err, "diag_hmm_errors"), (bycl, "diag_hmm_by_cl")]
    if only in (None, "bocpd_steps"):
        jobs.append((bocpd_steps(), "diag_bocpd_steps"))
    if only in (None, "bocpd_recovery"):
        jobs.append((bocpd_recovery(), "diag_bocpd_recovery"))
    if only in (None, "npmle"):
        jobs.append((npmle_seeds(), "diag_npmle_seeds"))
    if only in (None, "npmle_accel"):
        per, summ = npmle_accel()
        jobs += [(per, "diag_npmle_accel"), (summ, "diag_npmle_accel_summary")]
    for df, name in jobs:
        df["quantity_type"] = QT
        df["seed_base"] = SEED
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(name, len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
