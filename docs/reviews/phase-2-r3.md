# Red-team review, round 3: Phase 2 (imagery pipelines)

Reviewer: red-team-reviewer. Date: 2026-11-18. Basis: `KICKOFF.md` Sections 3, 6 and 7, `CLAUDE.md`, rounds 1 and 2
(`docs/reviews/phase-1-2.md`, `docs/reviews/phase-1-2-r2.md`, both left unchanged) and the files in the repository. I did not
take builder status rows as evidence. Every status below comes from code I read or from numbers I recomputed with
`uv run python` against `data/chips/`, `data/processed/` and `results/`. I did not store the scratch scripts.

Author-pending items, not judged: Sentinel-2 chips for 140 sites (December, 9,500 PU budget recorded in the STATUS decisions
log), the author's review of the sanity panels, acceptance of the DOP source table with its NOT OBTAINABLE gaps
(`docs/research/dop_sources.md:231-245`), and the decision on Mecklenburg-Vorpommern (MV).

## 0. Test suite and lint (rerun by reviewer)

- `uv run pytest`: **157 passed, 1 skipped**. The skip is `tests/test_sentinelhub_integration.py:11` (network, `BO_INTEGRATION=1`). One Pandas4Warning remains at `src/bo/data/registry_sites.py:264`.
- `uv run ruff check src tests`: **All checks passed.**
- New tests: `tests/test_platform_and_orbit.py` (platform mixing, orbit consistency, old boundary, store cleaning) and `tests/test_pilot_guard.py`. `PC_PAIRS` in `tests/test_sentinelhub.py:56-63` now has 22 pairs, including S1C 8010/139, 8017/146, 8018, 8257, 8258 (old numbering) and 8264, 8265, 9840, 10066 (new numbering). The pairs are checked in both Python and the evalscript.

## 1. Round-2 findings

### B3 S1C boundary. Status: **resolved**
- `src/bo/imagery/s1orbit.py:17` sets `S1C_BOUNDARY = 8260`, and `sentinelhub.py:288` uses the same value (`a >= 8260 ? 99 : 172`).
- Independent check from Planetary Computer stores, where items are selected by STAC `sat:relative_orbit`, not by our formula: `data/chips/v0/P007.zarr` and `P013.zarr` (orbit 139) contain S1C 8010 (2026-06-08) and 8287 (2026-06-27), and `P011.zarr` (orbit 146) contains 8017 and 8294. The formula with boundary 8260 maps all four correctly (offset 172 below the boundary, offset 99 above it). The switch therefore lies between 8018 and 8286. The exact placement at 8260 rests on the builder's scan of items 8258 and 8264, which I could not re-run offline. It does not matter for the stored data: no store holds any S1C item with an absolute orbit from 8018 to 8286.
- Recomputed over all 161 stores with S1 item lists (83,316 items): **0 items on another relative orbit, 0 unparsed, 0 item lists for months outside the store axis.** S1C 8010 now sits in 25 stores on orbit 139 and 8017 in 17 stores on orbit 146, counted across both platforms.
- Spot checks, 2026-06. `sh_v1_s1/N015` (orbit 37), `sh_v1_s1/Q033` (orbit 37) and `sh_v1_s1/N082` (orbit 44): each lists 6 items (S1A 2, S1D 3, S1C 7908 or 7915, which map to 37 and 44), and `s1_n_scenes` = 6. The wrongly assigned 2026-06-08 pass is gone. All 145 SH stores carry `s1_refetch_done ... 2026-06..2026-06#s1c-boundary-8260` and the corrected formula text. No store has a zero-scene month in 2026-06 to 2026-10. The 2026-06 counts per store are 3 to 7.
- Minor residue, see R3-m1.

### I1 circularity. Status: **partly resolved (important, before Phase 3)**
- `pilot_sites_v1.parquet` now has `reg_status`, `reg_commissioning_date`, `reg_planned`, `reg_size_class` and `reg_power_kw` (`src/bo/data/pilot.py:37-43`). `registry_columns()` drops all five. Columns left: `pilot_id, subtype, site_key, lat, lon, n_units, unit_ids, bundesland, quantity_type`.
- Still open. `registry_columns()` (`src/bo/data/registry.py:132-143`) keeps the capacity-derived `flag_power_missing`, `flag_power_implausible`, `flag_net_gt_gross`, `flag_kwh_missing` and `flag_kwh_implausible_duration` (`registry_units.parquet`), their `_any` versions, and `n_units` (`registry_sites.parquet`). `tests/test_pilot_guard.py` tests a synthetic five-column frame, not a feature frame. Fix: add the `flag_power_*`, `flag_kwh_*`, `flag_net_gt_gross*` and `n_units` columns to the guard. Write the feature-frame test with the Phase 3 loader.

### I2 platform mixing. Status: **resolved**
- `store.read_series` (`src/bo/imagery/store.py:135-150`) raises `PlatformMixError` on mixed sources and `ValueError` on overlapping variables. Tests: `tests/test_platform_and_orbit.py:21-41`. Sources in the stores: sentinelhub 145, planetary_computer 117. The two stores without the attribute are `split_no-s1/` and `split_no-s2/` (1 each). They count as Planetary Computer by default (R3-m2). The "about 0.001" claim is gone from STATUS. Row 2A.9 now reads 0.0109. `s2_n_passes_used` carries a note attribute on SH stores (`shchips.py:145`). I accept that.

### I5 chips narrower than the site. Status: **not resolved (important, before Phase 4)**
- `site_extent_m` is still absent from `pilot_sites_v1.parquet`. No Phase 4 stratification for Q039, Q044, Q046, Q047 and Q049 is recorded in `docs/assumptions.md` or `docs/analysis_plan.md`, which does not exist. Fix: add the column, and pre-register the stratification.

### I7 quota. Status: **resolved for the log; minor residue**
- Recomputed from `results/imagery/quota_log.csv`, platform `cdse_sentinelhub`, November 2026: **8,221.6 PU and 3,646 requests** (1,169 rows). This matches the stated 8,222 PU and 3,646 requests. The B3 refetch is 145 rows, 35.8 PU and 145 requests. Both totals are below the recorded 9,500 cap and the 10,000 free limit. The 9,500 cap is now an author decision in the STATUS decisions log, so N6 is closed. Residue: the 184.0 PU / 144-request ESTIMATE row remains, and there is no reconciliation against the CDSE dashboard (R3-m3).

### I9 STATUS. Status: **not resolved (important, not blocking)**
- `docs/STATUS.md` still says: line 11 "B2 being fixed" and line 12 "B1 being fixed ... DOP chips ... being extracted"; follow-up rows B1 "fixing", B2 "fixing", DOP "extracting"; row 1.1a "done on PARTIAL data"; row 1.1b "pending full export"; row 2A.16 "99 from absolute orbit 8000" with no pointer to 2A.22; row 2A.17 "Nothing left for January". The Blockers table is empty while the MV decision and the S2 run are pending. Fix: update the phase rows and the follow-up table, mark superseded rows, and list the author-pending items as blockers.

### Other items
| ID | Status | Evidence |
|---|---|---|
| I6 negative sampling | not resolved, deferred | A34 (`docs/assumptions.md:129`) still records no deviation from KICKOFF 6.1 |
| I8 R3 power | open, accepted as open | unchanged |
| N1 DOP table | handed to the author (author-pending) | gaps marked NOT OBTAINABLE with source and date (`dop_sources.md:231-245`); Hessen added (`dop.py:99`) |
| N2 PV like-for-like | resolved (Phase 1) | `comparison_official_statistics.csv` rows 20 and 21, all-size variants, `partly` |
| N3 comparison text | resolved | row 2 "All of these units carry a plant capacity"; row 10 reworded; ambiguous MS/NS units excluded (`registry_compare.py:240`) |
| N4 register structure | resolved | Parts 1 to 7 unique; A38 consistent (boundary 8260, history recorded) |
| N5 stale store provenance | resolved | 0 of 145 SH stores say "excluded"; 0 with "8000"; 0 out-of-axis months over 161 stores |
| N6 December plan | resolved by decision | 9,500 PU monthly budget in the decisions log; wording "Nothing left for January" is part of I9 |
| N7 coverage columns | resolved | `dop_pilot_v1_coverage.csv`: `n_day + n_year_edition + n_production_only + n_date_none + n_no_chip = n_sites` in every row I checked |
| m2 git | not resolved | `git log`: no commits |
| m7 analysis plan | not resolved | `docs/analysis_plan.md` missing; required before any Phase 3 result is inspected |
| m8 rural benchmark | not resolved | Bremen only |

## 2. New findings

### R3-B1 (blocking). Results derived from the restricted MV orthophotos sit in `results/`
- The MV source is recorded as not open data, internal use only, with "chips stay in `data/`, never published or committed" (`docs/data_sources.md:34`, `docs/research/dop_sources.md:207`; `use_restriction` at `src/bo/imagery/dop.py:95`). Yet the publishable folder `results/` contains:
  - `results/imagery/dop_footprint_summary_by_state.csv:5`: footprint areas detected on MV DOP chips (values redacted here for the use restriction). These numbers came directly from MV pixels.
  - `results/imagery/dop_pilot_coverage.csv:6` and `results/imagery/dop_pilot_v1_coverage.csv:9`: MV flight dates (redacted here), read from the restricted service.
- Neither writer filters on `use_restriction` (`src/bo/imagery/footprint.py:279`, the coverage writer in `dop_pilot.py`), so a rerun recreates the rows. Figures: none of the sanity panels uses DOP (`sanity.py` has no DOP code), so `figures/` is clean. Nothing is published yet, because the repository has no commits.
- Fix: until the author decides, drop MV rows from every `results/` and `figures/` output, or write them under `data/processed/` only. Filter on a non-empty `use_restriction` in both writers. Add a test that no results writer emits a restricted source.

### R3-m1 (minor). Orbit-consistency table and boundary evidence
- `results/imagery/s1_orbit_consistency.csv` has 160 rows (sh_v1_s1 135, sh_v1 10, v0 10, test 5). It omits `split_no-s2/P002.zarr`, which also has an S1 item list, and it skips `demo150` (S2 only, correctly). STATUS 2A.23 reports 83,262 items, and I count 83,316 including that store. The 8258/8264 scan behind boundary 8260 exists only as docstring text. Fix: include all stores with S1 lists, or state the exclusion. Save the S1C scan (item ID, absolute orbit, STAC relative orbit) under `results/imagery/`.

### R3-m2 (minor). Test-split stores without `source`
- `data/chips/split_no-s1/` and `split_no-s2/` lack the `source` attribute (one store each). Fix: delete them or tag them.

### R3-m3 (minor). Quota reconciliation
- The ESTIMATE row remains, and the log has not been reconciled with the CDSE dashboard. With 8,221.6 logged PU, 1,778 PU of headroom remains for November, inside a 500 PU margin set for logging gaps. Fix: compare against the dashboard once before the December run.

## 3. Checks that passed

- Circularity: no registry date, status or capacity in chip attributes (unchanged); the pilot table guard holds for the pilot table.
- One orbit per series: 0 violations over 83,316 items (recomputed).
- Scope: no coordinate or geometry columns in any `results/*/*.csv` header. Sanity panels use OSM-public sites (`figures/sanity/public_basis.csv`). No security-relevant detail.
- Secrets: no credential patterns in `src`, `tests`, `results`, `docs` or `Makefile`.
- Missing months stay NaN with count 0 (unchanged).

## 4. Verdict

**Phase 2, apart from the author-pending items: no sign-off yet.** One blocking finding:
1. R3-B1: MV DOP-derived rows (footprint areas, flight dates) in `results/imagery/dop_footprint_summary_by_state.csv:5`, `dop_pilot_coverage.csv:6` and `dop_pilot_v1_coverage.csv:9`, with no filter in the writers. The fix is small: remove the rows, filter on `use_restriction` and add a test.

B3 is resolved. I1 (capacity flags and `n_units`) and m7 (analysis plan) must close before Phase 3. I5 must close before Phase 4. I9 should be fixed with the next STATUS update. Once R3-B1 is fixed, a file check is enough for sign-off; another full round is not needed.

## Addendum: fix verification

Checked 2026-11-18 against code and files. The text above is left unchanged.

**R3-B1: resolved.**
- `src/bo/imagery/dop.py:138-149`: `restricted_states()` returns every source with a non-empty `use_restriction`, which includes MV. `drop_restricted()` removes the rows for those states.
- The filter is applied in `dop_pilot.coverage()` (`dop_pilot.py:63`) and `dop_pilot.evaluate()` (`dop_pilot.py:83`). In `footprint.main()` (`footprint.py:278`) it runs after the per-site parquet is written to `data/processed/` (internal use) and before the state aggregate is written to `results/`.
- Tests: `tests/test_dop_restriction.py`. Three tests check that MV is restricted, that `coverage()` reports no restricted state and that other rows are kept.
- A grep of `results/` and `figures/` for "Mecklenburg", "M-V", "MV" and "mv_dop" finds only registry tables (`capacity_monthly_by_state.csv`, `registry_sites_by_state.csv`, `registry_pipeline_planned_by_state.csv`). Those are acceptable.
- The only DOP-derived outputs are the four `results/imagery/dop_*.csv` files, and none of them contains MV. The sanity figures contain no DOP.
- Residue (minor): `evaluate()` has no test of its own. It shares `drop_restricted`, which is tested.

**I1: resolved for Phase 2.**
- `registry_columns()` (`src/bo/data/registry.py:138-156`) now also drops the prefixes `flag_power_`, `flag_kwh_` and `flag_net_gt_gross`, and the columns `n_units`, `n_units_with_coords` and `n_locations`.
- I applied it to `pilot_sites_v1.parquet`, `registry_units.parquet` and `registry_sites.parquet`. No capacity flag and no unit count survives in any of them.
- Test: `tests/test_pilot_guard.py`, `test_capacity_derived_flags_and_unit_counts_are_dropped`.
- The docstring now calls the deny-list a second line of defence behind an explicit allow-list of imagery features. The feature-frame test is still due with the Phase 3 loader.

**Reruns:** `uv run pytest`: 161 passed, 1 skipped (network integration test). `uv run ruff check src tests`: all checks passed.

**Verdict: Phase 2 signed off, apart from the author-pending items** (S2 chips in December, the sanity-panel review, acceptance of the DOP source table, and the MV decision). Open but not blocking:
- I5: `site_extent_m` and the stratification, before Phase 4.
- m7: `docs/analysis_plan.md`, before Phase 3 results are inspected.
- I9: STATUS stale rows.
- R3-m1 to R3-m3.
