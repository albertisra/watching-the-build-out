# Red-team review: Phase 1 (registry ground truth) and Phase 2 (imagery pipelines, interim)

Reviewer: red-team-reviewer. Date: 2026-11-18. Basis: `KICKOFF.md` Sections 3, 6 and 7, `CLAUDE.md`, and the files
listed in the brief. Builder reasoning was not used. Phase 2 is reviewed as an interim state: Sentinel-2 chips for
140 of 150 sites are scheduled for December.

Every number below was recomputed by me from files in the repository unless a file is cited as its source. Scratch
computations were run with `uv run python` against `data/processed/` and `data/chips/` and are not stored.

## 0. Test suite and lint (rerun by reviewer)

- `uv run pytest`: **115 passed, 1 skipped** (the skip is `tests/test_sentinelhub_integration.py:11`, network test gated by `BO_INTEGRATION=1`).
- `uv run ruff check src tests`: **10 errors**: RUF046 x5 (`src/bo/imagery/dop.py:148`, `footprint.py:112,113,167`, `tests/test_dop.py:227`),
  RUF059 x2 (`tests/test_dop.py:43`, `tests/test_registry_grid.py:39`), BLE001 (`src/bo/imagery/dop_pilot.py:44`),
  SIM115 (`src/bo/imagery/sentinelhub.py:243`), SIM117 (`src/bo/imagery/shchips.py:163`).
- Required test areas: cloud masking, reflectance offset, coordinate transforms, chip extraction, orbit selection and
  compositing have tests (`tests/test_imagery_core.py`, `tests/test_sentinelhub.py`). Index calculations and change-point
  code do not exist yet (Phase 3 and 4). There is no test for the Sentinel-1B or Sentinel-1D relative-orbit formula (see B1).

## 1. Acceptance criteria (KICKOFF Section 7)

| Phase | Criterion | Judgement | Evidence |
|---|---|---|---|
| 1 | Site tables for BESS and PV with a data card | met | `data/processed/registry/registry_sites.parquet` (1,241 battery and 5,790 PV sites, `results/registry/registry_sites_summary.csv`), `docs/data_card_registry.md` |
| 1 | Monthly operational capacity series | met | `results/registry/capacity_monthly_by_state.csv`, `capacity_monthly_national.csv`; my recomputation of battery stock at 2025-10-15 gives 2.444 GW against 2.428 GW in `comparison_official_statistics.csv` (gap from temporary-shutdown handling) |
| 1 | Totals compared with published statistics, differences explained | **partly met** | comparison exists; large differences are not explained per row (B2) |
| 2 | Sentinel chips and monthly composites for 50 pilot sites plus 100 negatives | partly met (interim) | full-range S2 plus S1 for 10 sites (`data/chips/sh_v1`), S1 only for 135 more (`data/chips/sh_v1_s1`), N096 to N100 missing; Planetary Computer S2 for 2025 Q3 only, and for the v0 pilot, not v1 (`data/chips/demo150`) |
| 2 | Clear-observation counts recorded | met | per-pixel `s2_clear_count`, `s2_clear_count_alt`, `s2_clear_count_cld30`; I found 0 months with count 0 and a finite value, or the reverse, over 155 stored chips |
| 2 | National scan benchmarked on one state with runtime and quota | met, with caveats (m8) | `results/imagery/scan_benchmark.md`, `quota_log.csv` stage `scan_benchmark` |
| 2 | DOP source table complete | partly met | `docs/research/dop_sources.md` lines 196 to 213: Hessen licence "not read", Hamburg and Saarland unresolved, Mecklenburg-Vorpommern licence name missing, no flight date service for BW, BB, RP, SH, TH, BE, HB |
| 2 | DOP chips for the same pilot sites with flight dates | **not met** | `data/chips/dop/` holds P000 to P049 (pilot v0, 49 chips, 36 dated, `results/imagery/dop_pilot_coverage.csv`); the Sentinel chips use pilot v1 (Q000 to Q049). See I3 |
| 2 | Visual sanity panels for 10 public sites reviewed | partly met | 20 panels in `figures/sanity/` with an OSM basis per site in `figures/sanity/public_basis.csv`; no record that anyone reviewed them, and the A38 check against PC RTC on the sanity sites is "not done" (`docs/assumptions.md:134`) |

## 2. Blocking findings

### B1. Sentinel Hub Sentinel-1 series drop every Sentinel-1B scene, and Sentinel-1D, so the stored series are not the fixed-orbit series they claim to be
- Severity: **blocking**.
- Evidence: `src/bo/imagery/sentinelhub.py:273-280` computes the relative orbit as `(a - 73) % 175 + 1` for both S1A and S1B.
  The S1B offset is wrong. I checked it against the Planetary Computer chips, whose items carry STAC `sat:relative_orbit`:
  in all five v0 chips with 2018 to 2021 data (P007, P009, P011, P012, P013) the stored relative orbit equals `(a - 27) % 175 + 1`
  for all 118 to 119 S1B items per chip, and never equals the code's `(a - 73) % 175 + 1`.
  The result in the stored Sentinel Hub chips: across all 145 chips in `data/chips/sh_v1` and `data/chips/sh_v1_s1` the item lists contain
  48,991 S1A and 5,901 S1C entries and **zero S1B**. The mean number of S1 scenes per month on the chosen orbit is
  2.36 to 2.51 in 2016 to 2021 on Sentinel Hub against 4.80 to 5.07 in 2018 to 2021 on Planetary Computer for the same kind of site.
  S1D is excluded on purpose (`sentinelhub.py:278`, A38) although its offset could be checked the same way: the PC v0 chips hold 13 to 15 S1D items each.
  After S1A ended (June 2026) this leaves **77 of 145 chips with no S1 scene at all from 2026-07 to 2026-10**. Visible in `figures/sanity/Q010_panel.png` ("no S1" for 2026-07 and 2026-10).
  Those months fall inside the temporal hold-out of the most recent 12 months (A10). Assumption A38 (`docs/assumptions.md:134`) records the formula as "checked against Planetary Computer values", but the check covered S1A and S1C only (`tests/test_sentinelhub.py:56-62`).
- No orbit mixing was found: every S1A and S1C item in the Sentinel Hub chips maps to the stored relative orbit. The defect is silent data loss plus a wrong documented rule.
- Fix: take the relative orbit from catalogue metadata, not from a formula. If a formula is kept, use `(a - 27) % 175 + 1` for S1B and derive the S1D offset from PC STAC items. Add S1B and S1D cases to `test_relative_orbit_formula_matches_planetary_computer_values`. Correct A38.
  Rebuild S1 on Sentinel Hub for 2016 to 2021 (S1B years) and from 2026-04 (S1D) for the 145 chips, and fold that cost into the December quota plan before `make chips-s2` runs.
  Until then, mark these stores as not usable for features.

### B2. Phase 1: differences from published statistics are not explained, and two comparisons do not match in definition
- Severity: **blocking** for Phase 1 sign-off (acceptance criterion "differences are explained").
- Evidence: `results/registry/comparison_official_statistics.csv` and `docs/data_card_registry.md:213-239`. The card gives one generic list of possible causes, not an explanation per row.
  1. Planned storage: ours 13.08 GW and 40.14 GWh (ratio 2.62 and 3.86) is the status at the export date (2026-11-16) set against a BNetzA reference dated 2025-10-15.
     A reconstruction at the reference date is possible from the same table: units registered by 2025-10-15 and not commissioned by then. I get about 3.70 GW gross and 8.21 GWh (ratios about 0.74 and 0.79). That leaves a gap of the opposite sign, which still needs an explanation (units deleted or re-registered since, gross basis).
  2. Medium voltage and above: 358 units and 2.34 GW against 1,292 units and 3.6 GW (ratios 0.28 and 0.65). The reference covers storage of any technology and probably any size at medium voltage and above (`docs/research/bnetza_storage_stats.md:16,42`). Ours covers batteries from 1 MW only, and only the 61 % of operating batteries that got a voltage level from the grid join. Also, `registry_series.py:254,285` counts "Umspannebene Mittelspannung/Niederspannung" and "Mittelspannung;Niederspannung" as medium voltage and above.
  3. Battery additions 2025: one value (1,712 MWh) is set against two references that disagree with each other by 37 % (1,244 MWh from Battery-Charts and 1,700 MWh from Energy-Charts). The close ratio (1.01) is to the reference that was seen only as a search-result summary (`bnetza_storage_stats.md:94`). Agreement with one of two conflicting secondary figures does not validate the series.
     Part of the Battery-Charts gap can be explained from our data: 21 of the 110 units commissioned in 2025 were registered after 2026-01-06, the Battery-Charts data date.
  4. In operation at 2025-10-15: the ratio of 1.01 is partly backfill. 0.132 GW of the 2.444 GW (18 units) were registered after the reference date, so a snapshot-consistent value would be about 2.31 GW (ratio about 0.96, still inside the rounding of "about 2.4 GW").
- I found no sign of tuning: thresholds and power bases follow A1a and A2a, which predate the comparison. But the matches that look good are partly coincidental, and the matches that look bad are partly definitional.
- Fix: add a per-row explanation column to the CSV and the card. Add a reference-date reconstruction for the planned figures and a registered-by-reference-date variant for the in-operation figure. For the medium-voltage comparison, restrict or extend ours to the reference definition and report join coverage, or mark the row "not comparable". Mark the Energy-Charts row as resting on an unopened source.

## 3. Important findings

### I1. Registry dates and status travel unprefixed in the pilot table, outside the circularity guard
- Evidence: `src/bo/data/pilot.py:116-132` renames `reg_status` to `status` and `reg_commissioning_date_last` to `commissioned`. `data/processed/pilot/pilot_sites_v1.parquet` carries `status`, `commissioned`, `planned`, `power_kw`, `size_class` and `n_units`.
  The guard `registry_columns()` (`src/bo/data/registry.py:131-133`) drops only `reg_*` and `site_reg_*`, so it would not catch these. Today nothing leaks: `bo.imagery.sites.load_sites` keeps only id, lat and lon (tested in `tests/test_imagery_core.py:342`). No chip attribute, variable or scene log holds a registry field; I listed the attributes of all 145 Sentinel Hub chips.
  `r3_cli.py:38` reads `commissioned` to select "operating" days, an analysis use that does not reach features.
  Phase 3 and 4 will join this table as the label source, so the leak path exists.
- Fix: keep the `reg_` prefix in every derived table (`reg_status`, `reg_commissioning_date_last`, `reg_power_kw`). Extend `registry_columns()` to capacity fields as well (KICKOFF 6.4 circularity covers dates, status and capacity used as inputs). Add a test that fails if any non-id column from a registry-derived parquet appears in a feature frame.

### I2. Sentinel Hub and Planetary Computer chips cannot be mixed in one series yet
- Evidence: `results/imagery/sh_vs_pc_check.csv` is one site-year (P009, 2024), four bands (B11 and B12 not compared) and all after baseline 04.00.
  The text claims agreement "to about 0.001 reflectance" (`docs/STATUS.md:139`, A36), but the file shows monthly mean absolute differences up to 0.0109 (B08, 2024-09) and 0.0094 (B08, 2024-12). In 2024-09 the mean clear count differs (4.09 PC against 5.69 SH), so the platforms used different observation sets.
  For S1 the products differ (PC `sentinel-1-rtc` against Sentinel Hub `GAMMA0_TERRAIN` with the Copernicus 30 m DEM) and the platform sets differ (B1). The planned comparison is "not done" (A38).
  `s2_n_passes_used` means passes with any clear pixel on PC (`s2pipe.py:157`) but the maximum per-pixel clear count on SH (`shchips.py:95`, attribute `s2_n_passes_used_note`).
  On the offset, my own check found no +0.1 step at 2022-01 on either platform: the median over chips of the 5th percentile of B02 is 0.0532 in 2021-12 and 0.0273 in 2022-01 on SH, and 0.0437 and 0.0237 on PC. This partly closes the open item in A37.
- Fix: do not mix platforms within one site series. Use the `source` attribute to enforce one platform per series. If mixing is ever needed, run the comparison on at least the 10 sanity sites, all six bands, 2021 to 2022 across the baseline change, and S1 VV and VH. Rename one of the two `s2_n_passes_used` variables. Correct the "about 0.001" claim.

### I3. Track B pilot is a different site set from Track A
- Evidence: DOP chips and footprints exist for P000 to P049 (`data/chips/dop/`, `data/processed/pilot/dop_chips_v0.parquet`, `data/processed/footprints/`). The Sentinel chips are for Q000 to Q049 plus N000 to N100. KICKOFF 6.0 requires the same test sites in both tracks. 13 of 49 DOP chips have no flight date (BW 2, BB 3, RP 3, SH 5) and Hessen has none (`results/imagery/dop_pilot_coverage.csv`).
- Fix: run `bo.imagery.dop_pilot --sites data/processed/pilot/pilot_sites_v1.parquet` (and on the negatives). Record per chip whether the flight date is a day, a year or a production date (B-DOP3).

### I4. Residual cloud and snow pass the SCL 4/5/6 mask
- Evidence: site-months with at least 200 clear pixels whose clear-pixel median B02 exceeds 0.2: 7 of 724 in `data/chips/v0` (for example P016 2025-01, P040 2024-12) and 16 of 1,125 in `data/chips/sh_v1` (for example Q015 2022-12 at 0.675, Q044 2024-12 at 0.562, Q010 2018-01, visible as a white frame in `figures/sanity/Q010_panel.png`).
  These are winter months with low clear counts, consistent with SCL labelling snow or haze as class 4 or 5.
- Fix: record this as a known mask failure in `docs/assumptions.md` (A5). Store a per-month brightness or CLD-based flag. Make Phase 3 features robust to it (for example require `s2_clear_count_cld30` agreement, or a B02 and B11 snow test), and test the flag.

### I5. Pilot chips contain registry sites of the other technology
- Evidence: from `registry_sites.parquet`, 7 of 50 v1 pilot chips have a registered site of the other technology within the chip half-diagonal (453 m): Q004 (5 m), Q036 (98 m), Q009 (181 m), Q021 (328 m), Q037 (366 m), Q042 (414 m), Q005 (445 m). The `colocated_*` flags (300 m) mark only 4 of them. Five pilot sites have a unit extent above the 640 m chip width (maximum 4,735 m), so the chip shows only part of the site.
- Fix: add `other_tech_in_chip` and `site_extent_m` to the pilot table, exclude or stratify these sites in Phase 4 metrics, and cover them in the A4 chip-size sensitivity.

### I6. Negative sampling departs from KICKOFF 6.1 and is spatially clustered
- Evidence: random negatives are stratified by federal state area (`src/bo/imagery/negatives.py:192-228`, A34). KICKOFF 6.1 asks for stratification by land cover. All 50 hard negatives come from 8 random cells of about 26 x 24 km (`negatives.py:45-46`), so they will fall into a handful of 50 km CV blocks.
  The core exclusions hold. I checked: every negative is at least 2,050 m from every registry unit at or above 1 MW with coordinates, including rooftop PV and pumped hydro (`units_ge_threshold.parquet`). Negatives are at least 3,341 m apart and at least 2,979 m from any pilot site, and pilot sites are at least 4,597 m apart. No chip overlaps another. The 42 battery units without coordinates (371.8 MW) cannot be excluded.
- Fix: stratify random negatives by a land-cover layer with a recorded licence (for example CORINE), or record the deviation as an assumption with a sensitivity test. Spread hard-negative cells over more blocks before Phase 4.

### I7. Quota accounting: totals reconcile, but the log can lose rows and one STATUS claim is untraceable
- Evidence: summing `results/imagery/quota_log.csv` over Sentinel Hub rows gives 5,790.3 PU and 2,486 requests, matching `docs/STATUS.md:145`. Both ESTIMATE rows are marked in stage and note.
  But `quota.Stage` writes its row only on exit (`src/bo/imagery/quota.py`), and a killed run already lost one row. The replacement estimate is "half of the planned PU", called an "upper-ish bound" without support.
  The hard stop in `shcli.py` relies on this log (`shcost.used_this_month`). STATUS says "The estimate was low (6,451 against 4,297 planned)". Neither number appears in any file, and if 6,451 PU were the true November use, the 6,000 PU (60 %) cap would already be exceeded.
  `s1_items_by_month` lists 2026-11 items for months not in the store, because yearly requests run to 2026-12-31 (`sentinelhub.py:210-211`, `shchips.py:30-44`).
- Fix: reconcile November use against the CDSE dashboard and record the figure with its date in `results/imagery/`. Write quota rows per request, or append them incrementally. Remove or source the 6,451 and 4,297 figures. Cap request time ranges at `end`.

### I8. R3 (SCL masks bright targets) has little power
- Evidence: `results/imagery/scl_bright_target_test_v1.md` uses a 40 m disk around the registry coordinate. The OSM matches in `figures/sanity/public_basis.csv` sit 5 to 158 m from that coordinate, so the disk can miss the structure. Only 6 operating battery sites are available.
  "No masking signal" for PV and "open" for batteries are fair wordings, but the result cannot rule out masking.
- Fix: rerun R3 on OSM or DOP footprints instead of a coordinate disk, with more operating battery sites. Keep V11 and R3 open.

### I9. `docs/STATUS.md` contradicts the delivered state
- Evidence: the header says "Last update: 2026-11-12". The phase table says Phase 1 "only task 1.0 approved" and Phase 2 "not started" (lines 11, 12). Task 1.1a says "done on PARTIAL data ... totals are lower bounds" and 1.1b "pending full export" (lines 73, 74), while `docs/data_card_registry.md:9` and `registry_run_meta.csv` show a complete export with the grid join.
  The Blockers table is empty although line 143 names an author decision. STATUS also mixes PV counts (8,130 units in the coordinate check against 7,742 in scope, from different power bases) without saying so.
- Fix: update STATUS: phase states, task 1.1 rows, blockers, and a note reconciling 8,130 and 7,742.

## 4. Minor findings

- m1. Ruff reports 10 errors (Section 0). Fix them or add justified per-line exemptions.
- m2. No git commit exists, so every chip carries `code_version` "...+nogit" (`src/bo/imagery/store.py:18-24`) and stored chips cannot be traced to code. Ask the author for a first commit before the December runs.
- m3. `results/registry/negatives_v1_summary.csv` says 99 negatives. `negatives_v1.parquet` holds 100 after `top_up_random` (N100), and the summary was not rewritten.
- m4. Pilot selection parameters (`N`, `MIN_YEAR = 2018`, `MIN_SEPARATION_M = 2000`, `MAX_PLANNED_SHARE = 0.2`, `src/bo/data/pilot.py:37-40`) are not in `docs/assumptions.md`. The docstring still names `pilot_sites_v0.parquet` as output (line 16). Pilot v1 and negatives v1 have no `make` target, so they are not rebuildable with one command.
- m5. Quantity labels: `docs/imagery_chip_store.md` and the panel subtitles ("Detected imagery for review") label Sentinel composites as *detected*. In KICKOFF 3.4 "detected" means model output. Define imagery composites as measurements, separate from detections, in the register.
- m6. Grid fields: `registry_sites.parquet` holds coordinates, MW, `grid_operator_id` and `voltage_level` per site. These are public MaStR fields kept in `data/processed` only, and no results file or figure uses them. Drop them from any table handed to imagery, model or discovery stages so they can never be joined with detections (3.5).
  `registry.py:22` says "operator IDs are never extracted" while the grid operator ID is extracted. Say "plant operator".
- m7. `docs/analysis_plan.md` does not exist. R3 already reports bootstrap intervals over sites without a pre-registered plan. Create the file before Phase 3 analyses.
- m8. The scan benchmark state, Bremen, is the smallest and most urban state and consists of two separate parts. Scaling by area (factor 926, `results/imagery/scan_benchmark.md`) is labelled modelled, which is correct. Benchmark a rural state as well before quoting the national cost.
- m9. 30 of the 50 v1 pilot sites were commissioned in 2025 or 2026 (19 in 2026, `pilot_sites_v1.parquet`). Most construction events will fall inside the temporal hold-out (A10). Plan the Phase 4 split with this in mind.
- m10. Cross-zone reads on Planetary Computer warp neighbouring-zone tiles with nearest resampling and merge them with native-zone tiles in the same month (`src/bo/imagery/io.py:84-96`, `s2pipe.py:98-121`). That gives sub-pixel jitter for sites near 12 E (Q000, Q008, Q018, Q034, Q041). Record which tile and zone fed each pixel, or use one tile per site.

## 5. Checks that passed

- Chip centring: for all 145 Sentinel Hub chips the chip centre lies 0.4 to 6.9 m from the pilot or negative coordinate, within half a pixel diagonal. Pixel-centre x coordinates match the transform, and y is descending (north up).
- UTM zone: zone 32 for longitudes 6.01 to 11.97 E, zone 33 for 12.03 to 14.19 E. The lon/lat order is consistent (`always_xy=True` throughout `geo.py` and `registry_sites.py`).
- Missing months: no interpolation. Every month with count 0 is NaN on both sensors in all 155 chips.
- Sentinel-1 orbit: no chip mixes relative orbits. On Planetary Computer, S1A, S1B, S1C and S1D share one relative orbit per site by STAC metadata. On Sentinel Hub, see B1.
- Scope: no coordinates or UTM pairs in `results/`, `docs/` or `figures/` CSVs. The sanity panels carry pilot IDs only, with no annotation, and each has an OSM public basis recorded. No security-relevant detail found.
- Secrets: no credential values in code, results, docs or chip metadata. `.env` is git-ignored with mode 600, there is no git history to leak, and credentials are read only at runtime (`sentinelhub.py:33-51`).
- Free-service rule: only free tiers are used (Planetary Computer anonymous, CDSE quotas, open DOP WMS, Overpass). The fee-based BKG mosaic is not used (`docs/research/dop_sources.md:4`).

## 6. Verdict

**No sign-off.** Blocking findings:
1. B1: the Sentinel Hub S1 relative-orbit formula is wrong for S1B and S1D is excluded. Every S1B scene is missing from 145 chips, and 77 of 145 chips have no S1 in 2026-07 to 2026-10.
2. B2: the Phase 1 comparison with official statistics does not explain its differences, and two comparisons do not match the reference definition (planned figures 13 months apart, medium-voltage scope and join coverage).

Phase 2 acceptance as interim: one criterion not met (DOP chips for the same pilot sites, I3), three partly met, two met. Phase 1: two met, one partly met (B2). Counts: 2 blocking, 9 important, 10 minor.
