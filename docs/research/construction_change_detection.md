# Construction change detection from satellite time series
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Cluster F, note 1 of 2. Scope: utility-scale infrastructure only. Items marked VERIFIED were read on a page or PDF opened in this session. Several publisher pages (ScienceDirect, Nature) returned 403 or a login redirect, so their content is SECONDARY (taken from search-result summaries) and is marked as such.

## Key facts
| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | BFAST citation | Verbesselt, Hyndman, Newnham, Culvenor (2010) Remote Sens. Environ. 114(1):106-115, DOI 10.1016/j.rse.2009.08.014. Decomposes series into trend, seasonal, remainder and finds breaks in trend and season (tested on 16-day MODIS NDVI) | [1] | SECONDARY |
| 2 | BFAST Monitor citation | Verbesselt, Zeileis, Herold (2012) RSE 123:98-108, DOI 10.1016/j.rse.2012.02.022 | [2] | SECONDARY |
| 3 | `bfastmonitor()` model form | Default `response ~ trend + harmon` (linear trend plus harmonic season, harmonic order default 3). History period selected by ROC (default, reverse-ordered CUSUM), BP (Bai-Perron) or all. Default monitoring `type = "OLS-MOSUM"`, bandwidth `h` in (0,1), significance `level`. The page does not say how NA are handled | [3] | VERIFIED |
| 4 | bfast R package licence | GPL-2.0 (GitHub fork bfast2/bfast; fork includes bfastmonitor and stlplus-based NA handling) | [4] | VERIFIED |
| 5 | CCDC citation | Zhu & Woodcock (2014) RSE 144:152-171, DOI 10.1016/j.rse.2014.01.011. Change flagged when observed minus predicted exceeds threshold three consecutive times. Test: one Landsat scene, 519 images 1982-2011; reported change producer's accuracy 98%, user's 86%, temporal accuracy 80% | [5] | SECONDARY |
| 6 | COLD citation | Zhu, Zhang, Yang, Aljaddani, Cohen, Qiu, Zhou (2020) RSE 238:111116, DOI 10.1016/j.rse.2019.03.009 (online 13 Mar 2019) | [6] | VERIFIED |
| 7 | COLD model form | Harmonic regression per band: a0 + sum_{k=1..3}(a_k cos(2 pi k x/T) + b_k sin(2 pi k x/T)) + c1 x, T=365.25, x = Julian date; 4/6/8 coefficients depending on number of clear observations (12-17, 18-23, >=24); estimated on all clear observations, updated for every new observation; 7 Landsat bands | [6] | VERIFIED |
| 8 | COLD change rule and accuracy | Change probability 0.99 (chi-squared) with six consecutive anomalous observations and mean included angle < 45 degrees; model initialisation requires >=12 clear observations, >=1 year length, largest gap < 1 year. Omission error 27%, commission 28% (7200 reference plots, US) | [6] | VERIFIED |
| 9 | CCDC/COLD implementation | `pycold`: Apache-2.0, README says no longer maintained, recommends successor `pyxccd` (pyxccd licence not verified; GitHub URL I tried returned 404) | [7] | VERIFIED (pycold) / UNVERIFIED (pyxccd licence) |
| 10 | LandTrendr citation | Kennedy, Yang, Cohen (2010) RSE 114(12):2897-2910, DOI 10.1016/j.rse.2010.07.008. Temporal segmentation of yearly Landsat stacks into linear segments | [8] | SECONDARY |
| 11 | LandTrendr GEE implementation | eMapR/LT-GEE: repo text CC BY 4.0, code samples Apache 2.0; cite Kennedy et al. 2018 Remote Sens. 10:691 | [9] | VERIFIED |
| 12 | EWMACD citation | Brooks, Wynne, Thomas, Blinn, Coulston (2014) IEEE TGRS 52(6):3316-3332, DOI 10.1109/TGRS.2013.2272545: harmonic-regression residuals fed to Shewhart X-bar and EWMA control charts; 85% overall accuracy on loblolly pine stands, Alabama. Available as an Earth Engine algorithm (`ee.Algorithms.TemporalSegmentation.Ewmacd`) | [10] | SECONDARY |
| 13 | RADD (Sentinel-1 SAR) citation | Reiche et al. (2021) Environ. Res. Lett. 16(2):024005, DOI 10.1088/1748-9326/abd0a8 | [11] | VERIFIED |
| 14 | RADD method | Pixel-wise Gaussian mixture models from 2017-2018 VV/VH backscatter give forest/non-forest probabilities; alert triggered by a single new observation when non-forest probability > 0.75; Bayesian update of disturbance probability; unconfirmed alerts > 0.85, confirmed > 0.975 within 90 days; clusters < 0.2 ha removed | [11] | VERIFIED |
| 15 | RADD latency and accuracy | Disturbance typically occurred 6-12 days before the triggering image. With 12-day revisit 62% of alerts confirmed within 24 days, 88% within 48 days. 2019 validation: user's accuracy 97.6 +/- 4.8%, producer's accuracy 95.0 +/- 25.8% (>= 0.2 ha, confirmed); 83.5 +/- 37.5% including events < 0.2 ha | [11] | VERIFIED |
| 16 | RADD code and licence | Article gives no source code ("data available on reasonable request"); alerts public via Global Forest Watch and radd-alert.wur.nl; WUR page states CC BY 4.0 for the product | [11], [12] | VERIFIED (no code) / SECONDARY (CC BY) |
| 17 | SAR omnibus change test | Conradsen, Nielsen, Skriver (2016) IEEE TGRS 54(5):3007-3024, DOI 10.1109/TGRS.2015.2510160: likelihood-ratio omnibus test for equality of several complex covariance matrices plus factorisation locating the points of change. (Earlier two-image test: Conradsen et al. 2003 TGRS 41(1):4-19.) A Canty (2020) reference was NOT found | [13] | SECONDARY |
| 18 | REACTIV | Koeniguer et al., Remote Sens. 2020, 12(13):2089 (ONERA). HSV encoding: hue = time of change, saturation = temporal coefficient of variation, value = mean intensity. One implementation uses the Sentinel-1 number of looks L=4.9 (speckle reference mu = 0.2286) and takes the larger CV of VV and VH. Preprint arXiv 1904.11335 mentions construction sites among detectable long events. SNAP operator and Sentinel Hub script exist (licences not checked) | [14] | SECONDARY |
| 19 | SpaceNet 7 / MUDS | Van Etten et al. arXiv 2102.04420 (2021): > 40,000 km2, 24 monthly mosaics, > 100 geographies, > 11 million building polygons, 4.0 m imagery (Planet), unique building IDs across time; metric SCOT (change detection plus tracking) | [15] | VERIFIED |
| 20 | Dynamic World | Brown et al. (2022) Sci. Data 9:251, DOI 10.1038/s41597-022-01307-4; near-real-time 10 m Sentinel-2 per-image probabilities for 9 classes including built; GEE catalogue states CC BY 4.0 | [16] | SECONDARY |
| 21 | GHS-BUILT-S2 | Corbane et al. (2021) Neural Comput. Appl. 33(12), DOI 10.1007/s00521-020-05449-7: CNN, 5x5 pixel patches, ~1.45 M parameters, 10 m built-up probability for reference year 2018 (R2020A, listed as obsolete by JRC), validated on 277 sites. A single-epoch product, not a time-series dater | [17] | SECONDARY |
| 22 | Kruitwagen et al. 2021 | Nature 598:604-610, DOI 10.1038/s41586-021-03957-7; 68,661 verified facilities; Zenodo dataset 10.5281/zenodo.5005868 is CC BY 4.0, version 1.0.0, status at end of 2018. The repository states installation date "was inferred heuristically from the detection timeseries"; no date-accuracy figure found. The Zenodo record page does not list an installation-date field | [18], [19], [20] | VERIFIED (what is stated); accuracy OPEN |
| 23 | Kruitwagen code | Lkruitwagen/solar-pv-global-inventory, MIT | [19] | VERIFIED |
| 24 | Connecticut PV dating | "Back in time" (ScienceDirect S2666017225001282, 2025): U-Net on Sentinel-2 plus backward COLD on Landsat reconstructs installation year to 1985; mean dating error about 0.125 years (as reported in a search summary; page returned 403) | [21] | SECONDARY |
| 25 | Massachusetts PV dating | Object-based classification of Sentinel-2 monthly composites plus 20-year Landsat archive; overall classification accuracy 96%; 73% of construction years within one year of reference (search summary; page 403) | [22] | SECONDARY |
| 26 | India PV (Temporal Cluster Matching) | "An Artificial Intelligence Dataset for Solar Energy Locations in India", Sci. Data 2022, arXiv 2202.01340: first Sentinel-2 scene whose KL divergence to the pre-development distribution exceeds the median across the series is flagged as development; labels needed for one date only (search summary; Nature page redirected) | [23] | SECONDARY |
| 27 | TransitionZero Solar Asset Mapper | Construction dates inferred from changes in detection confidence across quarterly periods 2017-2024; upper bound only for plants first seen in 2017 (search summary; PDF was binary and not parsed) | [24] | SECONDARY |
| 28 | Global PV 2019-2022 | Sci. Data 2025: bi-monthly median Sentinel-2 composites, 6 x 16 spectral-temporal features, annual maps | [25] | SECONDARY |

## Details

### Algorithm family
All the optical algorithms share one structure: fit a seasonal-plus-trend model to a "stable" period, then flag observations that leave the prediction band.

* **BFAST / BFAST Monitor.** BFAST fits piecewise trend plus season and finds breaks offline. BFAST Monitor fits `trend + harmon` on a stable history (selected by ROC or BP) and monitors new data with an OLS-MOSUM process; it is a monitoring tool and assumes one break to find at the end of the series. Detection delay is governed by the MOSUM bandwidth `h` and the break magnitude (value not extracted). Licence GPL-2.0 for the R package (copyleft: relevant if we ship derived code in a public repository, which is acceptable under GPL if the repository is itself GPL-compatible; a Python re-implementation of the idea does not inherit it).
* **CCDC / COLD.** Per-pixel harmonic regression (3 harmonics plus trend, 8 coefficients) re-estimated for every new clear observation on all clear observations (the estimator is not stated in the pages read). COLD requires six consecutive anomalies, so the minimum detection delay is six clear observations. At Landsat density (8-16 days) that is a few months; for a monthly series that is six months, which is too slow for our task unless the rule is relaxed (the COLD paper reports that its parameters were tuned on Landsat with omission 27%, commission 28%).
* **LandTrendr.** Operates on one value per year (annual composite), fits piecewise linear segments. Temporal resolution is therefore yearly; it cannot date a phase to a month. Included for completeness.
* **EWMACD.** Residuals from a harmonic fit to a training period are tracked with an EWMA control chart; the smoothing parameter sets sensitivity and delay.
* **RADD (SAR).** Not harmonic: the backscatter distribution of the stable state is learned per pixel (Gaussian mixture), the first anomalous observation triggers an alert, and later observations confirm it. Delay: 6-12 days to trigger; 24-48 days to confirm. Designed for forest loss, not construction; the forest to non-forest state change is analogous to our "undisturbed to cleared" step.

### Construction-specific work
* SAR: construction produces a sustained rise in VV/VH backscatter (and falling coherence) as metal and concrete appear. REACTIV (coefficient of variation) and the omnibus test (Conradsen 2016; the dating factorisation gives the time of change) are the two documented, open approaches. Neither paper's quantitative results were extracted here (OPEN).
* Solar-park dating from time series has two patterns: (a) detect on Sentinel-2 then back-date with a Landsat COLD pass (Connecticut, Massachusetts), (b) change-point or distribution-shift test on the Sentinel-2 series itself (India Temporal Cluster Matching, TransitionZero). Reported accuracy is at annual resolution (73% within one year in Massachusetts; mean error 0.125 years in Connecticut). No source found reports month-level dating accuracy. Kruitwagen et al. date by heuristic on the detection time series with no accuracy figure located.
* Task framing: SpaceNet 7 poses construction as per-building appearance tracking in monthly 4 m mosaics with SCOT scoring; this is a useful framing for our four phases but its imagery is Planet, not Sentinel.
* Built-up products (Dynamic World built probability, GHS-BUILT-S2) classify imagery, so they can supply a per-month "built-up probability" feature to our model but do not date events themselves. Dynamic World's per-image probabilities are noisy under cloud and sensitive to bare soil.

### Seasonality and gaps
* Harmonic models (BFAST, CCDC, EWMACD) absorb the annual cycle but need enough observations per year; COLD switches to fewer coefficients when fewer than 18 clear observations exist and refuses to initialise with fewer than 12.
* Year-over-year differencing removes seasonality without a model but requires an undisturbed prior year (not available for sites already changing at series start) and doubles the noise variance.
* COLD handles clouds, shadow and snow upstream (Fmask, then Tmask), and drops non-consecutive outliers as transient events; this treats snow as missing, which is the right treatment for our winter gaps.
* Sentinel-1 is not cloud-limited, but wet or frozen ground and snow change backscatter; RADD normalises dry-season effects.
* A site-level monthly series of ~60 points (5 years) is far shorter than per-pixel Landsat series of hundreds of points; harmonic coefficients with k = 3 are over-parameterised. Use k = 1 harmonic or per-calendar-month baselines. This is our inference, not a sourced fact.

### Candidate methods summary (monthly, gappy, multi-sensor, site-level)
| Method | Pros | Cons for us |
|--------|------|-------------|
| BFAST Monitor (R, GPL-2.0) | Mature, statistical test, handles trend plus season | Needs stable history; single break at the end; R only; univariate |
| COLD / pyxccd | Multi-band, handles gaps, documented accuracy | Six consecutive anomalies, designed for dense Landsat; one transition (not a four-phase sequence) |
| LandTrendr | Simple, robust | Annual only |
| EWMACD | Cheap, EE implementation | Training period needed; univariate |
| RADD-style Bayesian pixel update | Works with SAR, probabilistic, low delay | Needs per-pixel baseline; not published as code |
| Omnibus / REACTIV (SAR) | Open, tuned for SAR statistics | Pixel-level; needs polarimetric/multilook statistics, not site-level features |
| Built-up probability (DW, GHS) | Free feature | Not a dater; classifier noise |
| BOCPD / HMM on site features (see bocpd.md) | Joint multi-sensor, explicit phase sequence, missing months handled by skipping the likelihood update | Self-implemented; priors need tuning; no published accuracy for this task |

## (verify) items from KICKOFF.md
None assigned to this note. See V13 in bocpd.md.

## What this means for our method
1. None of the established algorithms provides a four-phase decomposition; they declare one deviation from a stable model. The sequential model (HMM or BOCPD with phase labels) is our own composition, and its accuracy must be validated against reference sites ourselves.
2. Detection delay is design-driven: COLD six observations, RADD one plus Bayesian confirmation. With monthly data, treat reported dates as the first month at which evidence exceeds a threshold, and quote date uncertainty in months. Do not claim better than +/- 1 month.
3. Published dating accuracy is annual. A claim of month-level dating would be new and needs its own validation.
4. Treat snow/cloud months as missing, never as zeros.
5. Use Sentinel-1 backscatter as the primary change signal in winter; the optical series is gappy then.
6. Licences: BFAST (GPL-2.0) and scikit-survival (GPL-3.0, see bocpd.md) are copyleft; pycold (Apache-2.0), LT-GEE (Apache-2.0 code), ruptures (BSD-2) are permissive.

## Open questions
* Kruitwagen et al. supplementary method for installation date and any accuracy figure (Nature page not readable here).
* Month-level dating accuracy for any Sentinel-based solar or wind construction study.
* Wind-farm construction dating from time series: no source found in this session.
* Quantitative results of REACTIV and the omnibus test for construction.
* Canty's Sentinel-1 omnibus implementation and licence.
* pyxccd licence and maintenance.
* BFAST Monitor NA handling in the official `bfast` package; detection delay figures from Verbesselt 2012.
* Exact accuracy figures in the Connecticut/Massachusetts/India papers (read only via summaries).

## Sources
1. Verbesselt et al. 2010, RSE 114:106-115, via NASA MODIS publications record (search result), https://modarch.gsfc.nasa.gov/sci_team/pubs/abstract_new.php?id=00953 (not opened); DOI 10.1016/j.rse.2009.08.014. Retrieved 2026-11-12.
2. Verbesselt et al. 2012 RSE 123:98-108, DOI 10.1016/j.rse.2012.02.022; see https://bfast.r-forge.r-project.org/ (search result). Retrieved 2026-11-12.
3. bfastmonitor documentation, https://rdrr.io/cran/bfast/man/bfastmonitor.html. Retrieved 2026-11-12.
4. bfast2/bfast, https://github.com/bfast2/bfast. Retrieved 2026-11-12.
5. Zhu & Woodcock 2014, DOI 10.1016/j.rse.2014.01.011; https://open.bu.edu/items/e91f4cdc-0810-467b-b02e-51e36c91a3a3 (search result). Retrieved 2026-11-12.
6. Zhu et al. 2020 (COLD), https://gerslab.cahnr.uconn.edu/wp-content/uploads/sites/2514/2021/06/cold_2020_zhu.pdf (PDF read, pages 1-6). Retrieved 2026-11-12.
7. GERSL/pycold, https://github.com/GERSL/pycold. Retrieved 2026-11-12.
8. Kennedy et al. 2010, https://research.fs.usda.gov/treesearch/54160 (search result). Retrieved 2026-11-12.
9. eMapR/LT-GEE, https://github.com/eMapR/LT-GEE. Retrieved 2026-11-12.
10. Brooks et al. 2014, https://vtechworks.lib.vt.edu/items/ada8a6c3-0143-49aa-8231-e1a3f4b2a32b (search result). Retrieved 2026-11-12.
11. Reiche et al. 2021, https://iopscience.iop.org/article/10.1088/1748-9326/abd0a8. Retrieved 2026-11-12.
12. WUR RADD page, https://www.wur.nl/en/research/products-services/radd-forest-disturbance-alert (search result). Retrieved 2026-11-12.
13. Conradsen et al., search results at https://www2.imm.dtu.dk/pubdb/pubs/6827-full.html. Retrieved 2026-11-12.
14. REACTIV, https://arxiv.org/pdf/1904.11335.pdf and https://github.com/elisecolin/REACTIV (search results, not opened). Retrieved 2026-11-12.
15. Van Etten et al., https://arxiv.org/abs/2102.04420. Retrieved 2026-11-12.
16. Dynamic World, https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9184477/ (search result). Retrieved 2026-11-12.
17. GHS-BUILT-S2, https://human-settlement.emergency.copernicus.eu/ghs_bu_s2_2018.php (search result). Retrieved 2026-11-12.
18. Oxford ORA record for Kruitwagen et al., https://ora.ox.ac.uk/objects/uuid:0478449c-ccbb-4f52-afb3-d38ffef3a7fa. Retrieved 2026-11-12.
19. https://github.com/Lkruitwagen/solar-pv-global-inventory. Retrieved 2026-11-12.
20. Zenodo, https://zenodo.org/records/5005868. Retrieved 2026-11-12.
21. https://www.sciencedirect.com/science/article/pii/S2666017225001282 (403; summary via search). Retrieved 2026-11-12.
22. https://www.sciencedirect.com/science/article/abs/pii/S2352938523000198 (403; summary via search). Retrieved 2026-11-12.
23. https://www.nature.com/articles/s41597-022-01499-9 and https://arxiv.org/pdf/2202.01340 (search results). Retrieved 2026-11-12.
24. https://blog.transitionzero.org/hubfs/Data%20Products/TZ-SAM/tz-sam-scientific-methodology-Q12024.pdf (binary, not parsed; summary via search). Retrieved 2026-11-12.
25. https://www.nature.com/articles/s41597-025-04985-y (search result). Retrieved 2026-11-12.
