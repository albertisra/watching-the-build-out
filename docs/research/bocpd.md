# BOCPD, HMMs, survival analysis and bootstrap for phase and lead-time estimation
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Cluster F, note 2 of 2. Equations in the first section were read directly from the Adams & MacKay and Fearnhead & Liu PDFs. Library facts come from PyPI/GitHub pages opened today. Where a page did not state something, it is marked UNVERIFIED or OPEN.

## Key facts
| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | BOCPD paper | Adams & MacKay, "Bayesian Online Changepoint Detection", arXiv:0710.3742 (19 Oct 2007) | [1] | VERIFIED |
| 2 | Run-length posterior | P(r_t \| x_{1:t}) = P(r_t, x_{1:t}) / P(x_{1:t}) (eq. 2) | [1] | VERIFIED |
| 3 | Joint recursion | P(r_t, x_{1:t}) = sum_{r_{t-1}} P(r_t \| r_{t-1}) P(x_t \| r_{t-1}, x_t^{(r)}) P(r_{t-1}, x_{1:t-1}) (eq. 3) | [1] | VERIFIED |
| 4 | Changepoint prior | P(r_t \| r_{t-1}) = H(r_{t-1}+1) if r_t = 0; 1 - H(r_{t-1}+1) if r_t = r_{t-1}+1; 0 otherwise (eq. 4) | [1] | VERIFIED |
| 5 | Hazard | H(tau) = P_gap(g = tau) / sum_{t=tau}^{inf} P_gap(g = t) (eq. 5); geometric P_gap with timescale lambda gives constant H(tau) = 1/lambda | [1] | VERIFIED |
| 6 | Algorithm 1 steps | Initialise P(r_0=0)=1 and nu_1^{(0)}=nu_prior, chi_1^{(0)}=chi_prior; observe x_t; predictive pi_t^{(r)} = P(x_t \| nu_t^{(r)}, chi_t^{(r)}); growth P(r_t = r_{t-1}+1, x_{1:t}) = P(r_{t-1}, x_{1:t-1}) pi_t^{(r)} (1 - H(r_{t-1})); changepoint P(r_t = 0, x_{1:t}) = sum_{r_{t-1}} P(r_{t-1}, x_{1:t-1}) pi_t^{(r)} H(r_{t-1}); evidence P(x_{1:t}) = sum_{r_t} P(r_t, x_{1:t}); normalise; update sufficient statistics nu^{(r+1)}_{t+1} = nu_t^{(r)} + 1, chi^{(r+1)}_{t+1} = chi_t^{(r)} + u(x_t); predict P(x_{t+1} \| x_{1:t}) = sum_{r_t} P(x_{t+1} \| x_t^{(r)}, r_t) P(r_t \| x_{1:t}) | [1] | VERIFIED |
| 7 | Cost and pruning | "The space- and time-complexity per time-step are linear in the number of data points so far observed." Discarding run-length tail mass below a threshold (example 10^-4) gives constant average cost "on the order of the expected run length E[r]", worst case still linear | [1] | VERIFIED |
| 8 | Conjugate-exponential form | Likelihood P(x \| eta) = h(x) exp(eta^T U(x) - A(eta)); conjugate prior with hyperparameters (nu, chi); nu_t^{(r)} = nu_prior + r_t, chi_t^{(r)} = chi_prior + sum_{t' in r_t} u(x_t') | [1] | VERIFIED |
| 9 | Student-t predictive for Normal-Inverse-Gamma | Predictive after r observations is Student-t; parameters follow from the standard NIG update | not fetched | UNVERIFIED (textbook conjugacy result, not read in a source today) |
| 10 | Fearnhead & Liu citation | "On-line inference for multiple changepoint problems", J. R. Stat. Soc. B 69(4):589-605 (2007), DOI 10.1111/j.1467-9868.2007.00601.x | [2], [3] | VERIFIED (text read, journal details SECONDARY) |
| 11 | Fearnhead & Liu model | State C_t = time of most recent changepoint before t (C_t in 0..t-1), a Markov chain. Segment length pmf g(.), cdf G(.). Transition (eq. 5): Pr(C_{t+1}=j \| C_t=i) = [1-G(t-i)]/[1-G(t-i-1)] if j=i; [G(t-i)-G(t-i-1)]/[1-G(t-i-1)] if j=t; 0 otherwise. Filtering: Pr(C_{t+1}=j \| y_{1:t+1}) proportional to w_{t+1}^{(j)} Pr(C_{t+1}=j \| y_{1:t}), with w_{t+1}^{(j)} = sum_q P(j,t+1,q)p(q) / sum_q P(j,t,q)p(q) for j<t, and sum_q P(t,t+1,q)p(q) for j=t (eq. 6). P(s,t,q) = integral of Pr(y_{s+1:t} \| beta, model q) pi(beta) d beta (eq. 2), requiring conjugate priors or numerical integration. Exact cost of each step proportional to t; memory for stored filtering densities quadratic; approximate version resamples (stratified optimal resampling, stratified rejection control) for constant cost. Also gives an online Viterbi MAP recursion (eq. 7) | [3] | VERIFIED |
| 12 | Equivalence of the two | In A&M, run length r_t = t - C_t; with geometric g both give the same recursion. Fearnhead & Liu allow an arbitrary segment-length pmf and a set of models per segment | [1], [3] | UNVERIFIED (our reading, not stated in the papers) |
| 13 | Robust BOCPD | Knoblauch, Jewson, Damoulas, "Doubly Robust Bayesian Inference for Non-Stationary Streaming Data with beta-Divergences", NeurIPS 2018, arXiv:1806.02261. Robust to outliers in both parameter and run-length posteriors; linear time, constant memory; beta chosen online by minimising expected predictive loss; abstract claims reduction of false discovery rate from over 90% to zero on real data | [4] | VERIFIED (abstract only) |
| 14 | GP change-point models | Saatci, Turner, Rasmussen, "Gaussian Process Change Point Models", ICML 2010, pp. 927-934: combines BOCPD with GP underlying models for within-regime smoothness; three variants and cost-reduction methods | [5] | SECONDARY |
| 15 | Missing observations in BOCPD | No primary source found in this session. Standard reasoning: if x_t is missing, skip the predictive-likelihood update for that step (pi_t = 1 for all run lengths) but still apply the hazard transition, so the run length grows with calendar time | none | UNVERIFIED |
| 16 | Hazard learning | No primary source retrieved. Adams & MacKay use fixed lambda_gap (250 for well-log, 250 for Dow Jones, 1000 for coal-mining examples) | [1] | VERIFIED (fixed values only) |
| 17 | Multivariate BOCPD | The `bayesian_changepoint_detection` repo implements online and offline `MultivariateT` (Normal-Wishart) models on [T, d] input, plus offline independent-features and full-covariance likelihoods | [6] | VERIFIED |
| 18 | PELT | Killick, Fearnhead, Eckley (2012) J. Am. Stat. Assoc., arXiv:1101.1438: exact penalised-cost minimisation, cost "linear in the number of observations" under mild conditions (abstract) | [7] | VERIFIED (abstract) |
| 19 | ruptures paper | Truong, Oudre, Vayatis, "Selective review of offline change point detection methods", Signal Processing 167:107299 (2020), DOI 10.1016/j.sigpro.2019.107299, arXiv:1801.00718; organised by cost function, search method, constraint on number of changes | [8] | VERIFIED |
| 20 | ruptures package | PyPI latest 1.1.10 (10 Sep 2025; 1.1.11rc1 pre-release listed), BSD-2-Clause, Python >=3.9 and <3.14 | [9] | VERIFIED |
| 21 | lifelines | 0.30.3 (5 Mar 2026), MIT, Python >=3.11 | [10] | VERIFIED |
| 22 | scikit-survival | 0.28.0 (5 Jul 2026), GPL-3.0-or-later, Python >=3.11 | [11] | VERIFIED |
| 23 | lifelines truncation and censoring | `entry` argument for left truncation (documented for fit, fit_interval_censoring, fit_left_censoring: "useful for left-truncated (not left-censored) observations"); `KaplanMeierFitter.fit_interval_censoring` is the non-parametric MLE "also called the Turnbull Estimator", closed intervals only, "new and experimental, and many features are missing" | [12], [13] | VERIFIED |
| 24 | Turnbull | Turnbull (1976) JRSS B 38(3):290-295, DOI 10.1111/j.2517-6161.1976.tb01597.x; for combined truncation and censoring the method needs modification (Frydman 1994, per a search snippet) | [14] | SECONDARY |
| 25 | Non-negative durations in lifelines | The pages read do not state any requirement or lack of one | [12], [15] | OPEN |
| 26 | Block bootstrap | Kuensch (1989) Ann. Stat. 17(3):1217-1241, DOI 10.1214/aos/1176347265 (moving blocks); Politis & Romano (1994) JASA 89(428):1303-1313, DOI 10.1080/01621459.1994.10476870 (stationary bootstrap, geometric block lengths) | [16] | SECONDARY |
| 27 | Spatial block bootstrap | Lahiri (2003) book "Resampling Methods for Dependent Data" (Springer); Lahiri & Zhu (2006) Ann. Stat. 34(4):1774-1813 on irregularly spaced spatial data, noting naive grid extension fails under nonuniform designs and that Politis, Paparoditis and Romano formulated a spatial block version | [17] | SECONDARY |
| 28 | hmmlearn | 0.3.3 (31 Oct 2024), BSD, README: "limited-maintenance mode". `GaussianHMM(covariance_type="full")` gives multivariate Gaussian emissions. Tutorial shows left-right transition matrices ("need not to be ergodic") and fixing parameters by removing letters from `params`; it does not state that zero entries persist under EM (they do under multiplicative Baum-Welch updates, standard, UNVERIFIED here). No NaN support found; 0.2.6 changelog mentions missing observations only for multinomial | [18], [19], [20] | VERIFIED / OPEN as stated |
| 29 | pomegranate | 1.1.2 (7 Feb 2025), MIT, PyTorch-based. Docs mention "learning with missing values" generally; HMM-specific missing-data, constrained-transition and maintenance details not found on the page read | [21] | VERIFIED (version, licence) / OPEN (details) |
| 30 | dynamax | 1.0.3 (13 Oct 2026), MIT, JAX, Python >=3.10; HMMs with Categorical, Gaussian, Poisson emissions (from search snippet), EM and SGD. README does not mention constrained transitions or NaN handling; constraint via initial parameters and `props` is a search-snippet suggestion only | [22], [23], [24] | VERIFIED (version, licence) / OPEN (constraints, missing data) |
| 31 | ssm (lindermanlab) | MIT; README says "partial observations and missing data" supported; team "working full time on a JAX refactor"; no PyPI release listed; maintenance unconfirmed; the JAX refactor is dynamax | [25] | VERIFIED |
| 32 | HSMM reference | Yu (2010) "Hidden semi-Markov models", Artif. Intell. 174:215-243: explicit-duration (variable-duration) HMM as one conventional HSMM variant. Library support (e.g. pyhsmm) not checked | [26] | SECONDARY |
| 33 | `bayesian_changepoint_detection` | PyPI `bayesian-changepoint` (import `bayesian_changepoint_detection`), MIT, 782 stars, 110 commits, no GitHub releases, version 1.2.2 referenced, pytest suite (tests tagged `math`/`behavior`, CI Python 3.9-3.13), PyTorch tensors; online (Adams & MacKay) and offline (Fearnhead 2006) | [6] | VERIFIED |
| 34 | Other BOCD packages | y-bar/bocd (MIT per third-party index, health score 28/100), Fast-BOCPD (MIT per its docs), pybocd, BOCPD (phamquiluan), ocpdet, JackKelly/bayesianchangepoint (port of Adams' MATLAB code): licences/quality not checked directly | [27] | SECONDARY / UNVERIFIED |

## Details

### BOCPD in our notation
Let x_t be the (possibly vector-valued) site features in month t, r_t the run length. Joint recursion and hazard as in rows 3-5. With a constant hazard H = 1/lambda the prior on segment length is geometric with mean lambda. Our four phases have unequal expected lengths and a fixed order, which a single constant hazard does not encode.

The Adams & MacKay paper models one regime in each run with i.i.d. data given parameters. It does not model a sequence of distinct phases. To get phases, one can (a) run BOCPD for change-points only and label segments afterwards (clustering segment means), or (b) use Fearnhead & Liu's multi-model formulation (a set of models q per segment, prior p(q)), or (c) use an HMM with left-to-right transitions (below). Option (b) is in the literature; its use for ordered phases is our inference.

Pruning: drop run lengths with posterior mass below a threshold (A&M example 10^-4) or keep a maximum run length. For ~60-120 monthly points per site, cost is trivial; exact O(T^2) per series is acceptable.

### Robustness and non-Gaussianity
Satellite features have outliers (residual cloud, speckle, snow). Standard BOCPD with Gaussian predictives treats an outlier as strong evidence of a change. Knoblauch et al. 2018 target exactly this; their code licence was not checked (OPEN). A simpler alternative is a Student-t observation model, or outlier gating before the filter.

### Missing months
Row 15 gives the conventional treatment and is UNVERIFIED. Two choices need testing on synthetic data: whether the hazard acts per calendar month (recommended) or per observation. For HMMs the same device applies: for conditionally independent emissions, a missing observation contributes likelihood 1 for every state, and the forward-backward algorithm otherwise proceeds unchanged. Speekenbrink and Visser (arXiv 2109.02770) is a search hit on ignorable and non-ignorable missingness in HMMs; it was not opened. Missingness from snow is correlated with season, which could correlate with phase only weakly, but should be checked (if the missing pattern is informative it is not ignorable).

### Offline alternatives
* PELT (exact, linear cost under conditions) and ruptures (many costs, search methods; multivariate input). ruptures returns segmentations, not probabilities, and does not natively handle NaN (not verified; fill or drop missing months and keep a calendar index).
* Use PELT/ruptures as a cross-check on BOCPD/HMM change dates, not as the primary method.

### HMM design
* Left-to-right (Bakis) constraint: set the transition matrix so that state i can go only to i or i+1 (strict left-to-right), or i to i+1 and i+2 if one phase can be skipped. For "cannot jump straight from undisturbed to complete" use strict left-to-right with allowed skip only where physically plausible (e.g. cleared to complete is rare, so also forbid).
* Geometric state durations are implied by self-transitions. If phase durations are strongly non-geometric (construction takes a minimum number of months), an explicit-duration HSMM (Yu 2010) is the formal remedy; an alternative is to expand each phase into a chain of several sub-states (Erlang-type duration) inside an ordinary HMM, which works with hmmlearn or a custom forward algorithm (our suggestion, UNVERIFIED).
* Absorbing final state: structures-complete should be absorbing (self-transition 1). Right-censoring of the sequence is then natural.

### Survival analysis for lead time
Define lead time L = registry date minus detected date (e.g. detected construction start versus MaStR commissioning/registration date).
* Right-censoring arises when a registry event has not occurred by the data cut-off (events still pending).
* Left-truncation arises when sites are only observed if already past some entry date (e.g. registry in the sample only after a registration date).
* Interval censoring arises because detection is monthly (the true date lies in an interval of about one month) and because detected phase dates have posterior uncertainty.
* lifelines supports right/left/interval censoring and an `entry` argument (row 23). The pages read do not confirm the combination of interval censoring plus left truncation for parametric AFT models (OPEN).
* Negative lead times: Kaplan-Meier/Turnbull and parametric AFT models assume positive support. Options (not from a source): (i) shift: analyse L + c with c large enough to make all values positive, and report back-shifted quantities (a Weibull on the shifted variable is then a three-parameter model with location c); (ii) treat the sign as a separate binary outcome (registry first versus detection first) and model magnitudes on each side; (iii) use a distribution with real-line support (e.g. normal or logistic on L) fitted by interval-censored likelihood; scikit-survival and lifelines do not provide this out of the box as far as the pages read show. Choose (iii) or (i) and check sensitivity.
* Licences: lifelines MIT; scikit-survival GPL-3.0-or-later, which is incompatible with permissive redistribution in a non-GPL public repository if we import or ship it; using it as an installed dependency is generally allowed but confirm.

### Bootstrap
Sites are the unit; months within a site are autocorrelated. Resample sites (whole series) for lead-time statistics; use moving-block or stationary bootstrap (Kuensch 1989; Politis & Romano 1994) only when resampling within a series. For clustering in space (neighbouring parks, shared weather), use spatial blocks (e.g. grid cells larger than the dependence range) (Lahiri 2003; Lahiri & Zhu 2006, row 27). The choice of block size is a tuning decision not resolved by these sources.

### Implementation choice
`bayesian-changepoint` is MIT with tests and multivariate Student-t online models, but is a single-maintainer project without GitHub releases, has no documented handling of missing observations, and takes PyTorch tensors (heavy dependency for ~100-step series). Recommendation: implement our own BOCPD (about 60 lines in NumPy for the recursion in rows 3-6 with an NIG or Normal-Wishart predictive) and validate it against `bayesian-changepoint` as a reference in unit tests. This meets the specification's requirement for tested change-point code, controls the missing-data rule and hazard, and avoids a dependency. Unit tests worth writing: (1) joint probabilities sum to one after normalisation; (2) a constant series gives run length growing by 1 per step; (3) a step change of known size is detected within k steps; (4) a missing-value step leaves the likelihood unchanged and still applies the hazard; (5) agreement with the reference library on a fixed random seed; (6) with constant hazard, the prior mean segment length equals lambda (simulation).

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict (CONFIRMED / CORRECTED / OPEN) | Source |
|----|---------------------|---------|-----------------------------------------|--------|
| V13 | A four-state left-to-right HMM "constrained so it cannot jump straight from undisturbed to complete", and BOCPD, are well supported by literature and libraries for monthly series with missing months (claim text paraphrased from the brief; KICKOFF.md was not read in this session) | Literature: BOCPD (Adams & MacKay 2007; Fearnhead & Liu 2007) and left-to-right HMMs/HSMMs (Yu 2010) are established. Libraries: hmmlearn supports full-covariance Gaussian emissions and left-right transitions via initial matrices, but is in limited-maintenance mode and no NaN support was found for Gaussian emissions; pomegranate 1.1.2 mentions learning with missing values in general; dynamax 1.0.3 (MIT, JAX, actively released) and ssm list HMMs, with ssm advertising missing-data support; constrained-transition support in dynamax is not documented on the pages read. No BOCPD library documents missing observations. Caveats: (a) BOCPD finds change-points, not ordered labelled phases; (b) HMM self-transitions imply geometric durations; (c) missing-data treatment (skip the emission term) is simple but must be implemented and tested by us; (d) no published accuracy for either method on this task; (e) snow-driven missingness may be informative | OPEN (well supported in theory, library support for gaps and constraints incomplete; plan on a custom forward algorithm or custom BOCPD) | [1], [3], [18]-[25] |

## What this means for our method
1. Write our own BOCPD and our own HMM forward-backward/Viterbi with a missing-observation mask and a fixed left-to-right transition mask; use hmmlearn/dynamax only as cross-checks. This is cheap for series of this length and removes the dependency on undocumented library behaviour.
2. Use month-indexed series with NaN for gaps; treat a missing month as a step with no likelihood term.
3. Report change dates as posterior distributions or intervals, and feed those intervals (not point dates) to the interval-censored survival step.
4. For lead time use right-censoring, `entry` for truncation, and an explicit plan for negative values (shift or real-line support). Confirm AFT handling of interval censoring plus truncation with a simulation before relying on it.
5. Bootstrap over sites (or spatial blocks), not over months.
6. Licence check before adding scikit-survival (GPL-3.0-or-later).

## Open questions
* Student-t predictive parameters for NIG (derive and test, or cite Murphy's conjugate note; not fetched).
* Hazard-rate learning in BOCPD: no source retrieved this session.
* Multivariate/robust BOCPD code licences (Knoblauch et al. repository not located).
* Whether lifelines parametric AFT models accept zero or negative durations and combine interval censoring with entry.
* pomegranate and dynamax NaN and transition-constraint details (read API docs or source).
* pyhsmm or other HSMM library availability and licence.
* Whether `ruptures` accepts NaN input.
* Content of KICKOFF.md for V13 wording.

## Sources
1. Adams & MacKay, arXiv:0710.3742, PDF read (pp. 1-5): https://arxiv.org/pdf/0710.3742 (abstract https://arxiv.org/abs/0710.3742). Retrieved 2026-11-12.
2. Fearnhead & Liu citation: https://ideas.repec.org/a/bla/jorssb/v69y2007i4p589-605.html (search result). Retrieved 2026-11-12.
3. Fearnhead & Liu preprint text, PDF read (pp. 3-9): https://eprints.lancs.ac.uk/id/eprint/745/1/online_chpt4.pdf. Retrieved 2026-11-12.
4. Knoblauch, Jewson, Damoulas, https://arxiv.org/abs/1806.02261. Retrieved 2026-11-12.
5. Saatci, Turner, Rasmussen ICML 2010, https://icml.cc/imls/conferences/2010/papers/170.pdf (search result, not opened). Retrieved 2026-11-12.
6. https://github.com/hildensia/bayesian_changepoint_detection. Retrieved 2026-11-12.
7. Killick, Fearnhead, Eckley, https://arxiv.org/abs/1101.1438. Retrieved 2026-11-12.
8. Truong, Oudre, Vayatis, https://arxiv.org/abs/1801.00718. Retrieved 2026-11-12.
9. https://pypi.org/project/ruptures/. Retrieved 2026-11-12.
10. https://pypi.org/project/lifelines/. Retrieved 2026-11-12.
11. https://pypi.org/project/scikit-survival/. Retrieved 2026-11-12.
12. https://lifelines.readthedocs.io/en/latest/Survival%20analysis%20with%20lifelines.html. Retrieved 2026-11-12.
13. https://lifelines.readthedocs.io/en/latest/fitters/univariate/KaplanMeierFitter.html. Retrieved 2026-11-12.
14. Turnbull 1976, search result, https://scilit.com/publications/5669692a888df09f7963f6eacda5e49e. Retrieved 2026-11-12.
15. https://lifelines.readthedocs.io/en/latest/fitters/regression/WeibullAFTFitter.html. Retrieved 2026-11-12.
16. Kuensch / Politis & Romano, https://projecteuclid.org/journals/annals-of-statistics/volume-17/issue-3/The-Jackknife-and-the-Bootstrap-for-General-Stationary-Observations/10.1214/aos/1176347265.full (search result). Retrieved 2026-11-12.
17. Lahiri & Zhu 2006 and Lahiri 2003, search results: https://projecteuclid.org/euclid.aos/1162567633, https://www.doi.org/10.1007/978-1-4757-3803-2_1. Retrieved 2026-11-12.
18. https://pypi.org/project/hmmlearn/. Retrieved 2026-11-12.
19. https://hmmlearn.readthedocs.io/en/latest/tutorial.html and https://github.com/hmmlearn/hmmlearn. Retrieved 2026-11-12.
20. hmmlearn changelog/Stack Overflow via search: https://hmmlearn.readthedocs.io/en/0.3.0/changelog.html. Retrieved 2026-11-12.
21. https://pypi.org/project/pomegranate/ and https://pomegranate.readthedocs.io/en/latest/. Retrieved 2026-11-12.
22. https://pypi.org/project/dynamax/. Retrieved 2026-11-12.
23. https://github.com/probml/dynamax. Retrieved 2026-11-12.
24. https://probml.github.io/dynamax/ (search snippet only). Retrieved 2026-11-12.
25. https://github.com/lindermanlab/ssm. Retrieved 2026-11-12.
26. Yu 2010, https://www.cs.ubc.ca/~murphyk/Teaching/CS540-Spring10/projects/Yu-hsmm09.pdf (search result, not opened). Retrieved 2026-11-12.
27. Search result listing of BOCD packages: https://pypi.org/project/bocd/0.1.0/, https://fast-bocpd.readthedocs.io/, https://www.github.com/JackKelly/bayesianchangepoint. Retrieved 2026-11-12.
