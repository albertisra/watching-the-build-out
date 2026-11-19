# Red-team review, round 2: Phase 1 (registry ground truth) and Phase 2 (imagery pipelines, interim)

Reviewer: red-team-reviewer. Date: 2026-11-18. Basis: `KICKOFF.md` Sections 3, 6 and 7, `CLAUDE.md`, the first review
`docs/reviews/phase-1-2.md` (left unchanged) and the files in the repository. Builder status rows were not taken as evidence;
every status below rests on files I read or numbers I recomputed with `uv run python` against `data/processed/`, `data/chips/`
and `results/` (scratch scripts not stored). Phase 2 stays interim: Sentinel-2 chips for 140 of 150 sites are scheduled for
December and the author has not yet reviewed the sanity panels. Those two items are not judged.

## 0. Test suite and lint (rerun by reviewer)

- `uv run pytest`: **141 passed, 1 skipped** (skip: `tests/test_sentinelhub_integration.py:11`, network test gated by `BO_INTEGRATION=1`). One Pandas4Warning from `src/bo/data/registry_sites.py:264` (string fill on a float column).
- `uv run ruff check src tests`: **All checks passed.**
- New tests: per-satellite orbit pairs (`tests/test_sentinelhub.py:55-78`, Python and evalscript), QC flags, per-request quota rows, refetch windows, native-zone tile preference (`tests/test_imagery_review.py`). No pair covers S1C absolute orbits 8,000 to 8,264, which is where the new defect B3 sits.

## 1. Acceptance criteria (KICKOFF Section 7), current state

| Phase | Criterion | Judgement | Evidence |
|---|---|---|---|
| 1 | Site tables with data card | met | unchanged from round 1 |
| 1 | Monthly operational capacity series | met | recomputed battery stock at 2025-10-15: 2.4280 GW (all registrations), 2.2965 GW (registered by the date) |
| 1 | Totals compared, differences explained | met for batteries; PV only by definition (N2) | `results/registry/comparison_official_statistics.csv`, 20 rows, each with variant, comparability verdict and explanation |
| 2 | Sentinel chips and composites, 50 pilot plus 100 negatives | partly met (interim, S2 scheduled) | S1 for 145 of 150 chips, now including S1B and S1D; S2 for 10 |
| 2 | Clear-observation counts | met | unchanged |
| 2 | Scan benchmark with runtime and quota | met, caveat m8 open | unchanged |
| 2 | DOP source table complete; DOP chips for the same pilot sites with flight dates | chips **met**; table **partly met** (N1) | `data/processed/pilot/dop_chips_v1.parquet`: 50 of 50 sites; `docs/research/dop_sources.md:201-213` unchanged since before round 1 |
| 2 | Sanity panels reviewed | scheduled (author) | not judged |

## 2. Status of round-1 findings

### Blocking

**B1. Sentinel-1 orbit formula dropped S1B and S1D. Status: resolved as framed in round 1; the fix introduced B3.**
- `src/bo/imagery/s1orbit.py:12-23` and the evalscript `src/bo/imagery/sentinelhub.py:282-291` now use S1A 73, S1B 27, S1C 172 (99 from absolute orbit 8,000), S1D 42.
- I checked the formula against every S1 item in the Planetary Computer stores `data/chips/v0`, `test` and `demo150` (2,051 S1A, 594 S1B, 569 S1C, 132 S1D items). All S1A, S1B and S1D items map to the stored relative orbit. 3 S1C items do not (B3).
- Sentinel Hub stores (`sh_v1`, `sh_v1_s1`, 145 chips) now list 48,991 S1A, 22,014 S1B, 6,604 S1C and 2,383 S1D items (round 1: zero S1B and zero S1D). Mean `s1_n_scenes` per month by year: 2017 4.84, 2018 5.02, 2019 4.97, 2020 5.03, 2021 4.84 (round 1: 2.36 to 2.51). 2026: 5.14. Chips without any S1 scene in 2026-07 to 2026-10: **0 of 145** (round 1: 77).
- Same-orbit comparison for the five round-1 chips. The PC v0 chips are other sites than the SH v1 chips, so I compared each PC chip with the median of all SH chips on the same relative orbit and pass direction, month by month over 106 months (2018-01 to 2026-10):

| PC chip | orbit | SH chips on orbit | months identical | max abs difference | 2018 to 2021 yearly means, PC / SH |
|---|---|---|---|---|---|
| P007 | 139 desc | 23 | 97 of 106 | 1 | 4.92/5.00, 4.92/5.00, 5.08/5.08, 4.83/4.83 |
| P009 | 168 desc | 15 | 90 of 106 | 3 | 4.92/5.08, 4.58/4.92, 5.08/5.08, 4.92/4.50 |
| P011 | 146 asc | 16 | 95 of 106 | 3 | 5.08/5.08, 4.92/5.00, 5.00/5.00, 4.83/4.92 |
| P012 | 168 desc | 15 | 89 of 106 | 3 | 4.92/5.08, 4.67/4.92, 5.08/5.08, 4.92/4.50 |
| P013 | 139 desc | 23 | 97 of 106 | 1 | 4.92/5.00, 4.92/5.00, 5.08/5.08, 4.83/4.83 |

  The residual differences are frame-edge and archive differences of single scenes, not a lost satellite.
- Residue (minor, see N5): the store attribute `s1_orbit_rule` still says "S1D scenes excluded" on all 145 stores, and A38 (`docs/assumptions.md:134`) still states "S1A, S1B: (a - 73) mod 175 + 1" before giving the corrected offsets. The S1A-versus-PC RTC comparison for the 10 sanity sites is still "not done" (A38).

**B2. Comparison with published statistics not explained, definitions not matched. Status: resolved.**
- Every row of `results/registry/comparison_official_statistics.csv` (20 rows) now carries `ours_variant`, `comparable` (yes, partly, no), `explanation_class` and a row-specific `explanation`. The same table and the explanations are in `docs/data_card_registry.md` section 10.
- Recomputed from `data/processed/registry/registry_units.parquet` (battery, gross > 999 kW):
  - In operation at 2025-10-15: 338 units commissioned and not finally shut down = 2.4435 GW; minus 9 temporarily shut down = **2.4280 GW** (CSV row 1: 2.42799). Registered by 2025-10-15: **2.2965 GW**, 311 units; 18 late registrations, 0.1315 GW (CSV row 0: 2.29647, text "18 units (0.132 GW)"). Usable: 3.1066 GWh (row 2: 3.10656). All match.
  - Planned, reconstructed at 2025-10-15: 387 units, **3.7036 GW, 8.2064 GWh** (rows 3 and 4 match). The export-date figures (13.08 GW, 40.14 GWh) are now marked `not_comparable`.
  - Additions 2025: 110 units commissioned, 89 registered by 2026-01-06, 721.8 MW gross, 1,441.9 MWh (rows 11 to 13 match). 2026-01 to 2026-09: 194 units, 1,905.9 MW and 3,919.2 MWh over all registrations; 9 were registered after 2026-10-13. The CSV values 1,843.8 MW and 3,837.5 MWh fit that cut.
  - Medium voltage and above: of 623 operating batteries, 380 have a voltage level; 250 MS, 53 HS, 38 HS/MS, 12 HöS, 1 HöS/HS and 1 "Mittelspannung;Niederspannung" give the 355 in row 7; the 3 "Umspannebene MS/NS" units are excluded as stated.
- Matched definitions: the in-operation rows match the reference definition and date. The planned rows are reconstructed at the reference date, with the remaining 26 % gap called unexplained and a route to settle it (2025-10-01 quarterly snapshot). The MV rows carry coverage and an upper-bound variant. Energy-Charts rows are marked "source not opened". The PV rows are marked not comparable (size class). This meets "differences are explained" for batteries. Text defects remain (N3), and PV has no like-for-like row (N2).

### Important

| ID | Status | Evidence |
|---|---|---|
| I1 circularity guard | **partly resolved** | `pilot_sites_v1.parquet` now has `reg_status`, `reg_commissioning_date`; `registry_columns()` (`src/bo/data/registry.py:132-141`) also drops `gross_kw`, `net_kw`, `power_kw`, `usable_kwh*`, `storage_plant_n_linked`. Applied to `pilot_sites_v1.parquet` it still keeps **`size_class`** (registry capacity class, 1-5 / 5-20 / 20-100 / >=100 MW) and **`planned`** (status-derived), plus `n_units`. In `registry_units.parquet` it keeps the capacity-derived `flag_power_*` and `flag_kwh_*`. No chip attribute or variable holds a registry date, status or capacity: I listed the attribute keys of all 145 SH, 11 v0 and 102 demo150 stores and of 181 DOP sidecar JSONs. `other_registered_sites_in_chip` holds technology counts only. The requested test that a feature frame contains no non-id registry column does not exist. Fix: prefix or drop `size_class`, `planned` and `n_units` (`reg_size_class`, `reg_planned`), add the capacity-derived flags to the guard, write the feature-frame test before Phase 3. |
| I2 SH versus PC, offset | **partly resolved** | A36 (`docs/assumptions.md:132`) now quotes a maximum of 0.0109. But `docs/STATUS.md:152` still says "agrees to about 0.001 reflectance". Offset: `results/imagery/offset_step_check.csv` shows no +0.1 step at 2022-01 on either platform (PC B04 p1 0.0329 to 0.0233, SH 0.0421 to 0.0249). I confirmed the PC stores span a real baseline change: v0 items for 2018 to 2020 are baseline 02.12, and from 2022 they are 04.00 or later. `offset_step_raw_dn_pc.csv` shows DN about 1,280 to 1,430 mapping to 0.028 to 0.043, which is consistent with subtracting 1,000 once. Unremarked: PC 2021-11 has B04 p1 0.334 and B08 p1 0.331 (5 chips, a snow or cloud month). Not done: nothing enforces one platform per series (PC stores carry no `source` attribute), and `s2_n_passes_used` keeps two meanings (`shchips.py:145`, `store.py:63`). Fix: add `source` to PC stores and assert it in the feature loader; correct STATUS:152; rename one variable. |
| I3 DOP for pilot v1 | **resolved** | `dop_chips_v1.parquet`: 150 rows, 50 of 50 site chips and 82 of 100 negative chips. `date_type` is `day`, `year_edition`, `production_only` or `none`: day-dated 38 sites and 41 negatives. RP and TH dates are kept as `production_date` and never as `flight_date`; BE and HB edition years go in `flight_year`. I recomputed `dop_pilot_v1_flight_vs_commissioning.csv`: 38 day-dated sites, 24 flown before and 14 on or after commissioning (match). This comparison lives outside the chip metadata. Remaining gaps are stated: BB 5, SH 1, BW 1 without any date. |
| I4 residual cloud and snow | **resolved** | `src/bo/imagery/qc.py`, A40, `results/imagery/qc_flag_rates.csv` (15 of 738 and 19 of 1,141 months). Q015 2022-12, Q044 2024-12 and Q010 2018-01 all have `s2_flag_bright = 1`. Tests: `tests/test_imagery_review.py:13,27`. Phase 3 must use the flags (A40). |
| I5 other technology in chip | **partly resolved** | I recomputed which other-technology registry sites lie inside the 640 m square: Q004, Q009, Q021 and Q036, matching `results/imagery/chips_with_other_registered_sites.csv`. The builder's claim that Q005, Q037 and Q042 lie outside the square holds. Not done: `site_extent_m` on the pilot table. Five sites are wider than the chip (Q039 2,839 m, Q044 4,735 m, Q046 3,645 m, Q047 1,442 m, Q049 3,499 m, from `registry_sites.parquet`). No Phase 4 stratification is recorded. |
| I6 negative sampling | **not resolved** (deferred) | A34 (`docs/assumptions.md:129`) still reads "remainder by area" and records no deviation from KICKOFF 6.1 or any sensitivity test. Hard negatives are still from 8 cells. STATUS:87 defers both to Phase 3. Acceptable for Phase 2 if A34 records the deviation now. |
| I7 quota | **partly resolved** | `results/imagery/quota_log.csv`, platform `cdse_sentinelhub`, November: **8,185.9 PU and 3,501 requests** (1,024 rows), which supports STATUS 2A.17. Round 1 total 5,790.3 PU plus refetch 2,395.6 PU (1,015 rows, one request each) gives the same sum. "6,451" is now sourced (`november_quota_reconcile.csv`: 2,153.8 + 4,296.8). Still open: no reconciliation against the CDSE dashboard, and the 184.0 PU / 144 request ESTIMATE row remains. The refetch used a 9,500 PU cap (`src/bo/imagery/shrefetch.py:33`) instead of the project's 60 % share (`src/bo/imagery/shcost.py:34`, Makefile `chips-s1`), with no entry in the decisions log. Stale 2026-11 item lists remain in 68 of 145 stores. |
| I8 R3 power | **not resolved** (kept open) | `results/imagery/scl_bright_target_test_v1.md:3,27` still uses a 40 m disk; V11 and R3 remain open. Acceptable as an open item. |
| I9 STATUS | **partly resolved** | The header date and the review follow-up table are new. Stale: phase rows 11 and 12 ("B2 being fixed", "B1 being fixed", "DOP chips ... being extracted"); follow-up rows 83, 84 and 86; rows 73 and 74 ("PARTIAL data", "pending full export"); row 152 ("about 0.001"); row 173 "N000 to N099" (the IDs run to N100). The Blockers table is still empty. There is no note reconciling 8,130 and 7,742 PV units. |

### Minor

| ID | Status | Evidence |
|---|---|---|
| m1 ruff | resolved | ruff clean |
| m2 no commit | not resolved | `git log`: "does not have any commits yet"; chips carry `+nogit` |
| m3 negatives summary | resolved | `results/registry/negatives_v1_summary.csv` says 100 |
| m4 pilot parameters, make target | resolved | A50 to A54; `make pilot`; docstring names v1 |
| m5 quantity labels | resolved | `docs/imagery_chip_store.md:27` defines composites as observed measurements |
| m6 grid fields, wording | partly | `registry.py` fixed; `docs/data_card_registry.md:18` still says "operator IDs are not extracted" while `grid_operator_id` is extracted; grid fields are absent from the pilot table |
| m7 analysis plan | not resolved | `docs/analysis_plan.md` does not exist |
| m8 rural benchmark | not resolved | only Bremen in `results/imagery/scan_benchmark.md` |
| m9 hold-out concentration | resolved as documentation | note under A54 |
| m10 cross-zone jitter | resolved in code (`s2pipe.py:138`, test `test_group_passes_prefers_native_zone_tiles`); I did not verify whether the existing PC stores were rebuilt |

## 3. New findings

### B3 (blocking). The S1C boundary at absolute orbit 8,000 is wrong, and 9 Sentinel Hub series now mix relative orbits
- Evidence: `src/bo/imagery/s1orbit.py:5-7,14` and `sentinelhub.py:288` switch S1C to offset 99 from absolute orbit 8,000. The docstring says no S1C data exists between 7,937 and 8,265. Planetary Computer has S1C items at absolute orbits **8,010 and 8,017 (2026-06-08)**, and their STAC relative orbits (139 and 146) follow offset 172, not 99 (`data/chips/v0/P007.zarr`, `P011.zarr`, `P013.zarr`, attribute `s1_items_by_month`). The switch therefore lies between 8,018 and 8,265.
- Consequence in the stored Sentinel Hub series: the evalscript assigns the 2026-06-08 S1C pass of orbit 139 to orbit 37, and the pass of orbit 146 to orbit 44. It entered the 2026-06 median of **9 stores**: N015, N016, N029, N032, N047, N061 and Q033 (orbit 37, descending, acquisition 05:41:43 against the stores' regular 05:49 to 05:50 passes) and N082 and N084 (orbit 44, ascending). The 39 stores on orbits 139 and 146 hold no item of that pass for 2026-06 (lost, where the pass covers them). All 145 stores carry `s1_relative_orbit_enforced_server_side: true` and `s1_orbit_formula` "...99 from abs orbit 8000". The month falls inside the temporal hold-out (A10). This breaks the one-orbit-per-series rule (KICKOFF 6.2, `CLAUDE.md`), which held in round 1.
- Fix: set the S1C boundary inside 8,018 to 8,264 (or read the relative orbit from catalogue metadata). Add the PC pairs (S1C, 8010, 139) and (S1C, 8017, 146) to `PC_PAIRS`. Refetch 2026-06 only for the 48 affected stores (about 48 requests). Correct A38, the `s1_orbit_formula` attribute and the `s1orbit` docstring.

### N1 (important). DOP source table not complete (Phase 2 criterion)
- `docs/research/dop_sources.md` was last modified before round 1. Rows 201 to 213 still show Hessen licence "not read", Hamburg and Saarland unresolved, the Mecklenburg-Vorpommern licence name missing (line 235), and flight-date service "not read" for most states. Rows 202 and 213 say "no pilot site" for Bremen and Thüringen, which now have chips. `docs/data_sources.md:33` likewise says "Coded, no pilot site" for Berlin, Bremen and Thüringen. STATUS 2B.7: "not searched further". 11 negatives in Hessen, 4 in Saarland and 2 in Hamburg have no DOP.
- Fix: close or explicitly mark each open cell as unobtainable with the date and the source tried, and update the stale rows. Until then this Phase 2 criterion is partly met. The author may accept that state, but the record must show his decision.

### N2 (important). No like-for-like comparison for ground-mounted PV
- Both PV rows (18 and 19) are `not_comparable` because the references cover all sizes. Our pipeline reads all 67 solar members of the full export (`docs/data_card_registry.md:24`), so an all-size ground-mounted figure can be computed from the same export.
- Fix: add an all-size variant (commissioned 2025, and 2026-01 to 2026-08, registered by the reference date) so that the PV comparison tests completeness instead of only stating a size difference.

### N3 (minor). Defects in the comparison text
- Row 2 (CSV and data card line 260): "Only 100% of these units carry a plant capacity, so ours is a lower bound for the units with kWh missing" contradicts itself. Make the template conditional.
- Row 10: the upper bound 4.62 GW exceeds the reference 3.6 GW, so "same reasoning" (the gap is definitional because even the upper bound is below the reference) does not hold for GW. State what the row shows.
- Rows 11 to 14 call 61 units / 520 MW / 767 MWh "a third reading of Battery-Charts". `docs/research/bnetza_storage_stats.md:47` says it was seen only in a search summary; say so.
- Rows 16 and 17 say "registered by the export date 2026-10-13". That is the Energy-Charts export date; our export is 2026-11-16.
- Row 7 counts one "Mittelspannung;Niederspannung" unit as MV and above (`registry_compare.py:65-74`, maximum rank). Flag it the same way as the 3 excluded "Umspannebene MS/NS" units.

### N4 (minor). Assumptions register structure
- No duplicate IDs: I listed every first-column ID; A25 to A40 and A50 to A54 are unique, and no file outside the register cites a stale A-number. But section headers repeat: "Part 4" at lines 82 and 138, "Part 5" at lines 102 and 114. A38 contradicts itself (line 134: "S1A, S1B: (a - 73) mod 175 + 1" and later "S1B offset 27"). Renumber the parts and rewrite A38.

### N5 (minor). Stale provenance in the chip stores
- All 145 SH stores carry `s1_orbit_rule` "... S1D scenes excluded". 68 stores list 2026-11 items in `s1_items_by_month`, a month outside the store, and 106 S1C item names in those 2026-11 lists do not map to the stored orbit under the corrected formula. Remove the out-of-axis months and update the attribute.

### N6 (minor). December plan versus the 60 % rule
- Scenario E in `results/imagery/sentinelhub_cost_estimate.csv` gives 8,997 PU for S2 on 150 sites. Scaled to 140 sites that is about 8,400 PU (modelled, my scaling), against a 6,000 PU allowance. `make chips-s2` resumes after a quota stop, so the S2 run will span December and January. STATUS 2A.17 ("Nothing left for January") reads as if December completes the set. State the expected split, and record the 9,500 PU November cap as an author decision or restore the 60 % rule.

### N7 (minor). Column meaning in `results/imagery/dop_pilot_v1_coverage.csv`
- `n_no_date` counts year-only and production-only chips as well (for example RP negatives: 13 production-only and 13 no-date). Rename it `n_no_day_date` or make the classes exclusive.

## 4. Checks that passed in this round

- Circularity: no registry date, status or capacity in any chip attribute, variable or DOP sidecar. The flight-versus-commissioning comparison is a separate results table.
- Scope: no coordinate columns in `results/` CSVs (pattern matches were reflectance ratios), no security-relevant detail, sanity panels unchanged in kind.
- Secrets: no credential patterns in `src`, `tests`, `results`, `docs`, `Makefile`. `.env` is git-ignored with mode 600. No git history exists.
- Quota: November Sentinel Hub use in the log is 8,185.9 PU and 3,501 requests, below the 10,000 and 10,000 free limits (`docs/research/access_platforms.md:15-16`).
- Missing months are still NaN with count 0. 103 of 20,590 SH store months have zero S1 scenes, none in 2026-07 to 2026-10.

## 5. Verdict

**Phase 1: sign-off.** B2 is resolved. N2 and N3 should be fixed before PV capacity figures are used in Phase 5. The I1 residue (`size_class`, `planned`) must be closed before Phase 3 joins the pilot table.

**Phase 2 (apart from the scheduled S2 chips and the author's panel review): no sign-off.** Blocking:
1. B3: the S1C relative-orbit boundary at 8,000 is wrong. The 2026-06-08 S1C pass of orbits 139 and 146 sits in 9 stores on orbits 37 and 44 (orbit mixing), and 39 stores on orbits 139 and 146 hold no item of that pass. The fix and a 48-request refetch are cheap.

The Phase 2 criterion "DOP source table complete" remains partly met (N1). It needs either completion or a recorded author decision before sign-off.

Counts in this round: round-1 findings resolved B1 (with B3 split out), B2, I3, I4, m1, m3, m4, m5, m9, m10 (code). Partly resolved I1, I2, I5, I7, I9, m6. Not resolved I6, I8 (both deferred and open), m2, m7, m8. New: 1 blocking (B3), 2 important (N1, N2), 5 minor (N3 to N7).
