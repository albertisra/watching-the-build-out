# Review: Phase 3 deliverables and Phase 4 preparation code

Reviewer: red-team-reviewer. Date: 2026-11-19. Inputs: files only (KICKOFF.md, CLAUDE.md, code, data, docs).
Severity levels: blocker / major / minor.

## Test and lint rerun

* `make test`: **345 passed, 1 skipped, 4 xfailed** (71.8 s). The 4 strict xfails are the 3 HMM recovery
  scenarios and the NPMLE combined scenario (`tests/test_timeline_models.py:179`, `:206`).
* `make lint` (`ruff check src tests`): **All checks passed**.

## Verified without finding

* Analysis plan hash: `shasum -a 256 docs/analysis_plan.md` = `1b3782f1...227b0383f`, identical to
  `results/timeline/analysis_plan_v1_sha256.txt`.
* Fold file `data/processed/splits/blocks_v1.parquet`: file SHA-256 `a2a4d1e2...6fc54` and content hash
  `adcfb6fe...6c70` match `results/timeline/split_v1_summary.csv`. 410 unique `queue_id`; no cluster or block
  in more than one fold; no duplicate registry `site_id`; no duplicate coordinates. My own recomputation:
  minimum distance between two sites in different folds is 3,407 m (above the 2 km link and the 640 m chip),
  so no chip overlaps across folds. Per-fold counts reproduce the summary.
* Feature table `data/processed/features/features_ee_r1.parquet`: 58,220 rows, 410 sites, 2015-01 to 2026-10;
  columns are exactly `ID_COLUMNS + FEATURE_COLUMNS` (50 features) and pass `assert_no_registry_inputs`.
  No cross-site normalisation; `yoy`, trailing windows (`features/temporal.py`, `models/assemble.py:51`) use
  current and past months only. STATUS 4P.4 counts recomputed: `s2_valid_c > 0` 42,306, `s1_valid_c > 0`
  57,678, usable 57,919, `s2_qc_flag = 1` 600. All match.
* Detector: `training_rows` refuses fold 0 and months after 2025-10 (`models/detector.py:81-89`); inner
  calibration and tuning are grouped by 50 km block; `evaluate_test` is gated by the freeze hash
  (`models/pipeline.py:87`). `model_freeze.json` does not exist, as it should not yet.
* Track B slot: DOP joined as-of backward (`models/trackb.py:57`); later flights never seen.
* Earth Engine stores: one platform (`source = earthengine`), `PlatformMixError` covers it
  (`imagery/store.py:128`); one S1 relative orbit and direction enforced by filter (`imagery/eechips.py:184`);
  SCL 4/5/6 clear rule (`eechips.py:127`); missing months NaN with count 0. On 40 sampled stores the chip centre
  lies 3.4 m (median) and at most 6.9 m from the queue coordinate, UTM zones consistent. Store attributes carry no
  registry field (also `results/imagery/ee_queue_round1_leak_check.csv`, 410 of 410 clean).
* Scope: no Mecklenburg-Vorpommern DOP-derived values in `results/` or `figures/` (MV appears only as queue
  composition and in a note); no coordinate columns in any `results/**/*.csv`; no credential strings found.
* Signature headline "battery 3.9 to 9.4 MW" traces to `results/features/min_detectable_size.csv` rows
  `battery,vv,winter,d6,median` and `battery,vv,summer,d6,median` (`amin_q99_p80_r40_*`).

## Findings

### B1 (blocker). The label schema cannot produce the labels the frozen plan requires

Evidence:
* `src/bo/labelling/schema.py:14-18`: one `start_month` and one `complete_month` per item. No `uc_label`
  (first month with structures), no earliest/latest bracket [a, b], no co-location flag.
* `docs/analysis_plan.md:51-56` (plan 2.3) requires `start_label`, `uc_label`, `complete_label`, each with a
  bracket; `:92` (plan 2.6) requires each technology of a co-located chip to be "its own target with its own
  dates"; `:174` (plan 6.3) fits the four-state HMM by supervised MAP from labelled phase sequences, which needs
  Cl and UC to be separable in the labels; `:219-220` evaluates S' against `uc_label` and the Cl phase.
* `src/bo/models/targets.py:13-15` and M2 in `docs/assumptions.md`: `battery+PV` gets one shared date pair.
  The plan's own fact: 605 of 1,199 battery sites lie within 300 m of PV (`analysis_plan.md:91`).
* `targets._series` yields phase 0, 1 (Cl or UC, undistinguished) or 2, so `hmm.fit_supervised`
  (`timeline/hmm.py:215`) cannot be fed four-state sequences.

Once the author has labelled 300+ sites this cannot be repaired without relabelling. STATUS 4P.6 lists the
mapping as "open" but labelling (task 3.6) is next.
Fix: before round 1 starts, either (a) add `uc_month`, per-technology dates for `battery+PV`, and optional
earliest/latest months to the app and schema, with tests; or (b) enter a deviation in plan Section 13 that drops
`uc_label`, brackets, S', the Cl-phase test and the supervised four-state fit, and states what replaces them.
(a) is the cheaper path.

### M1 (major). Invalid Sentinel-1 values (about -50 dB) enter the features as valid observations

Evidence: in `features_ee_r1.parquet` 89 site-months at three stores (`L1-0051`, `L1-0322`, `L1-0332`;
2015-05 to 2018-03) have `s1_vv_c` down to -49.97 dB with `s1_valid_c = 1.0`. VV and VH are identical at
-49.97 in many months, which is a fill value, not backscatter. `s1_vv_c_yoy` reaches -36.8 dB. `eechips.py:187`
takes the median of the daily mosaics without a floor; `split_s1` (`:199-203`) masks only the -9999 nodata.
The step out of the -50 dB regime in 2018 will register as a change point and a false "start" in two negatives
and one PV site, and the app shows these months as data.
Fix: mask S1 pixels below a physical floor (for example -30 dB VV, -35 dB VH, value to be recorded in
`docs/assumptions.md` with a source) as missing in `split_s1`, add a unit test, rebuild the three stores and the
feature table, and report how many site-months were affected.

### M2 (major). Rounded registry coordinates are not flagged; rounded positives are in the queue

Evidence: `src/bo/data/registry.py:467` sets `coord_rounded` from `coord_decimals <= 2`, counted on the export
string, which always has 6 decimals (`54.300000`). Result: 0 sites flagged, while my count on
`registry_sites.parquet` (`coord_state == ok`) finds 106 sites with at most 2 effective decimals and 259 with at
most 3. The queue filter `queue.py:135` therefore passes `L1-0012` (PV, 54.3 / 12.9, about 11 km by 6.5 km
cell) and `L1-0138` (52.35). KICKOFF 6.1 names rounded coordinates as a registry problem to handle explicitly.
Fix: count significant decimals from the numeric value (strip trailing zeros), rebuild the flag and the data card
numbers, replace or mark the affected queue items before labelling (a fold rewrite must go through the force log).

### M3 (major). Pre-registered simulation thresholds failed; no deviation entry, BOCPD failure not in the suite

Evidence: `results/timeline/simulation_checks.csv`: HMM joint S and E within 1 month 0.79 / 0.695 / 0.635
against the [P] 0.90 (plan 6.4, `analysis_plan.md:181`); BOCPD 0.005 / 0.0 / 0.0; NPMLE combined 0.0625 against
0.05. Plan Section 9 puts these tests first; plan Section 13 has no entry. The HMM and NPMLE failures are strict
xfails, the BOCPD failure is not represented by any test (`tests/test_timeline_models.py` has no BOCPD recovery
test). The seeds 0 to 4 NPMLE row was added after the registered seed failed (labelled descriptive, correctly).
Rows with `inf` medians carry `pass = True`.
Fix: a dated deviation entry with the decision (accept as is, change the synthetic design, or change the model)
before any tuning on real labels; add a BOCPD recovery xfail; write `pass` as empty for descriptive rows.

### M4 (major). Registry dates reach the author for queue sites before or during labelling

Evidence:
* `src/bo/features/signatures.py:471-480` draws the MaStR commissioning month (red dashed) on
  `figures/signatures/*_series.png` for 20 public sites; these figures are referenced from
  `docs/research/signatures.md`. By coordinate match at least 11 of them are queue items, including
  `L1-0027` and `L1-0055` in the locked fold 0.
* `src/bo/labelling/blind.py:96-101`: the reveal panel shows registry power, status and first commissioning
  date after each save. Each reveal is logged and excluded from the relabel set, but the author's priors for the
  following items are shaped by registry timing across the session, which feeds back into start and completion
  labels that H2 is scored against.
* Plan 3.4 (`analysis_plan.md:105`) says the app hides registry fields; the remaining limitation listed there is
  press knowledge only.
Fix: write a list of registry-exposed queue ids (signature and sanity sites) and carry it as a label column like
`revealed_before`; exclude them from primary H2/H3 or add a sensitivity; disable the reveal button until the
first pass of round 1 is complete; log the change in plan Section 13.

### M5 (major). DOP shown during labelling makes the labels non-independent of the Track B input

Evidence: `app/label_app.py:248-253` shows the DOP chip next to the Sentinel views in open-DOP states; Track B
uses DOP-derived inputs (`models/trackb.py`, slot `dop_p_battery`, `dop_p_pv`) and is scored against these labels.
Plan Section 12 (`analysis_plan.md:365`) states that only DOP snapshots are independent of the imagery the models
use; once the labels are read partly from DOP that is no longer true for Track B, and the Track B minus Track A
difference (the main comparison of KICKOFF 6.0) is biased toward Track B. MV chips are shown with an
"internal use only" banner; labels informed by them then flow into published aggregates, which the author has not
decided on (STATUS decision 2026-11-18).
Fix: pre-register (deviation entry) how the comparison handles this: for example, hide DOP for a seeded random
half of items and run the paired comparison on that half, or report Track B on labels made without DOP. Use the
already recorded `chip_stores` field (DOP date type) to stratify. Get the author's decision on MV before MV items
are labelled with DOP visible.

### m1 (minor). Signature physics measured on gamma0, features computed on sigma0

`docs/research/signatures.md:63` says S1 levels are gamma0; the contrasts and minimum-size predictions come from
Sentinel Hub and Planetary Computer stores (gamma0), while Phase 4 uses Earth Engine sigma0
(`eechips.py:13-16`; EE minus SH VV about -0.6 to -1.0 dB, `results/imagery/ee_vs_sh_check.csv`). The refit
promised in STATUS 3.2b relies on the December Sentinel Hub S2 run that STATUS 3.5f cancelled.
Fix: rerun `make signatures` on `ee_r1` stores before Phase 4 and state the platform in `signatures.md`.

### m2 (minor). Blindness rests on rendering only; documentation overstates the separation

`queue_round1.parquet` holds `stratum`, `site_id` (prefix `BESS-` or `PV-` reveals the technology),
`osm_category` and `worldcover_class`; the app loads it (`labelling/queue.py:21`) and writes `stratum` into
`data/labels/labels.csv` (`app/label_app.py:126`). STATUS 3.4a and plan 3.4 say the strata are only in
`queue_round1_strata.parquet`. Nothing is displayed (verified in `blind.py`, `label_app.py`).
Fix: drop `stratum`, `site_id`, `osm_category`, `worldcover_class` from the file the app reads, or correct the
two documents.

### m3 (minor). Stale or wrong provenance attributes in the EE stores

`s2_offset_policy = "baseline >= 04.00: DN-1000 ..."` (inherited from `store.py:71`) contradicts
`s2_harmonised = "... no client-side offset"`; `s2_items_by_month` and `s1_items_by_month` are `{}`.
The EE vs SH agreement indicates no double offset was applied, but the attribute is wrong.
Fix: overwrite `s2_offset_policy` in `build_site_ee`; record scene ids per month or state that they are not kept.

### m4 (minor). No physical-range check on Sentinel-2 reflectance

`s2_b11_c` reaches 1.54 (reflectance above 1) in 14 stores, 13 of them positives, all with `s2_qc_flag = 0` and
1 to 3 clear observations. The A40 flag (chip-median B02 > 0.2, `imagery/qc.py:17`) cannot catch single bright
outliers. Fix: flag months with a centre median above 1.0 in any band (or a robust per-site outlier rule), record
it in the assumptions register.

### m5 (minor). Registry deny-list gaps

`registry_columns()` does not deny `site_extent_m` (a size proxy), `colocated_*`, `nearest_other_tech_site_m`,
`voltage_level`, `grid_operator_id`. The allow-list blocks them in practice.
Fix: add them to the deny-list for defence in depth, with a test.

### m6 (minor). `fit_standardiser` does not enforce development folds

`timeline/adapter.py:41` trusts the caller to pass development-fold rows. Fix: take the fold map and refuse fold 0.

### m7 (minor). STATUS and docs out of date or inconsistent

* `docs/STATUS.md:103` "allow-list of 51 columns"; `FEATURE_COLUMNS` has 50.
* STATUS 3.5e, 3.5-DOP and 4P.6 describe issues already fixed (app keys by `queue_id`, reads the queue DOP
  index; `data/labels/README.md` names `queue_id`).
* Two sections titled "Phase 4 preparation".
* `docs/data_sources.md:28` still says Earth Engine is "not used unless the author opts in".
* The plan uses the registry technology to select the HMM emission set (`analysis_plan.md:153`); declared in
  plan 3.1, acceptable, but no code test confirms that technology is the only registry field reaching the
  timeline.

### m8 (minor). Signature and sanity sites sit in the locked test fold

17 of the 50 pilot sites are in fold 0; at least two signature sites (`L1-0027`, `L1-0055`) informed the feature
relevance list that plan 4.4 uses for forward selection. Fix: report fold-0 metrics with and without these
items (covered by the list in M4).

## Verdict

Not signed off. Blocking: **B1** (fix before the author starts round-1 labelling). Majors M1 to M5 should be
fixed or registered as deviations before any tuning on real labels.

## Fix verification (2026-11-19)

Reviewer: red-team-reviewer, files only. STATUS claims were not used as evidence; every point below was checked
in code or data. M3 is out of scope here.

### Reruns
* `make test`: **365 passed, 1 skipped, 4 xfailed** (82.9 s). `make lint`: **All checks passed**.
* Fold file `data/processed/splits/blocks_v1.parquet` SHA-256 still `a2a4d1e2...6fc54` (equals
  `results/timeline/split_v1_summary.csv`). Queue (`queue_round1.parquet`, written 2026-11-18 23:55, before the
  registry rebuild at 2026-11-19 06:38) unchanged: 410 queue_ids, all 410 in the fold file with identical
  `site_id`; all 290 registry keys still exist in the rebuilt `registry_sites.parquet` with coordinates identical
  to the queue (maximum distance 0.0 m). The registry rebuild did not move queue items or folds.
* Analysis plan hash unchanged (`1b3782f1...227b0383f`); Section 13 still holds only the two freeze rows.

### B1 label schema: **fixed** for the purpose of starting round 1 (residuals N1, N2, m-new-1)
* `src/bo/labelling/schema.py:35-46`: per technology (`bat`, `pv`) three events `clear` (plan `start_label`),
  `struct` (`uc_label`), `complete` (`complete_label`), each with month plus optional earliest/latest bracket;
  `before_series`, `after_series`, `not_visible`; `colocated` flag; a visible co-located technology becomes an
  active technology with its own required dates (`active_techs`, `validate_events`). Positive classes cannot be
  saved with an undetermined event. `phase_sequence` gives 0 to 3 per month, -1 where undetermined.
* `src/bo/models/targets.py` reads the per-technology events (no shared date pair; M2 of the register void), returns
  `state` 0 to 3, and has no default for `onset` or `brackets`.
* Blind relabels cannot replace a first label: `labels.read_labels:172` drops `is_relabel` rows before the
  latest-row rule; `targets._two_pass` does the same; the app never sends a relabel to the DOP pass
  (`label_app.py:231`). Test `test_blind_relabel_never_replaces_first_label`.
* Pass-1 rows cannot be voided (`labels.void_label:123`). But see N2: they can be superseded.
* Residual: plan 2.3 (`analysis_plan.md:56`) asks for a confidence per event; the schema has one per item. Plan
  2.3 also requires the schema mapping in Section 13 before evaluation (not before labelling); not yet written.

### M1 Sentinel-1 fill values: **fixed** (residual N3)
* `src/bo/imagery/s1.py:44-65` `mask_s1_db` (VV [-30, +25], VH [-35, +25] dB, count 0 where VV masked), applied in
  `eechips.split_s1:204` and `sentinelhub.py:373`; tests `tests/test_eechips.py:152`, `:167`. A42 is in
  `docs/assumptions.md:218` with sources (NESZ, open-water means) and range; its sensitivity test is "not yet run".
* My own scan of all 565 S1 stores (ee_r1 410, sh_v1_s1 135, sh_v1 10, v0 10): **0** VV pixels below -30 dB,
  **0** VH below -35 dB, **0** above +25 dB remain. ee_r1: 0 pixels with NaN VV and count > 0.
* `features_ee_r1.parquet`: min `s1_vv_c` -25.58 dB, min `s1_vh_c` -32.66 dB, min `s1_vv_c_yoy` -17.20 dB
  (was -49.97 and -36.8). The three stores L1-0051, L1-0322, L1-0332 now have no S1 centre values from 2017 to 2023.

### M2 coordinate precision: **partly fixed**
* `mastr_coords.classify_coordinate_precision:197` judges the numeric value (round trip within 5e-7 deg), class by
  the coarser of lat and lon; `registry.py:475-476` sets `coord_rounded` for dp1/dp2; `registry_sites.py:235-239`
  gives a site the coarsest class of its units. `flag_coord_rounded_any` now 118 sites.
* **Reconciliation 118 vs 106.** My earlier 106 counted decimals of the *site* coordinate (coarser of lat/lon at
  most 2 decimals). I reproduce 106 on the rebuilt file. The 12 extra sites (all PV, e.g. `PV-SEE901013375713`) are
  multi-unit sites where at least one unit is dp2 but the site coordinate, a mean over units, is not round. The
  builder's 118 is right for "site position contains a coarse unit"; 106 undercounted. For those 12 the mean
  mixes a coarse unit with precise ones, so `coord_unc_m` (max over units) is an upper bound (see m-new-3).
* Excluded from inputs: `registry_columns()` lists `coord_precision_class`, `coord_unc_m`, `flag_coord_rounded_any`;
  none is in `FEATURE_COLUMNS` (50); the feature parquet has no such column; `assert_no_registry_inputs` raises
  `CircularityError` on both new names (checked).
* Not done: `L1-0012` (dp1, 6,444 m) and `L1-0138` (dp2, 652 m) are still in the queue and nothing marks them in the
  label or target path (`results/labels/queue_coarse_coordinates.csv` lists 10 items). Fix: decide replacement via
  the force log, or carry `coord_precision_class` as evaluation metadata and exclude dp1/dp2 from H2/H3 primary.

### M4 blindness: **partly fixed**
* Verified: the session sees only `queue_id`, `stratum`, `bundesland` (`blind.session_columns:85`); the view payload
  is position only; nothing displays stratum, state or any registry field; `label_app.py` does not import
  `bo.labelling.review` and `exposure` reads queue ids only at runtime. Reveal exists only in `app/review_app.py`,
  needs a committed pass 1 (and pass 2 where a DOP chip exists) and locks the item (`labels._check_unlocked`,
  test `test_reveal_locks_item`). `registry_date_exposed` is written per label and carried by `targets`.
* Gap 1: `results/labels/registry_date_exposed_queue_ids.csv` (14 ids) misses **L1-0159**. Signature figure
  `figures/signatures/P040_series.png` draws MaStR commissioning 2024-03-14 for P040; P040 lies 55 m from queue item
  L1-0159 (PV), outside `MATCH_M = 50` (`exposure.py:16`). My recomputation over all 20 drawn sites: 15 matches
  within 55 m, the other 5 are 2.3 km or more away. Fix: raise `MATCH_M` to a site-scale radius (for example 300 m,
  the site link distance A3a) and regenerate.
* Gap 2: the review app can still be used while round 1 is in progress; the original fix asked to disable reveals
  until pass 1 of round 1 is complete. Locking protects the revealed item only, not the priors for later items.
  Fix: refuse `lock_and_reveal` while unlabelled round-1 items remain, or record the number of prior reveals with
  each label.
* Gap 3: no plan Section 13 entry for the exclusion or sensitivity rule on `registry_date_exposed`.

### M5 DOP two-pass: **partly fixed**
* Verified: pass 1 renders S2/S1 only (`label_app.py:339-354`, DOP loaded only at stage 2); pass-2 rows are separate
  `dop_review` rows linked by `pass1_label_id`. On the real queue `dop_status` gives `restricted` for all 29
  Mecklenburg-Vorpommern items, `chip` for 362 and `none` for 19 others; `dop_for_site` returns nothing for MV.
  `targets.primary_labels` refuses any pass other than `pre_dop` for Track A (`TRACK_PASSES`, tested).
* Not done: the truth for the paired Track A vs Track B comparison (common pre_dop truth or per-track passes) is not
  pre-registered; no Section 13 entry. Fix: register "primary paired comparison on pre_dop labels for both tracks;
  post_dop as sensitivity, stratified by `dop_identity` and DOP date type" (or the author's alternative) before
  any Track B result.

### New findings

**N1 (important). Label sequences and the supervised HMM fit are incompatible for common cases.**
`schema.phase_sequence` maps `clear = not_visible`, or clearing and structures in the same month, to a jump 0 to 2
(checked: `[0,0,0,2,2,2,2,3,...]`). `hmm._onehot:178` rejects any step > 1, so `fit_supervised` raises for every such
target; the plan's strict left-to-right model (`analysis_plan.md:165-171`) has no rule for zero-length Cl in labels.
A leading undetermined month is accepted silently: states `[-1,-1,0,1,2,3,...]` fit with `pi = [0,0,0,1]`, because
-1 indexes state 3 (`_onehot:181`). Fix: reject negative states in `_onehot`; register in Section 13 how targets
without a labelled Cl month enter the supervised fit (drop, one-month Cl, or the U-to-UC skip variant) and test it.

**N2 (important). Pass-1 rows can be superseded by a later pass-1 row.** `labels.append_label:72-86` does not refuse
a second non-relabel `label` row for the same item and labeller, and `read_labels:175` keeps the *last* row. Checked:
pass 1, pass 2 (DOP), then a new pass-1 row is accepted and replaces the Sentinel-only answer; the DOP link is lost.
Reachable through two open app tabs. The original row stays in the file, so this is recoverable, but it breaks the
"pass 1 immutable" guarantee on which Track A's independence from DOP rests. Fix before round 1: refuse a second
non-relabel pass-1 row in `append_label`, read the first row, add a test.

**N3 (important). Fill days still enter the S1 monthly median and count.** `eechips.s1_month_image:186-187` takes
the median and the count over daily mosaics without masking fill pixels first; masking afterwards removes only
medians below the floor. Evidence of mixing: `s1_fill_value_scan.csv` L1-0051 has 78,752 VV pixels below -30 dB but
69,919 below -49 dB, so about 8,800 pixels lie between, i.e. medians of fill and real data; the same mixture can
fall just above -30 dB (L1-0332 still holds 1,821 VV pixels in [-30, -28] dB from 2015 to 2017). Fix: for the
affected stores, mark as missing every site-month where any chip pixel was below -49 dB before repair (no refetch);
for new fetches, mask per day server-side before the median. Run the A42 sensitivity.

**Minor.** (m-new-1) per-item instead of per-event confidence (plan 2.3), needs the Section 13 mapping entry.
(m-new-2) a blind relabel of an item whose DOP chip was shown in its first pass is not Sentinel-only; flag it or
exclude such items from the relabel draw. (m-new-3) for the 12 multi-unit sites with a coarse unit, compute the site
coordinate from precise units only. (m-new-4) stale text: `targets._two_pass` docstring and STATUS 4P.7 say
`read_labels` takes the latest row before dropping relabels; it no longer does. (m-new-5) `sh_v1_s1` and `sh_v1`
hold 21,755 pixels with NaN VV and count > 0 (49 and 3 stores); not used by Phase 4 features, but inconsistent.

### Verdict
B1 **fixed** (no longer blocks round-1 labelling). M1 **fixed**. M2 **partly**. M4 **partly**. M5 **partly**.
No blocking finding remains. Before round 1 starts: N2 and the L1-0159 exposure gap (cheap code fixes). Before any
tuning or evaluation: N1, N3, the M2 queue decision, and the Section 13 entries for M4, M5 and the schema mapping.
