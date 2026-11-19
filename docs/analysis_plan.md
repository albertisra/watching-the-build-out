# Analysis plan (pre-registration), Phases 3 to 6

Owner: changepoint-statistician. Version 1.0, frozen 2026-11-18.
Hypotheses H1 to H5 are those of `KICKOFF.md` Section 2.3. Method rules are `KICKOFF.md` Section 6 and `CLAUDE.md`.

## 0. Status of this document

**What existed when this plan was written.** No detection output, no timeline output, no lead-time estimate and no author label existed (`data/labels/` was empty and `src/bo/timeline/` did not exist). The plan was written from the data descriptions only: `docs/data_card_registry.md`, `docs/imagery_chip_store.md`, `docs/assumptions.md`, `docs/research/*.md`, the registry summaries in `results/registry/*.csv` and the imagery quality summaries in `results/imagery/*.csv`. None of these contains a model result.

**Number tags.** Every number in this plan is one of **[P]** a pre-set decision threshold, **[D]** a design choice (registered in `docs/assumptions.md` Part 10, IDs A70 to A85), or **[F]** a fact quoted from a named file in this repository. No number in this plan is a result.

**Freeze.** The SHA-256 of this file at freeze is stored in `results/timeline/analysis_plan_v1_sha256.txt`. Later changes are allowed only through the deviations log (Section 13).

**Quantity types.** Registry dates, status and capacity are *observed*. Author labels are *observed* (human interpretation of imagery, used as reference). Change-point, HMM and detector outputs are *detected*. Footprint-derived capacity, recall-corrected totals, durations used in scenarios and scenario paths are *modelled*. Every table in `results/` carries a `quantity_type` column or states the type in its header.

## 1. Time frame and data versions

| Item | Value | Tag |
|---|---|---|
| Registry snapshot (cut-off T_x) | Gesamtdatenexport of 2026-11-16 | [F] `docs/STATUS.md` task 1.0b |
| Last imagery month D_end | 2026-10 (last complete UTC month before T_x) | [D] A70 |
| Temporal hold-out H | 2025-11 to 2026-10, the 12 months ending at D_end | [D] A70, A10 |
| Development period | all months up to 2025-10 | [D] A70 |
| Calendar month | UTC month of acquisition | [F] A27 |
| Registry opening | 2019-01-31 | [F] A18 |

Imagery series start at the first month of each chip store (`time_start`). Each series uses one platform and one Sentinel-1 relative orbit (`docs/imagery_chip_store.md`). If a later export or later imagery is used, these dates move only through a deviation entry.

## 2. Units of analysis, sampling frame and definitions

### 2.1 Sites and targets
* **Registry site.** Units of one technology grouped by the Phase 1 rule (single linkage at 300 m, A3a; location ID within 2,000 m, A3b), from `data/processed/registry/registry_sites.parquet`. In scope are batteries from 1 MW gross (A1, A1a) and ground-mounted PV from 1 MWp net (A2, A2a), all statuses including "In Planung". Pumped hydro and building PV are out of scope.
* **Target.** The unit of evaluation is the pair (site, technology). A chip with a battery and a PV park has two targets, each with its own labels and evaluation.
* **Negatives.** Hard negatives come from OSM confuser classes (A34 and the Phase 3 queue rules). Random negatives are stratified by land cover (task 3.4). A negative is a chip labelled "no BESS and no PV at the centre". Negatives the author labels as containing a site become positives and are reported as contamination.
* **Sampling frame.** For H1 to H3 the frame is the Phase 3 labelling queue (`data/processed/labels/queue_round1.parquet`) plus later rounds. For lead times only, it also includes every in-scope registry site that has a chip store. For H4 and Phase 5, the Track A national and Track B regional scans add discovered sites.

### 2.2 Size variables

| Variable | Definition | Type | Used for |
|---|---|---|---|
| MW | Site sum of unit gross power (battery) or net power (PV) | observed | strata (H1 to H3), H4 |
| MWh | Site sum of usable storage energy (battery) | observed | H4 |
| m² (Track B) | Site outline area on the latest DOP before D_end | detected | strata, A14 calibration |
| m² (Track A) | Pixels in the detected change footprint times 100 m² | detected | A14 calibration |

Size classes [D] A80 are 1 to 5, 5 to 20, 20 to 100, and 100 or more MW(p), the classes of `results/registry/pilot_v1_summary.csv` [F]. Capacity is used only for strata and H4, never as a model input.

### 2.3 Phases and events
There are four phases. **U** is undisturbed. **Cl** is cleared: ground stripped, levelled or graded, with no structures. **UC** is under construction: foundations, piles, frames, pads, containers or modules partly in place. **Co** is structures complete: the layout no longer changes.

**Label terms.** For each target the author records:
* `start_label`, the first month with visible site works (clearing, earthworks or structures);
* `uc_label`, the first month with visible structures;
* `complete_label`, the first month in which the structures look complete.

Each event gets an earliest and latest month bracket [a, b], with a = b when one image pins the month, and a confidence of high, medium or low. "Before series" or "not yet" is recorded when the event lies outside the series. If the app (task 3.3) stores another schema, the mapping is logged in Section 13 before any evaluation.

**Imagery terms (detected).** The HMM states are z_t in {0 U, 1 Cl, 2 UC, 3 Co}, and forward-backward on the whole series gives posterior marginals. Because transitions are left to right, these give CDFs:
* P(S <= t) = P(z_t >= 1 | x_1:T) for **construction start S**;
* P(S' <= t) = P(z_t >= 2 | x) for **start of structures S'**;
* P(E <= t) = P(z_t = 3 | x) for **completion E**.

The point estimate is the posterior median month; the interval is the 5 % to 95 % posterior quantiles [D] A76.
* "No start detected" if P(z_Dend >= 1) < 0.5 [D].
* "Started before the series" (left-censored) if P(z_first >= 1) >= 0.5 [D].
* BOCPD uses the same rules after segment labelling (6.2).

**The primary start is S; S' is the A13 variant** [D] A77.

**Alert month A (online).** A is the first t with filtered P(z_t >= 1 | x_1:t) >= 0.5 [D]. It is used only for the operational lead.

### 2.4 Site detected (H1)
The Phase 4 detector gives a monthly probability p_c,t for technology c.
* A target is **detected** if p_c,t >= theta_c in at least 2 months [D] A81 of H with usable imagery.
* theta_c maximises out-of-fold F1 on development folds only [D] A81.
* A **positive** is a target whose label shows c under construction or complete in at least one month of H. A **negative** shows no c in H.
* A Track A detection that the DOP contradicts counts as an error (KICKOFF 6.0).

### 2.5 Lead times
All leads are in months and are defined as registry date minus detected start (KICKOFF 6.4).
* **L_R = R − S**, where R is the site's registration date.
* **L_C = C − S**, where C is the site's commissioning date.
* Site dates are the earliest unit dates of the site [D] A78.
* Secondary: **L_V = max(R, C) − S**. This is a lower bound of the date on which the capacity becomes visible as operating, because the registry has no status history (data card Section 11 [F]).
* Secondary: the operational leads **L_R^A = R − A** and **L_C^A = C − A**.
* Planned commissioning dates are never event dates [D].

Discretisation: S is a month index s, and R or C is a day expressed as fractional months r. The true lead therefore lies in (r − s − 1, r − s], and this interval enters the likelihood. In the descriptive shares, "zero" means the same calendar month and "negative" means R falls in an earlier month than S.

### 2.6 Co-location
Of 1,199 battery sites with coordinates, 605 lie within 300 m of a ground-mounted PV site [F] (`results/registry/registry_sites_summary.csv`; bands in `results/registry/registry_colocation_breakdown.csv`).
* **Labelling.** Each technology is its own target with its own dates. The author flags co-location when the other technology is visible in the central area. This label flag is the primary stratum; the registry flag (A3c) is secondary.
* **Timeline.** One series cannot represent two construction episodes. On co-located targets, the HMM start is compared with (a) the target's own label dates and (b) the earliest labelled start in the chip. **Primary H2 and H3 use non-co-located targets only**, and co-located targets are reported separately.
* **Detection.** Co-located targets are separate pairs in H1. A PV detection on a battery-only target is a false positive only if no PV is labelled in the central area.

## 3. Circularity and leakage guard
1. **Inputs.** Inputs come only from an explicit allow-list of imagery features in `src/bo/features/`. The only registry fields used are the coordinate, which sets the chip centre, and the target technology, which selects the emission set. Neither carries timing, status or size.
2. **Deny-list.** `bo.data.registry.registry_columns()` drops `reg_*`, `site_reg_*`, capacity, capacity-derived flags and unit counts. `bo.timeline.assert_no_registry_inputs(df)` raises an error if a column:
   * is on that list;
   * is not on the allow-list; or
   * matches `reg_`, `commission`, `registr`, `status`, `mastr`, `inbetrieb`, `kwh`, `power` or `capacity`.

   The chip attribute `other_registered_sites_in_chip` is never an input. Both checks have unit tests.
3. **Freeze before join.** Registry dates are joined only in `bo.timeline.leadtime`. That code, and any run on the test fold, refuses to run without `results/timeline/model_freeze.json`, which holds the configuration hash, features, hyperparameters and date. The freeze is written once tuning ends.
4. **Blind labels.** The app hides registry fields. The strata live in `queue_round1_strata.parquet`, which the app never reads (`src/bo/data/queue.py` [F]). Positives are mixed with negatives, and the author does not see folds. Remaining limitation: the author may know public sites from the press.
5. **Stop rule.** The run stops for a leakage audit if the test fold shows a start MdAE of 0 with at least 90 % exact, or recall of 1.0 in the 1 to 5 MW class [P].

## 4. Train, validation and test design

### 4.1 Spatial blocks and folds
* **Blocks** [D] A71 are 50 km cells in EPSG:3035, aligned to the CRS origin.
* **Clusters.** All queue sites, of either technology, are linked by single linkage at 2 km [D] A71. Each cluster is atomic and goes to the block of its medoid, so co-located targets never split across folds.
* **Folds.** Blocks go into 5 folds [D] with `bo.paths.SEED`. Folds are balanced greedily on queue counts of battery positives, PV positives, negatives and open-DOP-state sites (`docs/research/dop_sources.md`). Balancing never uses dates or labels.
* **Fold 0 is the locked test fold**; folds 1 to 4 are the development folds.
* The assignment is written once, before labelling ends, to `data/processed/splits/blocks_v1.parquet`. Its hash and counts go to `results/timeline/split_v1_summary.csv`. Sites added later inherit the fold of their block.
* **Same test sites.** The Track B test set is fold 0 in open-DOP states, and the track comparison is paired on exactly these targets. Track A is also reported on all of fold 0.

### 4.2 Temporal hold-out
* Every fitted quantity uses development-fold sites and months up to 2025-10 only: detector weights, HMM parameters, BOCPD hyperparameters and thresholds.
* Test-fold sites are never used in fitting, in any month.
* Test evaluation covers all months of fold 0. Results are reported pooled (primary) and split into events before and inside H (secondary).

### 4.3 The pilot fact
30 of the 50 pilot v1 sites were commissioned in 2025 or 2026 [F] (`docs/assumptions.md`, note after A54), so much construction falls inside H. The rules:
1. **Minimum training base** [P] A85: at least 40 labelled starts and 40 labelled completions per technology in development folds, with the event month up to 2025-10.
2. If this is not met after round 1, sites commissioned 2018 to 2024 are added to the queue. This is a sampling decision only: the year is never a model input and is never shown to the author.
3. If it is still not met, timeline parameters are fitted on all months of development-fold sites (spatial hold-out only). The detector keeps the temporal hold-out, and the test fold stays untouched. Every affected table is marked as using the weaker guard.
4. The split into events before H and inside H is always reported.

### 4.4 Tuning
Tuning uses inner cross-validation over the four development folds, months up to 2025-10, and development-fold labels only. The objective is J = mean of [min(|e_S|,12) + min(|e_E|,12)], where e is the bracket error of 7.2 and a miss counts as 12 [D] A75. Ties go to the simpler setting. At most 6 features are used [D] A73, chosen by forward selection on J among allow-listed features that `docs/research/signatures.md` marks as relevant. After tuning, the model is refit on folds 1 to 4 and frozen.

Lead-time analyses need a start for every registry site with a chip. Development-fold sites therefore get out-of-fold detections, and fold 0 gets the frozen model.

## 5. Labels and label quality
* **Round 1** has at least 300 sites, stratified by technology, size and region (A12).
* **Blind relabel.** 10 % of round 1 is relabelled blind [F] (`app/config/labelling.toml`, A56). Sites are drawn with the seed, never appear among the first 10 items of a session, and are shown without the first label.
* **Agreement.** Intervals come from a site bootstrap, or a block bootstrap when at least 10 blocks are present. Output goes to `results/labels/relabel_agreement.csv`. The metrics are:
  * Cohen's kappa for presence per technology;
  * per event, the share identical, the share within 1 month and the median absolute difference;
  * linearly weighted kappa on the monthly phase.
* **Noise floor.** If agreement within 1 month on `start_label` is below 0.7 [P], H2 decisions are marked "limited by label noise" and written relative to the floor.
* **Confidence.** Primary analyses use all labels. Sensitivities drop low-confidence labels and use the bracket midpoint.
* **External check.** Projects with published dates in `docs/research/construction_durations.md` that fall in the sample are compared descriptively. These are the only references independent of the imagery the models use.
* Labels made on Sentinel panels measure agreement with a human reading of the same data. The paper says so.

## 6. Timeline models

### 6.1 Inputs
Each target has a monthly vector x_t of up to 6 allow-listed features, standardised with development-fold statistics up to 2025-10.
* Sentinel-2 features are missing in months flagged `s2_flag_bright` [D] A74 (A40), and in months with no clear observation.
* Nothing is interpolated.
* Emissions are technology-specific: registry technology for registry sites, detector class for discovered sites. Pooled emissions are a sensitivity.

### 6.2 BOCPD (Adams and MacKay 2007; `docs/research/bocpd.md`)
* **Observation model.** Independent Normal-Inverse-Gamma per feature, with Student-t predictives multiplied over observed features. mu0 = 0, kappa0 = 1, alpha0 = 2; beta0 is tuned in {0.5, 1, 2} [D] A75.
* **Hazard.** Constant 1/lambda per calendar month, with lambda in {12, 24, 48, 96} [D].
* **Missing months.** The predictive factor is 1 for every run length. The hazard step still applies, and sufficient statistics are not updated. A partly missing vector uses its observed features only.
* **Recursion.** Exact, with no pruning.
* **Change points.** They are local maxima of c_t = P(r_t+k = k | x_1:t+k) with c_t >= tau. The lag k is in {1, 2, 3} and tau in {0.3, 0.5, 0.7} [D].
* **Phase labelling.** Segments get monotone U, Cl, UC, Co labels by dynamic programming on the summed log likelihood under the frozen HMM emissions. S, S' and E are the first months of the first segment carrying the respective label.
* **Role.** BOCPD is the secondary method. Its online filter also gives an alert month.

### 6.3 Four-state HMM
* **Transitions: strict left to right** [D] A72 (A11).
  * a_00 = 1 − h_0 and a_01 = h_0.
  * a_11 = 1 − h_1 and a_12 = h_1.
  * a_22 = 1 − h_2 and a_23 = h_2.
  * a_33 = 1, so Co is absorbing.

  All other entries are structural zeros that no estimation step changes. U therefore cannot reach Co without at least one month in each of Cl and UC. Unit tests assert that the zero pattern survives fitting and that a path jumping from U to Co has zero probability.
* **Priors on exit probabilities** [D] A72. h_0 ~ Beta(1,59), h_1 ~ Beta(1,2) and h_2 ~ Beta(1,5), giving mean dwells of 60, 3 and 6 months. The UC dwell is deliberately shorter than the 6 to 20 month (BESS) and 9 to 15 month (PV) start-to-commissioning spans [F] (`docs/research/construction_durations.md`), because those spans include Cl and the time after structures. The initial distribution is Dirichlet(1,1,1,1).
* **Emissions** [D] A73. Diagonal Gaussian per state, with mu ~ N(0, 2^2) and sigma^2 ~ InvGamma(3, 2) on the standardised scale.
* **Estimation.** Primary: supervised MAP from labelled development-fold phase sequences up to 2025-10. Secondary: MAP-EM with the fixed zero pattern, adding unlabelled development sites.
* **Missing months.** The emission factor is 1. A partly missing vector uses the exact marginal of its observed features. Missingness rate by labelled phase and calendar month is written to `results/timeline/missingness_by_phase.csv` as an ignorability check.
* **Decoding.** Forward-backward marginals are primary; Viterbi is a sensitivity.
* **Variants.** Three states without Cl; a skip from U to UC; Erlang UC (3 sub-states); Student-t emissions with 4 degrees of freedom.
* **Track B fusion.** A month with a DOP flight gets an extra categorical emission: the phase read by the Track B classifier, with its confusion matrix estimated on development folds.

### 6.4 Software tests before real data
* **Recovery.** Synthetic multivariate series with known phases are generated with no gaps, with 30 % random gaps and with 3-month winter gaps. Start and completion must fall within 1 month in at least 90 % of 200 series at signal-to-noise 2 [P].
* **Run-length probabilities** sum to 1.
* **Constant series.** The run length grows by one per calendar month, including missing months.
* **Missing month.** It leaves the evidence unchanged.
* **HMM zero pattern** survives estimation.
* **NPMLE.** It recovers a known distribution under interval censoring, right censoring and right truncation.

## 7. Hypotheses, outcomes, decision rules
**General rules.** Intervals are spatial block bootstrap unless stated. Primary decisions use Bonferroni-adjusted intervals (Section 10). Strata with n < 10 get no interval [D] A84. Results that meet neither rule are reported as "inconclusive".

### 7.1 H1 Detectability
* **Population.** Fold 0 targets labelled for H. Track B uses the open-DOP subset.
* **Primary outcomes** (technology × track, 4 cells):
  * recall and precision in the largest class, which is 100 MW or more for BESS and 20 MWp or more for PV [D];
  * the recall curve against log10 MW from a logistic fit;
  * the **minimum detectable size**, where fitted recall reaches 0.8 [P] A82.
* **Secondary outcomes:**
  * recall and precision by size class;
  * by season (DJF, MAM, JJA, SON; monthly classification);
  * by region [D] A80: north (SH HH NI HB MV), east (BB BE SN ST TH), south (BY BW), west (NW HE RP SL);
  * by co-location;
  * paired Track B minus Track A recall per class;
  * false positives per 1,000 km² from the Phase 5 scan;
  * precision reweighted to scan prevalence. Sample precision depends on the queue's positive-to-negative ratio, which is stated next to every precision.
* **Supported** if recall and precision in the largest class are both at least 0.8, with adjusted lower bounds of at least 0.6 [P].
* **Evidence against** if either adjusted upper bound is below 0.8 [P].
* The minimum detectable size is compared with the physicist's prediction (R2).

### 7.2 H2 Phases and dates
* **Population.** Fold 0 non-co-located targets with a labelled event inside the series.
* **Bracket error.** e = 0 if the detected month lies in [a, b]; otherwise e is the signed distance to the nearer end. A miss is outside every tolerance and counts as +infinity for medians.
* **Primary outcomes** (HMM; technology × track × {S, E}, 8 cells): MdAE, and the share within 2 months.
* **Secondary outcomes:**
  * signed bias, and the shares within 0, 1 and 3 months;
  * error histograms (`results/timeline/date_errors_*.csv`) by technology, size, track, season, region, co-location, and event before or inside H;
  * coverage of the 90 % credible interval;
  * BOCPD on the same metrics, and the paired HMM minus BOCPD difference;
  * a naive year-on-year NDVI threshold baseline tuned on development folds;
  * S' against `uc_label`.
* **Distinguishable Cl phase** (secondary): among targets with a labelled Cl of at least 2 months, the share with P(Cl) > 0.5 in at least one labelled Cl month.
* **Supported** if MdAE <= 2 months and the share within 2 months is >= 0.6, with adjusted lower bound >= 0.5 [P].
* **Evidence against** if the adjusted upper bound of the share within 2 months is below 0.5, or the adjusted lower bound of MdAE exceeds 3 [P].
* **Cl phase.** Evidence against a distinguishable Cl if the upper bound of the Cl share is below 0.5 [P]. In that case the three-state model becomes the reported model through a deviation entry, and the four-state results are kept alongside.

### 7.3 H3 Lead time
**Population.** In-scope, non-co-located registry sites with a chip and a start that is not left-censored. Co-located sites are reported separately. Exclusions are counted: no start, start before the series, no coordinates. **Primary cohort**: S up to 2024-11 (T_x minus 24 months) [D] A79. Secondary: all starts, with truncation adjustment.

**Censoring and special cases:**
* **Right censoring.** L_C is right-censored at T_x − S for sites still "In Planung". Phase 5 discovered sites without a registry match by T_x are right-censored for both leads. A match is any unit of the same technology within 300 m, any status [D].
* **Right truncation.** Registry-sampled sites satisfy R <= T_x. The estimator conditions on this, using Turnbull's NPMLE with the Frydman correction (`docs/research/bocpd.md` row 24). The primary cohort keeps the truncation bound at 24 months or more.
* **Monthly interval censoring.** As in 2.5.
* **Detection uncertainty.** Each bootstrap replicate draws every S from its posterior.
* **Negative leads** (registration before construction) are kept, and all estimators work on the real line. 54.1 % of battery units and 8.6 % of PV units are "In Planung" [F] (data card Section 3), so the sign is a primary outcome.
* **Late registrations.** 11.3 % of battery units and 4.6 % of PV units were registered more than 31 days after commissioning [F] (`results/registry/registry_quality_flags.csv`, data card Section 5). They are kept in the primary analysis and reported as a stratum. Sensitivities exclude them and use thresholds of 14 and 62 days (A19).
* **Pre-registry sites.** Sites with C before 2019-01-31 (A18; 3.9 % of battery and 41.2 % of PV units [F]) carry backfilled registration dates. They are excluded from L_R and kept for L_C.
* **Multi-unit and staged sites** use the earliest dates (A78); the largest unit's dates are a sensitivity.

**Primary outcomes** (technology × {L_R, L_C}, 4 cells): the median; P(L<0), P(L=0) and P(L>0) on the month scale; the SD and the IQR.

**Estimators.**
* Primary: a self-consistency NPMLE for interval-censored, right-censored and right-truncated data, implemented in `src/bo/timeline/` and validated by simulation. Tail quantiles that the data do not identify are reported as bounds.
* The SD comes from a two-component normal mixture, fitted by the truncation-conditional, interval-censored likelihood.
* Secondary:
  * a normal location-scale regression on technology, size class and start year;
  * L_V;
  * the operational leads L_R^A and L_C^A;
  * the observed registry lag R − C as a reference.

**Supported** if the median is >= 1 month with an adjusted lower bound above 0 [P]. **Evidence against** if the adjusted upper bound of the median is <= 0, or the adjusted lower bound of P(L<=0) is >= 0.5 [P]. Otherwise the result is inconclusive. A negative L_C is reported as detection lag.

### 7.4 Scenario inputs
* **Construction duration** D = E − S (detected). It is interval-censored and right-censored at D_end for sites still in UC. It is estimated by NPMLE with log-normal and gamma fits on D >= 1, by technology and size class.
* **Completion probability** P(D <= k) for k = 12, 18, 24 and 36 [D]. The share still incomplete after 36 months is the stall estimate.
* **Completion to commissioning** C − E, with the same rules as L_C.
* **Outputs.** Bootstrap draws in `results/timeline/duration_draws.parquet` and a summary in `results/timeline/duration_summary.csv`. Durations are detected, and become modelled once used in scenarios (A15).

### 7.5 H4 Pipeline gap (batteries)
* **Construction stock** U(t) = sum over sites of P(z_t in {Cl, UC}) × capacity, monthly, in MW and MWh.
  * Capacity is the registry value for matched sites (observed) and the A14 footprint conversion for unmatched discovered sites (modelled).
  * The primary U(t) is recall-corrected with the Track A recall curve. The uncorrected sum is a lower bound.
* **Commitments** [F] (`docs/research/bnetza_storage_stats.md`):
  * 2025: 54.2 GW and 142.4 GWh, including answers to older requests;
  * 33.9 GW and 98.8 GWh for 2025 requests only.

  These are binding offers, not signed contracts. They can sit at several sites per project, cover medium voltage and above, and do not separate co-located storage. Our scope is 1 MW gross and above. These mismatches are stated next to every ratio.
* **Primary outcome.** rho = U(2025-12) divided by the 2025 commitments, in MW and MWh (2 cells).
* **Secondary outcomes:**
  * the same against 33.9 GW and 98.8 GWh;
  * flows: 2025 starts against 2025 commitments;
  * 2024 against the latest revision of the 2024 survey;
  * the gap G = commitments − U, with its interval;
  * registry "In Planung" capacity (observed);
  * U(t) by state.
* **Uncertainty.** Monte Carlo with 2,000 draws [D] over state posteriors, the A14 calibration, the recall curve and the block bootstrap.
* **Supported** ("much smaller") if the adjusted upper bound of rho is below 0.25 [P] A83. **Evidence against** if the adjusted lower bound is >= 0.5. Otherwise inconclusive.

### 7.6 H5 Market link (descriptive)
* **Spreads.** The three A16 metrics are computed daily from 2018-10-01 (DE-LU) on the hourly mean of quarter-hours. A separate 15-minute series runs from 2025-10-01. The **2025-10-01 switch is a structural break**: spreads computed on 96 values are mechanically larger [F] (`docs/research/market_data.md`).
* **Capacity.** Registry operational BESS capacity (observed), with the detected completion series as a comparison.
* **Association.** Monthly spread is regressed on log capacity with:
  * month-of-year;
  * solar and wind shares;
  * load;
  * dummies for the period from 2025-10-01 and for 2021-09 to 2023-06 [D] A84.

  Intervals come from a moving-block bootstrap over 12-month blocks.
* **Confounders named in the paper:**
  * solar build-out;
  * wind;
  * load;
  * gas and carbon prices, which have no free licence-clean daily series (R9);
  * the 2022 crisis;
  * the price cap change of 2022-05-10;
  * neighbouring markets and cross-border flows;
  * pumped hydro and other flexibility;
  * negative-price rules (unverified);
  * the 2018-10-01 zone split;
  * the 2025-10-01 switch;
  * the shared time trend.
* There is no test and no causal claim. The text may say capacity growth "coincides" with spread compression only if the adjusted association is negative with a 95 % interval excluding zero in the sample up to 2025-09 [P]. Otherwise it says that no association beyond the shared trend was found.
* Scenario spreads are illustrations, not forecasts.

## 8. Reporting rules
* Results are aggregates only, by technology, size, region, state and month. Per-site tables stay under `data/`, and `results/` contains no coordinates.
* Single sites appear only as public illustrations.
* All numbers come from rerunnable scripts with `bo.paths.SEED`. Each table states n, the interval method and the quantity type.

## 9. Order of work
1. Software and simulation tests.
2. Fold assignment.
3. Tuning on development folds.
4. Freeze.
5. One run on fold 0 for H1 and H2.
6. Registry join and H3.
7. Phase 5: H4 and the scenario inputs.
8. Phase 6: H5.

Steps 5 and 6 run once. A rerun after a bug fix is logged in Section 13, and both results are kept.

## 10. Intervals and multiple comparisons
* **Spatial block bootstrap.** The 50 km blocks of the evaluation set are resampled with replacement, B = 2,000 [D] A84, with percentile intervals and the seed. In H3 and H4, each replicate also draws dates and states from their posteriors. Relabel agreement uses a site bootstrap below 10 blocks.
* **Bayesian intervals** are used for single-site dates (90 % credible) and for the A14 calibration.
* **Bonferroni within each hypothesis** [D]:

  | Hypothesis | Primary cells | Interval level |
  |---|---|---|
  | H1 | 4 | 98.75 % |
  | H2 | 8 | 99.375 % |
  | H3 | 4 | 98.75 % |
  | H4 | 2 | 97.5 % |

  Secondary and stratified results carry unadjusted 95 % intervals and are labelled exploratory. H5 makes no decision.
* **Seeds.** Headline results are rerun with three further seeds (A17), and the spread across seeds is reported.

## 11. Planned sensitivity analyses

| # | Change | Assumption | Affects |
|---|---|---|---|
| S1 | Blocks 25 km, 100 km, by state | A9, A71 | H1 to H3 |
| S2 | Hold-out 6 and 24 months | A10, A70 | H1, H2 |
| S3 | Three-state HMM; U to UC skip; Erlang UC; Student-t; Viterbi | A11, A72, A73, A76 | H2, H3 |
| S4 | Drop low-confidence labels; bracket midpoint | A12 | H1, H2 |
| S5 | Start = entry to UC (S') | A13, A77 | H2, H3 |
| S6 | Clear rule: SCL blacklist; CLD 10, 30, 50 | A5, A29, A33 | H1, H2 |
| S7 | Keep `s2_flag_bright` months | A40, A74 | H2 |
| S8 | Two-month composites | A6 | H2 |
| S9 | Site grouping 100 m and 1,000 m | A3a | H1, H3 |
| S10 | Co-location distance 100 m and 1,000 m | A3c | H2, H3 |
| S11 | Size thresholds 5 and 10 MW(p) | A1, A2 | H1, H3 |
| S12 | Late-registration threshold 14 and 62 days; exclude late registrations | A19 | H3 |
| S13 | Largest unit's dates | A78 | H3 |
| S14 | Cohort cut-off 12 and 36 months | A79 | H3 |
| S15 | Pooled emissions | A73 | H2 |
| S16 | BOCPD hazard fixed at grid middle | A75 | H2 |
| S17 | Harmonic seasonality | A8 | H2 |
| S18 | Two orbits as separate series | A7, A26 | H2 |
| S19 | Footprint conversion without year | A14 | H4 |
| S20 | No recall correction | A82 | H4 |
| S21 | Three further seeds | A17 | all |
| S22 | Detection rule 1 and 3 months | A81 | H1 |

A conclusion is called robust only if its decision (supported, inconclusive or against) is unchanged in every applicable sensitivity run (KICKOFF 6.8).

## 12. Known limitations fixed in advance
* Labels and detections read the same imagery. Only DOP snapshots and the published project dates are independent.
* The registry has no status history, so L_V is a lower bound.
* The registry frame misses sites that are built but never registered. Only the Phase 5 discovery sample can estimate how many, and only within the scanned area.
* Commitments and the construction stock differ in scope and in kind: an offer versus physical activity.
* Fold 0 holds about a fifth of the labelled sites, so wide intervals are expected and are reported as they are.

## 13. Deviations log
Each entry records the date, the section, the change, the reason, and whether any result had been seen.

| Date | Section | Change | Reason | Results seen? |
|---|---|---|---|---|
| 2026-11-18 | all | Version 1.0 frozen | initial pre-registration (task 3.1) | no |
| 2026-11-18 | 0 | File saved to disk by the orchestrator from the statistician's hand-back text, unchanged, because subagents cannot create this file; no result existed at that time | tooling restriction | no |
