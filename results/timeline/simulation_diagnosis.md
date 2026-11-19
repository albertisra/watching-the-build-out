# Diagnosis of the plan 6.4 simulation failures (2026-11-19)

Owner: changepoint-statistician. Every number below is **synthetic** (simulation diagnostic on generated series; no label, chip or registry file was read). Code: `src/bo/timeline/diagnose.py` (`uv run python -m bo.timeline.diagnose`), `src/bo/timeline/simulate.py`. Generator design: A88 in `docs/assumptions.md`. `docs/analysis_plan.md` is unchanged; the deviations proposed in Section 5 are proposals for the author, not log entries.

## 1. HMM recovery: information limit, plus a duration misspecification; no code defect

Sources: `diag_hmm_recovery.csv`, `diag_hmm_errors.csv`, `diag_hmm_by_cl.csv`.

**Code check.** On a short series the forward-backward marginals, the evidence and the Viterbi path match exhaustive enumeration of every state path to 1e-10 (`tests/test_timeline_models.py::test_hmm_forward_backward_and_viterbi_match_enumeration`).

**Oracle.** The Bayes-optimal decoders use the true generator: exact enumeration of every start, Cl and UC duration under the uniform priors that generated the data, with the true emissions. Joint S and E within 1 month, SNR 2, 200 series (synthetic):

| Decoder | no gaps | 30 % gaps | winter gaps |
|---|---|---|---|
| HMM, supervised MAP, 200 training series (as in `simulation_checks.csv`) | 0.790 | 0.695 | 0.635 |
| HMM, 2,000 training series | 0.805 | 0.685 | 0.640 |
| HMM, true emission parameters | 0.805 | 0.690 | 0.645 |
| Bayes-optimal posterior median | 0.885 | 0.745 | 0.710 |
| Bayes-optimal for this criterion (joint ±1 window) | 0.930 | 0.785 | 0.765 |

* No decoder reaches 0.90 with gaps at SNR 2. Even the decoder that is optimal for the criterion itself fails by 0.115 and 0.135. **With gaps the 0.90 threshold cannot be reached for this generator at SNR 2.**
* More training data and the true emissions change nothing (0.79 to 0.81), so emission estimation is not the problem. The remaining 0.08 to 0.10 gap to the Bayes median comes from the duration model. The HMM imposes geometric dwells (prior means 3 months for Cl and 6 for UC); the generator uses uniform dwells (Cl 1 to 4, UC 3 to 12 months).
* **Bias check.** At SNR 2 the HMM completion is early: mean signed error −0.27 (MC SE 0.075), −0.39 (0.12) and −0.26 (0.10) months. Start is slightly late: +0.14 (0.06), +0.09 (0.08) and +0.05 (0.08). The Bayes median shows neither bias: E −0.09 (0.06), −0.03 (0.11), 0.00 (0.08). Exact hits for the HMM are 62 % for both S and E with no gaps. A 0.27-month mean shift with 62 % exact hits is not an off-by-one; it matches the geometric UC dwell exiting too early.
* **Cl ambiguity** (no gaps, HMM; joint within 1 month): Cl of 1 month 0.905, 2 months 0.744, 3 months 0.741, 4 months 0.787. A 1-month Cl is hard only with winter gaps: 0.521 for the HMM and 0.604 for the Bayes median, because the single Cl month is often unobserved. Each transition moves one of three features by 2 SD, so a Cl phase is only told apart from UC by one feature.
* **Where 0.90 holds** (HMM, 200 training series, `diag_hmm_recovery.csv`):

  | Tolerance | SNR | no gaps | 30 % gaps | winter gaps |
  |---|---|---|---|---|
  | 1 month | 3 | 0.950 | 0.875 | 0.765 |
  | 1 month | 4 | 0.990 | 0.955 | 0.860 |
  | 2 months | 2 | 0.950 | 0.855 | 0.900 |

## 2. BOCPD: no code defect; change-point detection is weak for short, one-feature phase changes

Sources: `diag_bocpd_steps.csv`, `diag_bocpd_recovery.csv`.

**Code check.** The run-length recursion matches brute-force enumeration of every segmentation, including missing and partly missing months (`test_bocpd_evidence_matches_brute_force_with_gaps`).

**Step audit.**

| Step | Result |
|---|---|
| A: one noiseless step at month 20 | found at 20, plan and scaled priors |
| C: indexing (argmax of c_t near the true month) | exact |
| D: phase labels of the true segments | exact (U, Cl, UC, Co) |
| E: S and E with extra spurious change points | unchanged |
| B, F: noiseless 4-phase series, plan or scaled prior (with and without missing months) | only month 20 found; c_t at the true months 23 and 29 is 0.020 and 0.235 (plan), 0.002 and 0.364 (scaled) |
| G: same series, prior noise matched to the data (E[sigma^2] 0.1) | every change point found exactly for Cl of 2, 3 and 6 months; for a 1-month Cl the two changes fall in adjacent months and the local-maximum rule returns one of them (c_t 0.844, 0.395, 1.000) |

A scratch check (not in a CSV) placed the c_t peak of a missed change exactly at the true month, at 0.46 against tau 0.5. Extraction, labelling and indexing are therefore correct. The weakness is in detection.

A BOCPD segment re-learns every feature, so a new segment pays the prior-predictive cost in all three features. A run that is only 3 to 6 months old is not confident enough for a 2-SD shift in one feature to overrule it.

**Recovery** (joint within 1 month, SNR 2; columns are no gaps, 30 % gaps, winter gaps):

| Variant | no gaps | 30 % gaps | winter gaps |
|---|---|---|---|
| Plan prior, grid centre | 0.005 | 0.000 | 0.000 |
| Data-scaled prior (kappa0 0.01, beta0 = (alpha0 − 1) × within-state variance, at 0.985 to 1.005), grid centre | 0.010 | 0.000 | 0.000 |
| Best of 108 scaled-prior grid cells, picked on the test series (optimistic) | 0.115 | 0.015 | 0.020 |
| True change points fed to the labelling step | 0.960 | 0.890 | 0.905 |

Detected change points per series average 0.54, 0.15 and 0.26 against 3 true. Start alone within 1 month: 0.240, 0.065 and 0.125 (plan prior). The data-scaled prior does not help, because here the within-state variance is about 1 and the limit is the information per change, not the prior scale.

## 3. NPMLE combined censoring: one real bug found and fixed in the simulation sampler; a smaller bias remains

Sources: `diag_npmle_seeds_run1_unclipped.csv` (run 1), `diag_npmle_seeds.csv` (run 2), `simulation_checks_run1_unclipped.csv` (run 1), `simulation_checks.csv` (run 2).

**Bug.** The sampler reported an uncensored value as the month (ceil(x) − 1, ceil(x)] even when the censoring time c fell inside that month. Knowing x ≤ c, the interval must be clipped at c. Without the clip, coarsening at random fails and the CDF is biased upwards.

| Scenario | Run 1: max of mean signed CDF error | Run 2: after the clip |
|---|---|---|
| Right censoring | 0.0159 (7.4 MC SE) | 0.0046 (1.9 SE) |
| Combined censoring and truncation | 0.0194 (5.4 SE) | 0.0122 (3.3 SE) |

Truncation was already clipped, which is why it showed no comparable bias (0.0047, 3.2 SE). The estimator code did not change. The same rule now exists for real data: `bo.timeline.leadtime.lead_interval(..., upper_bound=)` clips the lead interval at the censoring or truncation bound.

**Distribution of the sup error, 20 seeds, n = 2,000** (run 2, synthetic):

| Scenario | mean | SD | median | 95th pct | max | converged |
|---|---|---|---|---|---|---|
| Interval | 0.0165 | 0.0065 | 0.0155 | 0.0270 | 0.0310 | 20/20 |
| Right censored | 0.0196 | 0.0060 | 0.0201 | 0.0283 | 0.0302 | 19/20 |
| Right truncated | 0.0178 | 0.0067 | 0.0164 | 0.0305 | 0.0306 | 20/20 |
| Combined | 0.0271 | 0.0117 | 0.0269 | 0.0483 | 0.0531 | 15/20 |
| Combined, n = 8,000 (5 seeds) | 0.0149 | 0.0026 | 0.0151 | 0.0173 | 0.0174 | 0/5 |

* The registered-seed value in `simulation_checks.csv` is 0.0572 (run 1: 0.0625), above the largest of the 20 other seeds. It is the upper tail of a wide distribution, not a typical value.
* The 0.05 tolerance I set (A88) sits near the 95th percentile of the combined case, so it fails in about 1 run in 20 (synthetic).
* The mean sup error falls by a factor 1.8 from n = 2,000 to 8,000, close to the 1/√n rate (factor 2).
* **Open.** A residual combined-case bias of about 0.01 (3.3 SE at n = 2,000; 4.1 SE at n = 8,000) remains. Self-consistency converges slowly in this case (0/5 at n = 8,000 within 100,000 iterations), so non-convergence and the support construction under truncation plus censoring (Frydman 1994, cited as SECONDARY in `docs/research/bocpd.md`) are both candidates. This must be resolved before H3.

## 4. Review N1 (labels with skipped states and undetermined months): fixed

`hmm.fit_supervised` now accepts labelling-schema v2 sequences.

* A jump of m states between adjacent months (clearing not visible, or clearing and structures in one month) counts as one exit from each state passed, with no dwell month and no emission for the skipped state (`hmm.split_labels`).
* An undetermined month (−1) is marginalised by EM with a label-constrained forward-backward. Before this fix the one-hot indexing put such a month in state 3. A run of −1 months that the strict chain cannot bridge is split and counted the same way as a jump.
* Decoding keeps the strict left-to-right zero pattern.
* Six new tests cover this. One checks that leading −1 months give the same fit as labelling them U. Complete labels give the same fit as before (recovery unchanged at 158 of 200).
* The schema docstring now says −1 months are marginalised.

## 5. Proposed deviation entries (for the author; not entered in the plan)

Entries P1, P3 and P4 change success criteria after the simulation results were seen. Results seen: **synthetic simulation diagnostics only; no label or real-data result exists.**

| # | Section | Proposed change | Reason |
|---|---|---|---|
| P1 | 6.4 | Replace "S and E within 1 month in ≥ 90 % at SNR 2" by two conditions: (a) in every gap scenario, the HMM joint within-1-month share is at least the Bayes-optimal posterior-median share of the same generator minus 0.10; (b) ≥ 90 % at SNR 3 without gaps. Currently both hold: (a) 0.790 vs 0.885, 0.695 vs 0.745, 0.635 vs 0.710; (b) 0.950. Alternative: keep 0.90 and record the failure as an information limit | The fixed threshold is above what any decoder achieves with gaps at SNR 2 (Section 1) |
| P2 | 6.3, 11 (S3) | Run the Erlang UC variant (already a planned sensitivity) through the same simulation before tuning; promote it to primary only through a separate entry if it closes the gap to the Bayes median and removes the early E bias | The geometric dwell explains the remaining HMM gap and the −0.27 month E bias |
| P3 | 6.2, 6.4, 7.2 | Exclude BOCPD from the phase-recovery criterion. Keep it for its pre-registered secondary roles (start S and online alert month) and report its S recovery descriptively. Do not adopt the data-scaled prior | Labelling from true change points reaches 0.89 to 0.96, but detection finds 0.15 to 0.54 of 3 change points per series; the scaled prior does not help (0.010) |
| P4 | 6.4 (NPMLE) | Replace the fixed sup-error tolerance by: (a) no bias beyond max(3 MC SE, 0.005) at every grid point over 20 seeds; (b) mean sup error at 4n at most 0.6 times that at n. Add SQUAREM acceleration and a log-likelihood stopping rule; check the support construction before H3. Combined currently fails (a) (0.012, 3.3 SE) and meets (b) (factor 0.55) | 0.05 was my own choice and sits at the 95th percentile of the combined case |
| P5 | 2.5, 7.3 | Every observed lead interval is clipped at its censoring or truncation bound (`lead_interval(upper_bound=)`). The lead and its bound share the same uncertain start month; how to handle that is to be settled and simulated before H3 | Section 3: an unclipped interval biases the NPMLE |
| P6 | 6.3 estimation | Supervised MAP uses the skip and −1 rules of Section 4. Before tuning, report the share of development targets whose labels skip Cl. If it is 20 % or more of starts in a technology, adopt the planned U to UC skip variant (S3) as primary for that technology. The 20 % trigger is set now, before any label exists | The strict chain must place at least one month in Cl, so S' is late by about one month on targets that skip Cl |

## 5. Addendum 2026-11-19: SQUAREM option for the NPMLE (proposed deviation P4, code only)

Sources: `diag_npmle_accel.csv`, `diag_npmle_accel_summary.csv` (synthetic, same samples as `diag_npmle_seeds.csv`; `uv run python -m bo.timeline.diagnose --only npmle_accel`). `npmle.fit(..., method="squarem")` is an option; the default stays plain self-consistency (plan 7.3). `n_iter` counts map evaluations for both methods.

| Scenario, n | Method, tol | converged | mean map evals | worst-point bias (SE) | bias/SE |
|---|---|---|---|---|---|
| Combined, 2,000 | EM, 1e-9 | 15/20 | 63,224 | 0.0122 (0.0039) | 3.11 |
| Combined, 2,000 | SQUAREM, 1e-9 | 20/20 | 4,680 | 0.0122 (0.0039) | 3.11 |
| Combined, 2,000 | SQUAREM, 1e-12 | 19/20 | 25,125 | 0.0122 (0.0039) | 3.11 |
| Combined, 8,000 | EM, 1e-9 | 0/5 | 100,000 | 0.0094 (0.0040) | 2.36 |
| Combined, 8,000 | SQUAREM, 1e-9 | 5/5 | 9,456 | 0.0094 (0.0040) | 2.36 |

* SQUAREM reaches the same fixed point (log-likelihood within 1e-4 of EM, CDF bias identical to 4 decimals) with fewer map evaluations: mean ratio EM over SQUAREM 21 (right censored), 13.5 (combined, n = 2,000), 10.6 (combined, n = 8,000, EM capped) and 4.7 (right truncated) at tol 1e-9.
* **Non-convergence does not explain the combined-case bias.** The bias at t = 6 (n = 2,000) is unchanged when every fit converges and when the tolerance is tightened to 1e-12. Four grid points still fail the P4 (a) rule at n = 2,000, and two at n = 8,000. The support construction under truncation plus censoring (Frydman 1994) and the shared-bound structure of the sampler (P5) are the remaining candidates. The issue stays open before H3.
* At tol 1e-12 a few fits stop at max_iter: the EM residual has a floating-point floor near that level.
