# Chip store (Phase 2, Track A)

Code: `src/bo/imagery/`. Build: `make chips` (see `Makefile`) or `uv run python -m bo.imagery.cli chips --help`.
Stores live under `data/chips/<version>/<site_id>.zarr` (Zarr v2 through xarray; not committed). The site list is an
input: any parquet with an id column (`site_id`, `pilot_id` or `neg_id`) and `lat`, `lon`. No registry attribute is read.

Dimensions: `month` (UTC calendar month starts, one common axis for S1 and S2), `band`, `y`, `x` (UTM pixel centres).
Chip grid: 64 x 64 pixels at 10 m by default (`--size`), upper-left corner snapped to a multiple of 10 m in the local UTM zone.

| Variable | Dims | Meaning |
|---|---|---|
| `s2_refl` | month, band, y, x | Monthly median surface reflectance of clear pixels (float32). NaN where no clear observation. Offset applied per item by processing baseline (R5), floor at 0 |
| `s2_clear_count` | month, y, x | Clear observations per pixel under the primary rule (SCL 4, 5, 6; A5). 0 where `s2_refl` is NaN |
| `s2_clear_count_alt` | month, y, x | Same under SCL 2, 4, 5, 6, 7 (A29) |
| `s2_n_passes`, `s2_n_passes_used` | month | Overpasses touching the chip, and those with at least one clear pixel |
| `s1_vv_db`, `s1_vh_db` | month, y, x | Monthly median backscatter in dB (gamma0 RTC, one relative orbit). NaN where missing; `s1_vh_db` is all NaN if `--pols vv` |
| `s1_count` | month, y, x | Valid observations per pixel (first polarisation) |
| `s1_n_scenes` | month | Acquisition days used |

Attributes: `site_id`, `crs_epsg`, `transform` (affine a, b, c, d, e, f), `bounds_xy`, `chip_size_px`, `resolution_m`,
`time_start`, `time_end`, `code_version` (package version plus git hash), `attribution`, `s2_clear_rule`, `s2_alt_rule`,
`s2_offset_policy`, `s2_items_by_month`, `s2_processing_baseline_by_item` (JSON), `s1_relative_orbit`,
`s1_pass_direction`, `s1_orbit_candidates_orbit_dir_ndates`, `s1_items_by_month`, `s1_speckle_filter`, `s1_polarisations`.
Per-scene SCL class fractions and clear fractions are in `data/chips/<version>/scene_logs/<site_id>.parquet`.

Rules kept: missing months stay NaN with count 0 and are never interpolated; one relative orbit and pass direction
per site; S1 and S2 values are *observed* quantities (measurements, here aggregated into monthly composites). They are not model output, so they are not "detected" in the sense of KICKOFF 3.4, and they are not ground truth either. Only the scan candidates and the SCL class and cloud-probability layers are model output (*detected*).
Attribution: Contains modified Copernicus Sentinel data 2015-2026.

## Platform mixing (review finding I2)

Sentinel Hub (`source = sentinelhub`) and Planetary Computer chips **must not be combined in one site series yet**. The
Sentinel-2 comparison covers one site-year and four bands (`results/imagery/sh_vs_pc_check.csv`): median monthly mean
absolute differences are 0.0008 to 0.0031, the maximum is 0.0109 (B08, 2024-09, where the two platforms used different
observation sets). Sentinel-1 differs by product (Planetary Computer RTC with PlanetDEM against Sentinel Hub gamma0 terrain
with the Copernicus 30 m DEM). Use one platform per series; the `source` attribute (absent on the older Planetary Computer
stores, which are Planetary Computer) must be constant inside a series.
`s2_n_passes_used` is the number of passes with at least one clear pixel on Planetary Computer stores and a lower bound
(the per-month maximum of the per-pixel clear count) on Sentinel Hub stores; the attribute `s2_n_passes_used_note` says which.

Reflectance offset at the January 2022 baseline change: no step on either platform (`results/imagery/offset_step_check.csv`,
`offset_step_raw_dn_pc.csv`). Planetary Computer serves raw DN, the +1000 offset is present in every item of baseline 04.00
or later (including December 2021 scenes) and is subtracted once by `reflectance.dn_to_reflectance`; Sentinel Hub applies its
harmonisation (`harmonizeValues = true`) and nothing is subtracted client side.

## Quality flags and context attributes

- `s2_flag_bright` (per month): snow, haze or thin cloud passing the SCL 4/5/6 rule (`qc.py`). `s2_flag_cld_disagree` on
  Sentinel Hub stores. Flags never remove months.
- `other_registered_sites_in_chip`: JSON, registered sites of any technology inside the chip other than the centre site, by
  technology (`ground_pv`, `battery`), from `registry_sites.parquet`; no dates, status or capacity.
- `s1_refetch_done`, `s1_orbit_formula`: Sentinel-1 windows replaced after the relative-orbit fix (S1B 2016-09 to 2021-12, S1D from 2026-04).

- `s2_tile_rule`: Planetary Computer stores prefer tiles of the chip's own UTM zone and warp a neighbouring-zone tile only when a pass has no native tile (review m10; matters for sites near 12 E). Sentinel Hub stores are resampled server-side on one grid, so the rule does not apply.

## Earth Engine stores (`source = earthengine`)

Built by `src/bo/imagery/eechips.py`. Sentinel-2 values equal the Sentinel Hub values to display precision in most months (both are
the harmonised Level-2A product); the cloud-probability count is `s2_clear_count_csp060` (Cloud Score+ cs_cdf >= 0.60), not CLD <= 30.
Sentinel-1 is sigma0 dB with an ellipsoid-based terrain correction, not gamma0 terrain-flattened, and sits about 0.6 to 1.0 dB below
the Sentinel Hub series for the compared sites. `store.read_series` refuses to combine Earth Engine with Sentinel Hub or Planetary Computer stores.
