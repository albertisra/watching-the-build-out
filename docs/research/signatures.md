# Physical signatures of battery yards and solar parks in Sentinel-1 and Sentinel-2

Status: draft, Phase 3 task 3.2   Written: 2026-11-18   Author: remote-sensing-physicist

The minimum detectable sizes in section 5 are a **prediction written on 2026-11-18, before any detector
exists**. Phase 4 compares them with the empirical recall curves. Do not edit section 5 after Phase 4 results
are seen; add a dated comparison below it instead.

Quantity labels. Chip values are observed measurements (monthly composites). Contrasts, PSF widths, noise
quantiles and minimum sizes are **modelled** (derived from the chips with stated assumptions F1 to F10 in
`docs/assumptions.md`). MaStR commissioning months and capacities are **observed** registry values; they select
months for measurement and appear as reference lines, never as feature inputs. Nothing here is a detection.

Platform and backscatter convention. Sections 1 to 9 were measured on the Sentinel Hub (`sh_v1`, `sh_v1_s1`) and
Planetary Computer (`v0`) stores, whose Sentinel-1 is **gamma0, terrain flattened**; their tables sit directly under
`results/features/` (copy in `results/features/signatures_2026-11-18_frozen/`). Phase 4 features come from the Earth
Engine store `ee_r1`, whose Sentinel-1 is **sigma0, ellipsoid terrain correction, not flattened**. Section 10 reruns
the analysis on `ee_r1` (`results/features/signatures_ee_r1_sigma0/`) and on the current Sentinel Hub and Planetary
Computer stores (`results/features/signatures_sh_pc_gamma0/`). Every table there carries `platform` and
`s1_convention` columns.

Reproduce: `make signatures` (`bo.features.signatures`, `bo.features.scl_did`, `bo.features.confusers`).
Feature code: `src/bo/features/`, allow-list `src/bo/features/allowlist.py`, tests `tests/test_features.py`.
No new imagery was read for this task (Planetary Computer use 0 GB, Sentinel Hub use 0 PU).
Figures carry "Contains modified Copernicus Sentinel data" and, where outlines are used, "(c) OpenStreetMap
contributors".

## 1. Data and method

- Sites shown: the 20 public sites of `figures/sanity/public_basis.csv` (OSM `power=plant` or `generator` with a
  battery or solar source tag, 5 to 158 m from the registry coordinate). Outlines from one Overpass request
  (`src/bo/features/osm_geom.py`). Two PV entries (Q042, Q046) are single `generator` ways of 1,326 and 223 m2
  inside parks of 50 and 447 MW and do not outline the park; they are excluded from every fit. Q014's outline
  (513 m2 for 27.5 MW) is smaller than any footprint ratio in `site_footprints.md` allows and is probably
  partial; outlines under 1,000 m2 are excluded from fits.
- Chips: Sentinel Hub `sh_v1` (Q sites, S2 six bands from 2017, S1 from 2015) and Planetary Computer `v0`
  (P sites, S2 four bands without B11 and B12, S1 VV only). Never mixed within a series. Several v0 stores start
  in 2023, so P016, P040, P042, P048 have no "before" window.
- Contrast. For each site, variable and season (summer April to September, winter October to March), the
  per-pixel change between the same calendar months after commissioning (0 to 24 months) and before it
  (48 to 24 months earlier, F6) is regressed on the pixel's fill fraction. The fill fraction is the OSM outline
  rasterised at 1 m, blurred with a Gaussian PSF and averaged into 10 m pixels (20 m for B11 based variables).
  The slope is the **pure contrast**: the change a pixel would show if the target filled it. SAR is fitted in
  linear power (F9), because power and not decibels add inside a resolution cell.
- Effective PSF: the Gaussian width that maximises the mean R2 of that regression over sites (F8).
- Noise: the year-over-year change of window means (radius 8 to 120 m) minus the chip median change, at
  target-free windows: Sentinel-2 at pixels more than 100 m from the outline in the 20 sanity chips, Sentinel-1
  at the 45 random negatives of `sh_v1_s1` (no registered unit within 2 km). One-month values (`d1`) and the
  mean of six consecutive months (`d6`, at least three valid) are both kept.

## 2. Features, physical rationale and expected failure

All features are computed per month from the chip alone (`bo.features.site.site_features`). Centre is a 40 m
disk at the chip centre, ring 150 to 300 m (F1). `_c` centre median, `_ctr` centre minus ring, `_yoy` minus the
same month a year earlier, `_sd12` and `_cv12` trailing 12-month spread. Missing months are NaN with counts
(`s2_valid_c`, `s2_nobs_c`, `s2_n_valid_12`, `s1_n_scenes`, `s1_valid_c`, `s1_n_valid_12`); months failing the
A40 quality flags are NaN with `s2_qc_flag = 1`. Nothing is interpolated.

| Feature | Formula status | Why it should respond | When it should fail |
|---|---|---|---|
| `s2_ndvi_*` | experimental (formula UNVERIFIED in `pv_spectral_indices.md` fact 3) | Clearing removes chlorophyll (red absorption) and leaf structure (NIR scattering), so NDVI drops; modules shade the ground between rows and suppress vegetation partly; gravel pads under containers remove it fully | Winter and after harvest the field is already bare, so clearing produces no drop; grass kept between PV rows holds NDVI up (measured PV contrast only -0.21 in summer and -0.08 in winter, `results/features/contrast_summary.csv`); crop rotation causes year-over-year changes of the same size (section 4) |
| `s2_vnir_*` (mean of B02, B03, B04, B08) | band mean | Gravel and light containers raise visible reflectance; dark crystalline PV lowers it (aVNIR criterion of Ji et al., fact 6) | PV over grass: darker modules and bright grass cancel at 10 m (measured PV contrast -0.009 summer); dark or green containers; wet gravel |
| `s2_b11_*`, `s2_r1108_*` (B11 / B08) | band level, ratio | Silicon absorbs below about 1.1 µm and transmits beyond, and the B11 peak with low B08 is the published Sentinel-2 PV statement (fact 1); the ratio expresses it without NDPI's unstable denominator | 20 m native resolution (A30) halves the spatial detail; bare dry soil also has B11 above B08 (ratio near 1 at quarries and yards, `confuser_summary.csv`) |
| `s2_ndpi_*` | VERIFIED (Feng et al. 2024) | Same physics as B11 / B08 | Ill-conditioned: the denominator B08 minus B12 crosses zero over bare soil and PV mixtures, so NDPI jumps between large positive and negative values (one-month 99 % noise quantile of a single pixel is about +3.2 in summer, `noise_yoy_window.csv`); guarded by F3 |
| `s2_plastic_*` | VERIFIED script (Ibrahim and Gobin, fact 8) | Plastic films and greenhouse covers raise blue relative to the VNIR mean; included as a confuser check, not a target feature | Not selective (bare soil and coasts respond, per the source); needs B02, absent from the Planetary Computer demo store |
| `s2_ndbi_*`, `s2_mndwi_*` | experimental | NDBI: SWIR above NIR over built surfaces and modules; MNDWI: water and flooding check | NDBI rises over any bare soil; MNDWI responds to dark wet surfaces |
| `s2_b08_tex_*`, `s2_b08_grad_c` | spatial statistic | Construction is patchy (pads, roads, spoil) and a finished yard has sharp edges against fields; PV rows themselves (pitch 3 to 4 m, `site_footprints.md`) are far below the 20 m Nyquist period of 10 m pixels and are **not** resolved | Field boundaries and roads produce the same texture; inside a large park the texture is low and uniform |
| `s1_vv_*`, `s1_vh_*` | level in dB: gamma0 in sections 1 to 9, sigma0 in the Phase 4 store `ee_r1` (section 10) | Container rows and inverter stations are metal boxes on flat ground: dihedral (double bounce) returns make them bright, as urban areas are (`sentinel1.md` fact 28). Removing vegetation lowers VH volume scattering. Tilted PV modules are smooth at C band (5.5 cm) and reflect specularly away from the radar for most look geometries, so parks darken | Double bounce depends on the angle between container rows and the look direction (no source, `sentinel1.md` fact 30): some yards will not brighten. Soil moisture, wet snow and freezing move backscatter by several dB |
| `s1_vvvh_*` | VV minus VH in dB | Single and double bounce keep the polarisation (VV up), volume scattering depolarises (VH up); the ratio separates the two | Mixed yards contain both; measured battery change is small and site-dependent (median +0.8 summer, +0.2 winter in linear units, n = 4) |
| `s1_vv_p90_c` | 90th percentile of the centre | A few strong scatterers raise the upper tail before they raise the median | Speckle (single-scene SD 2.2 dB for ENL 4.4, `results/features/s1_speckle_check.csv`) inflates the tail |
| `_yoy` | same month one year earlier (A8) | Removes the seasonal cycle and the fixed look geometry of the single orbit, so a permanent change stands out for 12 months and then vanishes | Crop rotation and year-to-year weather are the dominant noise (section 4); the change is visible for only 12 months after it occurs |
| `_sd12`, `_cv12` | trailing spread | A finished yard or park has no phenology: the spread drops. Median `s2_ndvi_c_sd12` before against after: battery 0.170 to 0.094, PV 0.231 to 0.108; `s1_vv_c_cv12` battery 0.273 to 0.164, PV 0.410 to 0.207 (8 battery and 5 to 8 PV sites, `results/features/stability_before_after.csv`) | Permanent grassland and forest are equally stable; requires 6 valid months (F4) |
| `_ctr` | centre minus ring | Removes chip-wide weather, haze and phenology | Large parks fill the ring as well (ring 150 to 300 m), so contrast falls as parks grow; a co-located PV park in the ring confounds battery contrast (section 7) |

**Relevance list** (for the forward selection in `docs/analysis_plan.md`, A73; ordered by expected strength
from sections 3 and 5):
- Battery: `s1_vv_c_yoy`, `s1_vv_ctr`, `s1_vv_ctr_yoy`, `s1_vh_c_yoy`, `s1_vv_p90_c`, `s1_vv_c_cv12`,
  `s2_ndvi_c_yoy`, `s2_vnir_c_yoy`, `s2_ndvi_c_sd12`, `s2_b08_tex_c`.
- PV: `s2_r1108_c_yoy`, `s2_r1108_c`, `s2_b11_c_yoy`, `s2_ndpi_c_yoy`, `s2_ndbi_c`, `s2_ndvi_c_sd12`,
  `s1_vv_c_yoy`, `s1_vh_c_yoy`, `s1_vv_c_cv12`.
- Quality covariates for both (never evidence on their own): `s2_valid_c`, `s2_nobs_c`, `s2_n_valid_12`, `s2_qc_flag`,
  `s1_n_scenes`, `s1_n_valid_12`.
- Confuser checks, not target evidence: `s2_plastic_*`, `s2_mndwi_*`.

## 3. Measured signatures on public sites

Figures: `figures/signatures/<id>_series.png` (one per public site; centre disk, ring and inside-outline series
for NDVI, VNIR, B11, NDPI, VV, VH, VV minus VH) and `figures/signatures/aligned_yoy.png` (year-over-year change
against months since commissioning). Since 2026-11-19 (review M4) no figure draws a registry date, status, capacity,
technology or outline size for the 15 sites that are round-1 queue items (list in
`results/features/signature_sites_fold0.csv`); the commissioning line is drawn only for the 5 non-queue sites, and
`aligned_yoy.png` contains only those 5. Statements below about timing relative to commissioning for queue sites
rest on the result tables, not on the figures.

Pure contrasts (after minus before, median over sites, `results/features/contrast_summary.csv`; site values in
`contrast_at_best_psf.csv`):

| Variable | Battery summer | Battery winter | PV summer | PV winter |
|---|---|---|---|---|
| NDVI | -0.37 (7 sites, range -0.62 to -0.00) | -0.24 | -0.21 (3) | -0.08 |
| VNIR reflectance | +0.060 (7) | +0.037 | -0.009 (3) | -0.027 |
| B11 reflectance | -0.005 (4) | +0.013 | +0.139 (3) | +0.087 |
| B11 / B08 | +0.11 (4) | +0.13 | +1.17 (3) | +1.69 |
| VV, linear power ratio minus 1 | +8.2 (7, range +1.9 to +9.1) | +8.1 | -0.33 (3) | -0.42 |
| VH, same | +4.2 (4) | +5.1 | -0.34 (3) | -0.29 |

In words: a battery yard is a strong SAR brightening (VV power up about ninefold for a fully covered pixel at the
median site) with a moderate NDVI drop and a small VNIR brightening; spectrally it is close to a gravel yard. A
solar park is a SWIR brightening relative to NIR (B11 / B08 up by more than one) with SAR darkening by roughly
1.5 to 2.5 dB and a weak NDVI drop. Q015 (`Q015_series.png`) shows the sequence: NDVI collapses and VNIR rises in
early 2024 (clearing, pad), VV and VH rise from mid-2024 (containers), and the seasonal NDVI cycle disappears.
In `aligned_yoy.png` battery VV year-over-year change reaches +5 to +12 dB around commissioning and returns to zero
about 12 months later, as a year-over-year feature must. PV sites show negative VV changes of up to about -8 dB.
PV contrasts rest on three Sentinel Hub sites (Q044, Q047, Q049); battery S2 SWIR and VH contrasts on four.

Effective PSF (`results/features/psf_effective.csv`): Gaussian sigma 7.5 m (FWHM 17.7 m) for VV, NDVI, B11 and
B11 / B08, 10 m for VNIR, 15 m for VH (weaker fit). The VV value agrees with the IW GRD resolution of 20.4 x 22.5 m
(`sentinel1.md` fact 15). For the 10 m optical bands the fitted width is larger than one pixel because it
contains co-registration error, monthly compositing, the 20 m replication and OSM outline error; treat it as an
upper bound on the sensor PSF. B08 alone gave no usable fit (contrast sign varies between sites).

Speckle check (`results/features/s1_speckle_check.csv`): with ENL 4.4 and a median of 5 scenes per month, speckle
alone predicts a single-pixel year-over-year SD of 1.74 dB; the measured robust SD is 2.27 dB (VV) and 2.54 dB
(VH). The excess is real change of the background (moisture, vegetation), which is why measured noise, not speckle
theory, is used in section 5.

Registry coordinate offset. Q044's coordinate lies 158 m from its outline (`public_basis.csv`); in
`Q044_series.png` the centre-disk series follows the ring while the inside-outline series shows the park
(NDVI and VV drop from mid-2025). Centre features assume the target lies under the 40 m disk. PV coordinates in
the public set sit 50 to 158 m from the OSM centre, battery coordinates 5 to 129 m.

## 4. Confusers and the check for each

Descriptive values (centre medians, July to September 2025; S2 from the Planetary Computer demo store, pilot v0
and negatives v0; S1 from `sh_v1_s1`, pilot v1 and negatives v1; `results/features/confuser_summary.csv`,
`figures/signatures/confusers_2025q3.png`). Group sizes are small (car parks 2; S1 batteries 4; S2 random 1), so the
values describe, they do not separate.

| Confuser | What it shares with the target | Measured (median) | Check |
|---|---|---|---|
| Greenhouses | bright, low NIR, man-made, stable | NDVI 0.57, B11 / B08 0.73 against PV 2.18; VV -8.0 dB | `s2_plastic_*` high; B11 / B08 below 1 (glass and film do not show the silicon SWIR step); greenhouses exist before the change window, so `_yoy` stays near zero |
| Plastic mulch and foil tunnels | sudden low NIR and bright VNIR over fields | not in the negatives | Appears and disappears within one season: `d6` persistence and a return to the old NDVI the next year; `s2_plastic_*` |
| Warehouse roofs | SAR as bright as battery yards (VV -4.1 dB, p90 +1.5 dB against battery -6.5 and -3.1) | NDVI 0.04, B11 / B08 0.98 | Existed before: no year-over-year change; size and shape need Track B; roofs lose more clear observations under the cloud-probability rule (R3) |
| Car parks | flat, sealed, low NDVI | VV -10.5 dB, VH -19.6 dB (darkest group) | SAR dark, unlike battery yards; stable texture 0.011 |
| Gravel and industrial yards | the battery "pad" stage is a gravel yard | VV -7.6 dB, p90 -3.1 dB, texture 0.032 (battery 0.032) | No static check at 10 m. Only the sequence (vegetation loss, then SAR brightening months later) and Track B container geometry separate them. Main battery confuser |
| Quarries | bare, bright SWIR, low NDVI | NDVI 0.40, B11 / B08 0.95 | Continuous change: high `_sd12` and `_cv12` that never settle; usually larger than the ring, so `_ctr` stays small |
| Flooded fields | VV and VH fall like a PV park | not in the negatives | MNDWI rises above the field value; the drop reverses within weeks to months, so `d6` persistence fails and the next year returns to normal |
| Snow | bright VNIR, SAR change | QC flag | `s2_qc_flag` blanks the month (A40); wet snow lowers S1 backscatter for a few winter months only, which `d6` persistence and same-month `_yoy` suppress unless winters differ strongly |

## 5. Prediction: minimum detectable site size (written before any detector exists)

Model (assumptions F7 to F9). A square target of area A sits at the chip centre with random sub-pixel phase. Its
expected change in a window of radius r is the pure contrast times the mean fill fraction of the window after the
effective PSF (SAR: 10 log10(1 + fill x power contrast)). It is called detectable when that change exceeds the
one-sided 99 % quantile (and, as a second operating point, 95 %) of the target-free noise for the same window and
season. Two windows: the best of eight radii (8 to 120 m), and the fixed 40 m feature window of the allow-list.
Two persistence levels: one month (`d1`) and six-month mean (`d6`). Areas are converted with
`site_footprints.md` ratios: battery 94 to 150 m2 per MW; PV 0.88 ha per MWp, range 0.7 to 1.2.
Source table: `results/features/min_detectable_size.csv` (columns `amin_q99_m2`, `amin_q99_r40_m2`, capacity
columns `*_mw_lo`, `*_mw_hi`).

**Headline prediction for comparison with Phase 4.** `docs/analysis_plan.md` section 7.1 (A82) defines the
minimum detectable size as the size where recall reaches 0.8 and fits recall against log10 MW. The matching
model quantity is the size at which the expected change exceeds the 99 % noise threshold by the noise's 20 %
quantile (approximated as 0.8416 robust SD), i.e. 80 % detection probability (`amin_q99_p80_r40_m2` and
`amin_q99_p80_m2`). Central case: the 40 m feature window, six-month persistence, median contrast.

| Technology | Sensor and feature | 40 m window, 6 months (central) | 40 m window, 1 month | Best window, 6 months (lower bound) |
|---|---|---|---|---|
| Battery | S1 VV | 587 m2 winter to 884 m2 summer: **3.9 to 9.4 MW** | 1,014 to 1,752 m2: 6.8 to 18.6 MW | 130 to 149 m2: 0.9 to 1.6 MW |
| Battery | S1 VH | 1,162 to 1,752 m2: 7.8 to 18.6 MW | 2,304 to 4,565 m2: 15 to 49 MW | 673 to 1,014 m2: 4.5 to 10.8 MW |
| Battery | S2 VNIR | 9,047 m2 summer (60 to 96 MW); winter not reached | not reached | 9,047 m2 summer |
| Battery | S2 NDVI (experimental) | not reached | not reached | 15,637 m2 summer (104 to 166 MW) |
| PV | S2 B11 / B08 | 2,641 m2 winter to 5,235 m2 summer: **0.22 to 0.75 MWp** | 6,002 m2 winter (0.50 to 0.86 MWp); summer not reached | 884 to 2,641 m2 |
| PV | S2 NDPI | 3,982 to 6,882 m2: 0.33 to 0.98 MWp | 11,894 m2 winter; summer not reached | 1,333 to 3,982 m2 |
| PV | S2 B11 | 3,982 m2 summer to 13,638 m2 winter: 0.33 to 1.95 MWp | not reached | 1,528 to 13,638 m2 |
| PV | S1 VV | not reached | not reached | 27,027 m2 winter (2.3 to 3.9 MWp); summer not reached |

"Not reached" means no square up to 160,000 m2 passes in that window; for the 40 m window a target larger than
the window cannot raise the window mean further, so those cells need a larger centre (F1 sensitivity test).
The prediction on the analysis plan's log10 MW axis: **battery recall reaches 0.8 between about 4 and 9 MW
(Sentinel-1, Track A), PV recall reaches 0.8 below 1 MWp (Sentinel-2 SWIR)**, both conditional on the coordinate
lying inside the site, on the contrasts of section 3 holding for small sites, and on six months of persistent
change being available.

The tables below give the 50 % detection point (expected change equal to the threshold) for completeness.

**Battery storage, median contrast, 99 % quantile**

| Sensor and feature | Best window, 1 month | Best window, 6 months | 40 m window, 1 month | 40 m window, 6 months |
|---|---|---|---|---|
| S1 VV | 149 m2 (winter) to 258 m2 (summer), about 1.0 to 2.7 MW | 86 to 114 m2, about 0.6 to 1.2 MW | 771 to 1,333 m2, 5.1 to 14.2 MW | 512 to 673 m2, 3.4 to 7.2 MW |
| S1 VH | 1,014 to 2,641 m2, 6.8 to 28 MW | 446 to 771 m2, 3.0 to 8.2 MW | 1,528 to 3,029 m2 | 1,014 to 1,528 m2 |
| S2 VNIR | 35,532 m2 summer; winter not reached | 3,029 m2 summer (20 to 32 MW); 27,027 m2 winter | not reached | 6,002 m2 summer |
| S2 NDVI (experimental) | 46,713 m2 summer; winter not reached | 3,473 m2 summer (23 to 37 MW); 40,741 m2 winter | not reached | 6,882 m2 summer |

With the weakest observed battery contrast (VV +1.9 in summer, +2.7 in winter), S1 VV needs 296 to 771 m2 with
six-month persistence (2.0 to 8.2 MW) and 673 to 13,638 m2 for one month.

**Ground-mounted PV, median contrast, 99 % quantile**

| Sensor and feature | Best window, 1 month | Best window, 6 months | 40 m window, 1 month | 40 m window, 6 months |
|---|---|---|---|---|
| S2 B11 / B08 | 1,752 m2 winter (0.15 to 0.25 MWp); 27,027 m2 summer (2.3 to 3.9 MWp) | 771 to 2,009 m2 (0.06 to 0.29 MWp) | 4,565 m2 winter; summer not reached | 2,304 to 4,565 m2 (0.19 to 0.65 MWp) |
| S2 B11 | 23,572 to 40,741 m2 | 1,162 to 3,029 m2 (0.10 to 0.43 MWp) | not reached | 3,029 to 6,882 m2 |
| S2 NDPI | 3,473 m2 winter; summer not reached | 1,014 to 2,304 m2 | 9,047 m2 winter | 3,029 to 5,235 m2 |
| S1 VV | 23,572 m2 winter (2.0 to 3.4 MWp); summer not reached | 13,638 m2 winter (1.1 to 1.9 MWp); summer not reached | not reached | not reached |
| S2 NDVI (experimental) | not reached | not reached at 99 %; 2,641 m2 at 95 % | not reached | not reached |

Statement of the prediction (50 % detection point; the 80 % point used by the analysis plan is the headline
table above):

1. **PV, Sentinel-2.** Parks of 1 MWp and larger (about 8,800 m2) are detectable through the SWIR features
   (B11 / B08, B11, NDPI) once the change persists for six months, in both seasons, with the 40 m feature window
   as long as the coordinate falls inside the park. Single-month detection of parks below about 3 to 4 MWp fails in
   summer. NDVI alone does not detect PV parks at the 99 % level at any size.
2. **PV, Sentinel-1.** Only parks above roughly 1 to 2 MWp, only in winter, with persistence and a window
   matched to the park (the 40 m window never reaches the 99 % level). Sentinel-1 is
   supporting evidence for PV, not a detector.
3. **Battery, Sentinel-1 VV.** Expected recall rises from about 1 MW (best window, median contrast) to about 3 to
   7 MW with the 40 m feature window and six-month persistence, and to about 5 to 14 MW for a single month. Sites
   with weak double bounce need 2 to 8 MW with persistence.
4. **Battery, Sentinel-2 alone.** Only above about 3,000 m2 (roughly 20 to 37 MW) in summer with persistence;
   winter detection needs about tenfold larger yards. Below that, the optical signal of a battery yard sits inside
   the crop-rotation noise.
5. The recall curve will be steeper in summer for S2 and flatter across seasons for S1.

Why the battery S1 number may be too optimistic (rule 13 check): the median pure contrast comes from 7 sites, most
between 1,800 and 23,000 m2, and assuming the same ninefold power gain for a yard of a few containers ignores the
orientation dependence of double bounce. The prediction is for site-level detection at a known location; a
1 % false-alarm rate per window and month is far too high for a national scan, which needs a much stricter
threshold. Phase 4 should read the 40 m window, six-month column as the central prediction and the best-window
column as a lower bound on the minimum size.

## 6. Cloud mask over battery yards and PV

Evidence before this task: R3 (`results/imagery/scl_bright_target_test_v1.md`): disk-against-ring ratios near 1
for PV, a possible small deficit for batteries in v0 that v1 did not reproduce.

Test run here (`src/bo/features/scl_did.py`, `results/features/scl_did_summary.csv`, `scl_did_sites.csv`). Each
site is its own control: clear observations inside the true OSM outline divided by those in a ring 100 to 300 m
from the outline, after construction divided by before (difference in differences). Result for the 6 battery sites
with both periods: SCL 2/4/5/6/7 rule 0.969 [0.935, 0.992] (every site below 1, range 0.892 to 0.995); SCL 4/5/6
1.006 [0.898, 1.200] (range 0.869 to 1.534; P007's before period has 35 % of months with no clear pixel inside the
outline, so its pre-construction surface was itself excluded); cloud probability 30 % on three Sentinel Hub
sites 0.943 [0.867, 1.028]. Q015, the largest yard (15,000 m2), loses 9 to 13 % under every rule. Months with no
clear pixel in the outline while the ring was clear: 0.6 % after construction under SCL 4/5/6. PV (2 sites):
0.95 to 0.97 under both SCL rules, 1.01 under cloud probability 30 %.

Reading: yards lose a few percent of clear observations, up to about 10 % at the largest site, but whole months
are almost never lost. For monthly medians that is harmless. The question that matters for features, whether the
retained observations over a yard are biased (for example haze passed as clear), is not answered by counts.

Recommendation for the clear-pixel rule: keep SCL 4/5/6 as primary (A5) with the alternative count stored. Do not
switch to a cloud-probability rule over bright targets (it loses most at Q015 and at warehouse roofs in R3). Use
`s2_valid_c` and `s2_nobs_c` as features so a model can learn from observation density, never fill it.

What would settle it: (a) the same difference in differences on at least 30 operating battery sites with true
outlines and at least 24 months before construction, using the December Sentinel-2 delivery and the round-1
labels' outlines, with an equivalence margin fixed in `docs/analysis_plan.md` beforehand (for example: harmless
if the lower bound exceeds 0.9); (b) per scene SCL class histograms inside outlines (Statistical API, as in R3)
to see which class takes the lost observations; (c) agreement with an independent mask (Cloud Score+ or
s2cloudless) inside outlines, which tests the bias question that counts cannot.

## 7. Co-location with PV parks

Observed: 605 of 1,199 registry battery sites (50.5 %) have a ground-mounted PV site within 300 m
(`results/features/colocation_registry.csv`, from `results/registry/registry_colocation_breakdown.csv`). In pilot v1
only 2 of 20 battery chips contain a registered PV site (`colocation_pilot_chips.csv`), so the pilot under-represents
the common case.

Consequences for features:
- A 640 m chip around a co-located battery contains PV pixels; the 150 to 300 m ring often lies on the park. Battery
  contrast `_ctr` then measures battery minus PV, not battery minus field, and the PV construction enters the ring.
- The two signatures oppose in SAR (battery VV up about ninefold per covered pixel, PV down by 1.5 to 2.5 dB), so any
  feature averaged over both partly cancels. Features must stay local (40 m centre, F1), and Phase 4 should test a
  smaller centre (20 m) for batteries.
- When the battery is added to an existing park, the year-over-year change at the battery coordinate is the battery
  alone; when both are built together, the timeline of the chip mixes two construction sequences.

Consequences for site classification:
- A chip label of "battery" or "PV" is ambiguous for half the battery sites. Labels and evaluation should be per
  object (outline), and technology should be assigned from local features (SAR brightening against SWIR step) and,
  in Track B, from container geometry.
- Phase 4 should report battery metrics separately for co-located and isolated sites, using the registry flag
  `colocated_pv` for stratified evaluation only, never as an input (it is not in the allow-list).
- Queue sampling (A62) already requires at least 25 % co-located positives; the pilot does not.

## 8. Items in `docs/research/` that look physically wrong or need care

- `pv_spectral_indices.md` fact 1: NDPI = (B11 - B08) / (B08 - B12) is not a normalised difference. Its denominator
  crosses zero where NIR equals SWIR2 (bare soil, PV mixtures), which makes it unbounded and sign-unstable at 10 to
  20 m. Kept because it is verified, guarded by F3; B11 / B08 carries the same physics stably.
- `pv_spectral_indices.md` "What this means": "1 MWp (roughly 1-2 ha, about 100-200 pixels)" disagrees with
  `site_footprints.md` (0.88 ha per MWp for 2024, 88 pixels). The 1 to 2 ha figure fits parks built before about 2015.
- `site_footprints.md` item 4 under "What this means" implies a near-constant mixed-pixel signal inside a park. True
  for the interior; the measured signal is weak in VNIR and NDVI (section 3), so the usable optical PV signal is
  in SWIR, not the visible.
- `imagery_chip_store.md`, A30: B11 and B12 are replicated from 20 m. Any index mixing a 10 m and a 20 m band (NDVI
  is fine; NDBI, MNDWI, NDPI, B11 / B08 are not) has 20 m effective resolution and a misaligned edge response.
- `sentinel1.md` "Physics facts" expects a VH drop when PV replaces grassland. Measured PV VH change is -0.29 to
  -0.34 in linear units (about -1.5 to -1.8 dB) on 3 sites, consistent but small.

## 9. Open problems

- PV contrasts rest on 3 parks and battery SWIR and VH contrasts on 4 yards in sections 3 and 5 (4 and 8 on
  `ee_r1`, section 10). The December Sentinel Hub delivery that a refit was to use was cancelled; the refit now runs
  on `ee_r1` (section 10) and can grow to the round-1 positives once their outlines exist.
- Registry coordinates can miss the site (Q044). Phase 4 needs either a search over offset windows within about 150 m
  or Track B outlines; this is a detector design decision and is not in the allow-list.
- Row orientation, tilt and look direction are not modelled for SAR (no source, `sentinel1.md` fact 30).
- No plastic-mulch, flooded-field or snow negatives exist yet; their checks are designed, not measured.
- `docs/analysis_plan.md` was frozen while this was written; section 5 uses its definition (recall 0.8, A82). Its
  forward selection (A73) draws on the relevance list at the end of section 2.

## 10. Platform rerun on the Earth Engine store (2026-11-19, review m1)

Criteria fixed before the rerun was inspected. A contrast change is **material** if the median over the paired
sites changes sign or differs from the Sentinel Hub / Planetary Computer value on the same sites by more than 25 %
of its magnitude. A minimum size change is material if the central prediction (`amin_q99_p80_r40_m2`, six-month
persistence, median contrast) changes by more than a factor 1.5 (about three steps of the area grid) or switches
between reached and not reached.

Run: `make signatures` (`bo.features.signatures`, both platforms). Sites: the 15 of 20 public signature sites that
are round-1 queue items have an `ee_r1` chip (matched by registry key, else within max(100 m, coordinate
uncertainty); list and folds in `results/features/signature_sites_fold0.csv`); the 5 others have none. S2 noise from
off-site pixels of those 15 chips, S1 noise from the 52 queue `random_negative` items outside fold 0 (assumption F11).
The Sentinel Hub and Planetary Computer rerun on today's stores reproduces the frozen tables: every central minimum
size is identical and battery VH contrast moves from 4.19 to 4.18 after the A42 masking
(`results/features/signatures_platform_comparison.csv`, columns `b_median_frozen`, `b_median_sh_pc`). All values below
are modelled.

Physics expectation. sigma0 and gamma0 differ by a factor that is fixed for one pixel and one orbit (the local
incidence angle), so it cancels in every after/before power ratio and every year-over-year difference used here. A
change is expected only where the processing differs (resampling, terrain correction, noise removal) or where the
orbit differs.

**Contrasts, same sites on both platforms** (`signatures_platform_comparison.csv`, paired columns). Rerun of
2026-11-19 after the Sentinel-1 refetch of two `ee_r1` stores onto the orbits of their Planetary Computer stores;
all 15 sites now use the same relative orbit and pass direction on both platforms (`s1_orbits.csv` in both
directories; `results/imagery/ee_vs_sh_orbit_check.csv`).

| Variable | Battery summer | Battery winter | PV summer | PV winter |
|---|---|---|---|---|
| VV, power ratio minus 1 | +8.22 to +8.69 (7 sites) | +8.12 to +8.19 | -0.33 to -0.33 (3) | -0.42 to -0.43 |
| VH, same | +4.18 to +3.96 (4) | +5.01 to +4.83 | -0.34 to -0.34 (3) | -0.29 to -0.27 |
| B11 / B08 | +0.11 to +0.11 (4) | +0.13 to +0.10 | +1.17 to +1.14 (3) | +1.69 to +1.80 |
| NDVI | -0.37 to -0.40 (7) | -0.24 to -0.27 | -0.21 to -0.21 (3) | -0.08 to -0.08 |

(gamma0 store to sigma0 store.) No SAR contrast and no PV contrast changes materially. Two battery optical medians
pass the 25 % criterion: VNIR winter (+0.037 to +0.018) and B11 winter (+0.013 to -0.021); both are near zero and the
median paired difference is only -0.004 and -0.009, so the medians of 4 to 7 sites are unstable rather than the
platform being different. Per site (`signatures_sh_pc_gamma0/` and `signatures_ee_r1_sigma0/contrast_at_best_psf.csv`):
on the 10 Sentinel Hub sites VV contrasts agree within about 6 %. On the three Planetary Computer battery sites,
now on the same orbit, `ee_r1` is higher: +1.85 to +3.11, +8.43 to +10.70 and +3.59 to +4.44 in summer (ratios 1.7,
1.27, 1.24). The first `ee_r1` run of the same day had used the ascending orbit 44 at the last two sites and gave
pure VV contrasts several times the Planetary Computer values; its tables were overwritten by this rerun, so no
number from that run is quoted here. That difference was an **orbit effect, not a convention effect**: with the orbit matched, the
residual is a factor 1.2 to 1.7, and it appears only against the Planetary Computer RTC product, not against
Sentinel Hub gamma0. Its cause (RTC processing, the v0 store, resampling) is not identified. The orbit dependence
of double bounce (`sentinel1.md` fact 30) remains unmeasured by a controlled comparison.

**Effective PSF.** On the same 10 sites the best VV width is 7.5 m on gamma0 and 10 m on sigma0 (mean R2 0.217 and
0.262); NDVI, VNIR, B11 and B11 / B08 keep their widths; VH goes from 15 to 12.5 m
(`results/features/signatures_platform_psf_paired.csv`). The Earth Engine product is smoother in VV, a processing
difference that the convention alone does not explain.

**Noise.** VV, 40 m window, six-month persistence, summer: robust SD 0.56 dB (gamma0, 45 pilot negatives) and 0.61 dB
(sigma0, 52 queue negatives), 99 % quantile +2.97 and +3.15 dB (`noise_yoy_window.csv`). Single-pixel VV spread:
2.27 and 2.09 dB against 1.74 dB from speckle alone (`s1_speckle_check.csv`). The negative sets differ, so this is
not a pure platform comparison.

**All `ee_r1` sites** (the sample Phase 4 sees; 8 battery and 4 PV sites with a usable fit,
`signatures_ee_r1_sigma0/contrast_summary.csv`): battery VV +6.56 summer and +6.44 winter (range +0.48 to +10.70),
VH +2.05 and +3.47 (from 4 to 8 sites, because the Planetary Computer stores had no VH), PV B11 / B08 +1.14 and +1.63.
The battery VV median is lower than on the old stores (+8.22, +8.12) because the `ee_r1` set adds one site with a
before window and a weak contrast (+0.48) to the 7 paired sites, which moves the median of an even count down.

**Minimum detectable size, central prediction** (`amin_q99_p80_r40_m2`, 40 m window, six-month persistence, median
contrast; `results/features/signatures_platform_minsize_comparison.csv`, frozen 2026-11-18 value to `ee_r1`):

| Technology and feature | Summer | Winter | Material |
|---|---|---|---|
| Battery S1 VV | 884 to 1,162 m2 (7.7 to 12.4 MW on `ee_r1`) | 587 to 1,014 m2 (6.8 to 10.8 MW) | winter yes (ratio 1.31, 1.73) |
| Battery S1 VH | 1,752 to 5,235 m2 | 1,162 to 2,304 m2 | yes (ratio 2.99, 1.98) |
| Battery S2 VNIR | 9,047 to 6,002 m2 | not reached on both | no (0.66) |
| Battery S2 NDVI | not reached to 7,891 m2 | not reached on both | yes (now reached) |
| PV S2 B11 / B08 | 5,235 to 3,473 m2 (0.29 to 0.50 MWp) | 2,641 to 2,009 m2 (0.17 to 0.29 MWp) | no (0.66, 0.76) |
| PV S2 B11 | 3,982 to 10,374 m2 | 13,638 to 15,637 m2 | yes in summer (2.61) |
| PV S2 NDPI | 6,882 to 2,641 m2 | 3,982 to 3,029 m2 | yes in summer (0.38) |
| PV S1 VV | not reached on both | not reached on both | no |

With the weakest battery site, VV is now never reached: on `ee_r1` one site gains a before window and shows a pure VV
contrast of only +0.48 summer and +0.41 winter (R2 0.02 and 0.01), against +1.9 and +2.7 for the weakest site on the
old stores. Best-window battery VV moves from 149 and 130 m2 to 296 and 258 m2 (wider VV PSF, lower median contrast).

Reading. The backscatter convention itself does not change contrasts on matched sites and orbits. The central
minimum sizes move for other reasons: on the Phase 4 store battery recall 0.8 is expected between about 7 and 12 MW
(S1 VV, against 4 to 9 MW in section 5), and PV still below 1 MWp (B11 / B08). The material changes come from a
different site set (one weak battery site gains a before window; VH and SWIR now available at the Planetary Computer
sites) and from the wider VV PSF of the Earth Engine product. The weak-site tail of the battery prediction is less
favourable than section 5 states. Section 5 is left unchanged as the dated prediction; Phase 4 should compare its
recall curves with both.

Fold 0 (review m8). Two signature sites lie in the locked test fold 0 (`results/features/signature_sites_fold0.csv`,
`in_fold0`). Fold-0 metrics should be reported with and without those two queue items.
