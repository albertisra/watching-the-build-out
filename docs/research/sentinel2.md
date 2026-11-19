# Sentinel-2 MSI: bands, constellation, L2A, SCL, cloud masks, geometry, licence
Status: complete (with open items)   Retrieved: 2026-11-12   Author: literature-scout

## Key facts
| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | S2A launch | 2015 (exact day not stated on the SentiWiki mission page; 2015-06-27 is the first item in the Planetary Computer STAC extent, which is a data date, not the launch date) | [1], [12] | VERIFIED (year only); exact day UNVERIFIED |
| 2 | S2B launch | 2017 (exact day not stated on the page I opened) | [1] | VERIFIED (year only); exact day UNVERIFIED |
| 3 | S2C launch | 5 September 2024 (Vega, last Vega flight) | [2] | VERIFIED |
| 4 | S2C replaced S2A in operation | 21 January 2025 | [1], [3] | VERIFIED |
| 5 | S2A after S2C commissioning | Not retired. Moved to an orbit 36 degrees from S2B and resumed observations 13 March 2025 ("extension campaign"). Neighbouring relative orbits are imaged about 10 min apart ("virtual extended swath"); revisit improved over Europe and tropical Africa/S. America. | [1], [3] | VERIFIED |
| 6 | S2A extension end | DQR of July 2026: "Sentinel-2A extension campaign prolonged until the end of 2026" (CDSE page had said 3-satellite phase until 13 Mar 2026, so it was extended) | [4], [3] | VERIFIED (planned end; not a guarantee) |
| 7 | Operational units today (2026-11-12) | S2B and S2C nominal pair; S2A in extension campaign through end of 2026 (as planned in July 2026). No source newer than July 2026 was found on S2A. | [1], [4] | VERIFIED for plan; current actual status of S2A OPEN |
| 8 | S2D | "will succeed Sentinel-2B"; no launch date on the ESA page; mission then continues with Sentinel-2 Next Generation (continuity beyond 2035). A search snippet from a non-ESA site claims 2028 on Vega-C. | [1], search | Plan VERIFIED; date 2028 UNVERIFIED |
| 9 | Revisit | One satellite 10 days; nominal two-satellite constellation 5 days (equator). Germany-specific revisit not stated in any ESA page I opened (higher latitude and orbit overlap give more frequent coverage; not quantified here). | [1] | VERIFIED (equatorial/nominal values) |
| 10 | Revisit by period (derived from #1-#5) | 2015-06 to 2017-03: S2A only, 10 d. 2017-03 to 2024-12: S2A+S2B, 5 d. 2025-01-21 to 2025-03: S2B+S2C, 5 d. From 2025-03-13: S2B+S2C nominal plus S2A extension (up to 3 satellites over Europe). | derived from [1],[3] | SECONDARY (our arithmetic on VERIFIED dates) |
| 11 | L2A systematic availability | L2Ap (pilot, baseline 02.07) from 28 Mar 2017; L2A operational from mid-March 2018 starting with Euro-Mediterranean coverage; global from 13 Dec 2018 | [5] | VERIFIED |
| 12 | Collection-1 | Reprocessing of all data from S2A launch (2015) to 13 Dec 2023 into a consistent baseline (PB 05.10 deployed for nominal sensing 13 Dec 2023); CDSE said the Collection-1 download was "nearly finished" and L1C+L2A up to 13 Dec 2023 will be available in baseline 5.0 or later. Whether L2A for 2015-2016 is now complete on each platform was not checked. | [6], [7] | VERIFIED (scope); completeness OPEN |
| 13 | Processing baseline 04.00 | Operational 25 January 2022 (SentiWiki states 24 Jan in one section and 25 Jan in another; ESA's 2021 announcement planned deployment for 26 Oct 2021, which did not happen on that date) | [6], [5], [8] | VERIFIED (25 Jan 2022, with the inconsistency noted) |
| 14 | L2A reflectance formula from PB 04.00 | SR = (DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE; DN=0 is NO_DATA; offset reported in General_Info/Product_Image_Characteristics of the metadata | [5], [8] | VERIFIED |
| 15 | Offset value | -1000 DN (= -0.1 reflectance at quantification 10000). CDSE support confirmed declared scale/offset 0.0001 / -0.1 on a STAC test item; Google Earth Engine states DN range is "shifted by 1000" for baseline >= 04.00. ESA's announcement does not state the number in the text I read. | [9], [10] | VERIFIED via CDSE support + GEE; ESA text itself does not quote the number |
| 16 | SCL native resolution | 20 m; also delivered at 60 m (mode resampling); not delivered at 10 m | [6], [5] | VERIFIED |
| 17 | Cloud/shadow/snow dilation | From PB 04.00 (Sen2Cor 2.10+): +80 m cloud, +40 m cloud shadow, +20 m snow; over urban areas only large clouds (>1000 px at 20 m) are dilated | [6] | VERIFIED |
| 18 | Geolocation requirements (L1) | Absolute 20 m (2 sigma) without GCPs, 12.5 m (2 sigma) with GCPs; multi-temporal registration <= 0.3 pixel (2 sigma); multi-spectral <= 0.3 of coarser band sampling (3 sigma) | [1] | VERIFIED (requirements, not measurements) |
| 19 | Global Reference Image (GRI) | Global absolute geolocation accuracy "better than 6 m"; geometric refinement against the GRI started over Euro-Africa 30 Mar 2021 and worldwide 23 Aug 2021; Collection-1 reprocessing "in particular improving ... the products geometric performance" (no numbers) | [6] | VERIFIED |
| 20 | Measured geometry (ESA presentation, 2022, via search result, not opened) | absolute 11 m to under 7 m (CE95); multi-temporal co-registration 9 m to under 5 m (CE95) after refinement | search snippet of earth.esa.int LPS 2022 (Enache) | SECONDARY (snippet only; PDF returned 404 when fetched) |
| 21 | Cloud Score+ | Google dataset COPERNICUS-based, bands cs and cs_cdf, 10 m, 0-1; licence CC-BY-4.0; 2015-06-27 to present on Earth Engine; recommended thresholds 0.50-0.65 (example 0.60) | [11] | VERIFIED (Earth Engine page) |
| 22 | s2cloudless | Pixel-based LightGBM detector on L1C B01,B02,B04,B05,B08,B8A,B09,B10,B11,B12 (divide by 10000, apply harmonisation for PB>=04.00); README licence CC BY-SA 4.0; Sentinel Hub offers precomputed masks | [13] | VERIFIED |
| 23 | s2cloudless on CDSE | Not available on CDSE as of the forum thread; CDSE support (11 Jul 2025) said bringing it from Sentinel Hub "will be considered for the future roadmap" | [14] | VERIFIED (as of Jul 2025) |
| 24 | Copernicus data licence | Free, full and open; attribution "Copernicus Sentinel data [Year]"; modified: "Contains modified Copernicus Sentinel data [Year]" | [15] | VERIFIED |

## Band table (SentiWiki, equivalent wavelength = barycentre of spectral response; bandwidth in nm) [1]
| Band | Res. | S2A nm / BW | S2B nm / BW | S2C nm / BW |
|---|---|---|---|---|
| B1 | 60 m | 442.7 / 21 | 442.3 / 20 | 444.2 / 20 |
| B2 | 10 m | 492.7 / 65 | 492.3 / 65 | 489.1 / 65 |
| B3 | 10 m | 559.9 / 35 | 559.0 / 35 | 560.6 / 35 |
| B4 | 10 m | 664.6 / 31 | 664.9 / 31 | 666.5 / 31 |
| B5 | 20 m | 704.1 / 15 | 703.8 / 14 | 707.1 / 16 |
| B6 | 20 m | 740.5 / 13 | 739.1 / 14 | 741.1 / 16 |
| B7 | 20 m | 782.8 / 19 | 779.7 / 20 | 784.7 / 20 |
| B8 | 10 m | 832.8 / 118 | 832.9 / 115 | 834.6 / 114 |
| B8A | 20 m | 864.7 / 20 | 864.0 / 21 | 865.6 / 20 |
| B9 | 60 m | 945.1 / 20 | 943.2 / 19 | 947.2 / 20 |
| B10 | 60 m | 1373.5 / 29 | 1376.9 / 29 | 1372.2 / 33 |
| B11 | 20 m | 1613.7 / 89 | 1610.4 / 93 | 1612.0 / 90 |
| B12 | 20 m | 2202.4 / 180 | 2185.7 / 181 | 2191.3 / 181 |

Status: VERIFIED [1]. Differences between units are small (largest: B2 centre 489.1 nm on S2C versus about 492.5 nm on A/B; B12 2191 versus 2202/2186). L2A folders contain B02/B03/B04/B08 at 10 m; B01-B07, B8A, B11, B12, SCL at 20 m; 60 m adds B09 (B10 omitted) [5]. Since PB 04.00 B01 also exists at 20 m [8].

## Details

### SCL classes (L2A scene classification) [6], [5], [16]
| Code | Name (SentiWiki) | Earth Engine label |
|---|---|---|
| 0 | NO_DATA | No data |
| 1 | SATURATED_OR_DEFECTIVE | Saturated or defective |
| 2 | CAST_SHADOWS (named DARK_FEATURES before; renamed in PB 05.11; "topographic and casted shadows" from PB 04.00) | Dark area pixels |
| 3 | CLOUD_SHADOWS | Cloud shadows |
| 4 | VEGETATION | Vegetation |
| 5 | NOT_VEGETATED | Bare soils |
| 6 | WATER | Water |
| 7 | UNCLASSIFIED | Clouds low probability / unclassified |
| 8 | CLOUD_MEDIUM_PROBABILITY | Clouds medium probability |
| 9 | CLOUD_HIGH_PROBABILITY | Clouds high probability |
| 10 | THIN_CIRRUS | Cirrus |
| 11 | SNOW or ICE | Snow / ice |

From PB 04.00 "dark features" were moved into class 7 (UNCLASSIFIED) and class 2 became topographic/cast shadows [8]. Since PB 05.09 (6 Dec 2022) pixels with missing or degraded source packets are set to SCL=1 [5]. CDSE's own quarterly mosaic treats SCL 1, 3, 7, 8, 9, 10 as invalid (so 2, 4, 5, 6, 11 are kept) [7]: a blacklist, not a {4,5,6} whitelist.

### Known SCL weaknesses (documented)
- ESA PB 04.00 announcement (29 Sep 2021) lists as improvements: "Improved cloud detection over coastal bright targets such as buildings and bright sand, reducing false detections"; B08/B8A parallax "to reduce false cloud detections over bright urban targets and snow in high clouds" [8]. SentiWiki: parallax is used to "remove some of bright surfaces/buildings falsely detected as clouds from the final cloud mask" (flagged by very low pixel displacement) [6]. So ESA itself acknowledges bright man-made surfaces were falsely detected as cloud before PB 04.00, and mitigates it only partly (the parallax test needs a spectral-band displacement contrast, which a flat low-lying bright roof may not always give; this inference is ours).
- Snow on mountains "is as bright as opaque clouds in bands B1 and B10"; thin cirrus "is just a probability and not a certainty" [6].
- ESA L2A Data Quality Report, July 2026 (issue 99.0, 9 Jul 2026): cloud versus clear (clear = classes 4, 5, 6 and also 2 and 11; cloud = 8, 9, 10) validated on fixed and randomised sites. Potsdam T33UUU (Germany): balanced overall accuracy 95 %, clear producer 97 %, cloud producer 91 %. Randomised Europe sites: balanced OA 94 %, clear commission error 8 %, cloud producer accuracy 89 %. Worldwide balanced OA ranges 81-98 % (lowest North America 81 %, clear commission error 29 %). Snow cover (Yakutsk winter): 79 %. "Misclassification of cloud pixels to clear pixels is often found in snow-covered scenes ... and desert scenes". Cloud-shadow pixels misclassified as clear: 3 % (Europe randomised), up to 11 % (Australia), 10 % (Yakutsk winter). Cloud-shadow pixels misclassified as clear on snow/sand are "due to their brighter reflectance" [4]. The DQR uses clear-versus-cloud error matrices only; it does not report errors for specific man-made land cover.
- DQR editions 2022-2023, via a search summary (not opened): known limitations include "over-detection of clouds over bright targets, under-detection of semi-transparent clouds or cloud edges, cloud pixels misclassified as snow in shaded cloud parts, and dark areas misclassified as cloud shadows" [search].
- Louis et al. (Remote Sensing 2021, via search summary): Sen2Cor may misclassify clear land as topographic shadow; agreement across three algorithms 89-92 % overall but 45-62 % in disagreement areas. Not opened (HTTP 403).
- CDSE forum (21 Mar - 11 Jul 2025): users report SCL does not reliably classify clouds and shadows (e.g. Belgium); CDSE support: "the classification algorithm issue", no browser bug [14].

### PV modules, metal roofs, white containers: what the evidence says
No source I opened mentions solar panels, PV parks, metal roofs or containers being flagged as cloud, saturated or unclassified. The evidence is indirect:
1. ESA documents false cloud detection over bright buildings/sand before PB 04.00 and partial mitigation after [8], [6]. Brightness-driven false cloud is therefore a documented failure class; white container yards and light metal roofs are plausible members (inference, not demonstrated).
2. PB 04.00 moved "dark features" to class 7 UNCLASSIFIED [8]. PV modules are optically dark in much of the spectrum and could land in class 7 or class 2 (inference, not demonstrated). A {4,5,6}-only composite would drop those observations.
3. Saturation (class 1) needs very high reflectance; specular glint from panels is conceivable but undocumented.
4. The DQR validation sets contain no PV-specific class (one DLR validation deck listed a "solar panels" scene at Dunhuang, China, but the snippet gave no results) [search].
Verdict on V5c: NOT PROVEN SAFE. See table below.

### Alternative cloud masks
- Cloud Score+ [11]: ML quality score for L1C/L2A, 10 m, `cs` (instantaneous similarity to a clear reference) and `cs_cdf` (likelihood clear given the location's score distribution over time); CC-BY-4.0; thresholds 0.5-0.65. Documented only on Earth Engine; the page mentions no other host. Reference: Pasquarella et al., CVPR Workshops 2023, doi:10.1109/CVPRW59228.2023.00206. Because it is built on the harmonised L1C collection and designed to remove cloud, haze and cirrus shadows, it is not driven by land-cover classes, but whether it also flags bright PV/roof surfaces was not found.
- s2cloudless [13]: needs L1C (10 bands) not L2A; CC BY-SA 4.0 on the README; runnable offline with `pip install s2cloudless`; harmonisation offset must be applied for PB >= 04.00. A CDSE user found it "recognizes clouds better than SCL in some situations" (forum opinion, April 2025) [14].
- Fmask: no primary source opened. Louis et al. 2021 (secondary snippet) says Fmask dilates masks and so may overestimate cloud cover [search]. UNVERIFIED beyond that.
- MSK_CLDPRB / MSK_SNWPRB: SentiWiki states cloud and snow probability maps are provided at 20 m and 60 m from L2A processing and are quality indicators [5], [6]. The exact file names were not stated on the pages I opened, so the names MSK_CLDPRB / MSK_SNWPRB are as given in the brief (UNVERIFIED by me). They are per-pixel probabilities, so a threshold can be tuned, unlike the hard SCL classes.

### Baseline 04.00 offset and platform handling
- Cause: shifted dynamic range so negative reflectances are no longer clipped to zero [8]. It applies to products by PROCESSING_BASELINE, not by acquisition date, which matters for Collection-1 reprocessed older scenes (stated in an arXiv best-practice paper found via search; secondary).
- CDSE STAC / S3 files: values are stored raw; the offset is declared as scale 0.0001, offset -0.1 in the STAC metadata (CDSE support, Aug 2026). Omitting the offset in your own pipeline is "numerically equivalent to what harmonizeValues does" for baseline >= 04.00 scenes; CDSE support recommends keeping the offset in the pipeline [9].
- Sentinel Hub / Copernicus Browser: `harmonizeValues` defaults to true, so values are shifted back to the pre-04.00 convention (stated by a forum user, not by ESA staff; the "Harmonize Values" docs section was not opened) [9]. Do not apply the offset a second time on harmonised output.
- Google Earth Engine: `COPERNICUS/S2_SR_HARMONIZED` shifts newer scenes into the old range; the unharmonised `COPERNICUS/S2_SR` does not. L2A availability on Earth Engine: 2017-03-28 to 2026-11-11; the page lists only S2A and S2B and does not mention S2C [10].
- Planetary Computer `sentinel-2-l2a`: STAC collection JSON shows temporal extent starting 2015-06-27, licence "proprietary" linking to Copernicus terms, Sen2Cor L2A as COGs, SCL asset; the summary I received shows no raster:bands scale/offset and no S2C in the platform list. Microsoft's example notebook "baseline-change" provides a `harmonize_to_old` function (known only from a search summary; notebook fetch returned HTTP 429) [12]. Whether PC stores raw (unharmonised) values with a declared offset was not verified.

### Geometry and false change at site edges
Requirement: multi-temporal registration <= 0.3 pixel at 2 sigma (= 3 m at 10 m) [1]. Measured performance (secondary): about 5 m CE95 multi-temporal after GRI refinement, about 7 m absolute CE95 [search snippet]. A 5 m shift is half a pixel at 10 m, enough to move a bright object's edge by one pixel in some scenes. The GRI refinement applies only from 30 Mar 2021 (Euro-Africa) in operational data; pre-2021 data are only equivalent after Collection-1 reprocessing [6]. 2017-2021 data therefore should be taken from Collection-1 products (baseline >= 05.00) to have consistent geometry; check PROCESSING_BASELINE per scene.

### Copernicus Sentinel data licence (EC legal notice) [15]
Quoted: "free, full and open access to Copernicus Sentinel Data ... without any express or implied warranty"; permitted: "reproduction; distribution; communication to the public; adaptation, modification and combination with other data and information". "Where the user communicates to the public or distributes Copernicus Sentinel Data ... he/she shall inform the recipients of the source ... by using the following notice: 'Copernicus Sentinel data [Year]'". "Where ... adapted or modified, the user shall provide the following notice: 'Contains modified Copernicus Sentinel data [Year]'". Users renounce damage claims against the EU and providers. Use for our project: composites, change maps and derived rasters count as modified; any public GitHub repo, figure or table based on them should carry "Contains modified Copernicus Sentinel data 2017-2026" (year(s) of the sensing). Raw redistribution needs "Copernicus Sentinel data [Year]". The notice's PDF version bears no date in its text.

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|----|---------------------|---------|---------|--------|
| V5b (S2 part) | "Sentinel-1 and Sentinel-2 imagery ... covers Germany every few days, and goes back to 2015 to 2017" | S2 L1C data from mid-2015 (S2A launched 2015; PC extent starts 2015-06-27); S2B from 2017. L2A: pilot from 28 Mar 2017, operational Europe mid-March 2018, global 13 Dec 2018; Collection-1 reprocessing makes L1C and L2A from 2015 available (to 13 Dec 2023) but platform completeness unchecked; Earth Engine L2A starts 2017-03-28. Revisit: 10 d (2015-2017), 5 d with two satellites, 3 satellites over Europe in 2025-2026. "Every few days" holds for S2 only after mid-2017 and is limited by cloud. | CORRECTED (dates refined; "every few days" only from 2017) | [1], [5], [6], [7], [10], [12] |
| V5c | Monthly S2 composites from SCL classes 4, 5 and 6 only is safe for PV modules and bright roofs | Not supported by evidence. SCL 7 (unclassified, incl. former dark features), 2 (cast shadows), 1 (saturated) and 8-10 (false cloud over bright targets) are all plausible destinations for PV arrays, white containers and metal roofs; ESA documents bright-target false cloud before PB 04.00 and only partial mitigation. No PV-specific validation exists in ESA reports. CDSE's own mosaic excludes only 1,3,7,8,9,10. | OPEN (treat as risky; test empirically) | [4], [6], [7], [8] |

## What this means for our method
1. Do not whitelist SCL 4/5/6. Exclude clouds by blacklist (3, 8, 9, 10, 1, and 0), keep 2 and 7 candidate-valid, and add a second independent mask (Cloud Score+ cs_cdf >= 0.6 where Earth Engine is used, or s2cloudless probability where L1C is available), combining as "valid if not flagged by either mask". Report per-composite valid pixel counts.
2. Run a calibration test before any compositing: sample known ground-mounted PV and BESS sites (MaStR sites with known construction dates) plus bright roofs and compute the monthly frequency of each SCL class over those footprints versus the neighbouring field. If SCL 7/2/8/9 occurs above background, do not rely on SCL there.
3. Always harmonise baseline >= 04.00 scenes (subtract 1000 DN or use SR_HARMONIZED or Sentinel Hub default) before computing indices or differences; otherwise the 25 Jan 2022 step creates a +0.1 reflectance jump that looks like construction. Check per scene via PROCESSING_BASELINE, not by date. Avoid double application.
4. Use Collection-1 (baseline >= 05.xx) for 2017-2021 to get GRI-refined geometry; otherwise expect up to about 9 m multi-temporal error. Add a 1-pixel buffer or use object-level statistics at site edges rather than per-pixel differences.
5. Credit line: "Contains modified Copernicus Sentinel data [years]".
6. S2C differs slightly in B2 (489 nm) and B12; for 2025 onward mixing S2B, S2C, S2A is acceptable but check for sensor-dependent offsets in the time series.

## Open questions
- Exact launch days of S2A/S2B/S2D (not on pages opened); S2D launch date.
- Actual status of S2A after 2026 (extension planned to end 2026).
- Does Planetary Computer's `sentinel-2-l2a` store raw DN with a declared offset, and does it contain S2C scenes and Collection-1 reprocessed 2015-2018 scenes?
- Sentinel Hub "Harmonize Values" official documentation (only forum statement seen).
- Whether Cloud Score+ is hosted outside Earth Engine, and its behaviour over PV arrays.
- Fmask primary source; file names and thresholds of MSK_CLDPRB/MSK_SNWPRB.
- Germany-specific S2 revisit numbers (orbit overlap).
- Measured multi-temporal registration numbers from a primary ESA document (secondary snippet only).

## Sources
1. S2 Mission, SentiWiki, ESA/Copernicus. https://sentiwiki.copernicus.eu/web/s2-mission . Retrieved 2026-11-12 (page date not shown).
2. Sentinel-2C joins the Copernicus family in orbit, ESA press release, 5 Sep 2024. https://esa.int/Newsroom/Press_Releases/Sentinel-2C_joins_the_Copernicus_family_in_orbit . Retrieved 2026-11-12.
3. Sentinel-2 mission page, Copernicus Data Space Ecosystem documentation. https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html . Retrieved 2026-11-12.
4. Data Quality Report Sentinel-2 MSI L2A, July 2026, OMPC.CS.DQR.002.06-2026, issue 99.0, 9 Jul 2026 (SentiWiki attachment, opened as PDF pp. 1-8, 29-36). https://sentiwiki.copernicus.eu/__attachments/a_4499f8894ee8feb539a25c13cf4f4d5c800a2eaa578df537bd99772b400eb367/OMPC.CS.DQR.002.06-2026%20-%20i99r0%20-%20MSI%20L2A%20DQR%20July%202026.pdf . Retrieved 2026-11-12.
5. S2 Products, SentiWiki. https://sentiwiki.copernicus.eu/web/s2-products . Retrieved 2026-11-12.
6. S2 Processing, SentiWiki. https://sentiwiki.copernicus.eu/web/s2-processing . Retrieved 2026-11-12.
7. Same as 3 (Collection-1 and quarterly mosaic notes).
8. Copernicus Sentinel-2: Major Products Upgrade Upcoming, ESA/Copernicus, 29 Sep 2021. https://sentinels.copernicus.eu/-/copernicus-sentinel-2-major-products-upgrade-upcoming . Retrieved 2026-11-12.
9. Forum thread "Sentinel-2 baseline >=04.00 offset: CSDE STAC derived NDVI doesn't match Copernicus Browser NDVI", CDSE forum, Aug 2026. https://forum.dataspace.copernicus.eu/t/sentinel-2-baseline-04-00-offset-csde-stac-derived-ndvi-doesnt-match-copernicus-browser-ndvi/5417 . Retrieved 2026-11-12. (Support Team reply is official; first reply is a user.)
10. COPERNICUS/S2_SR_HARMONIZED, Google Earth Engine catalog. https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED . Retrieved 2026-11-12.
11. Cloud Score+ S2_HARMONIZED V1, Google Earth Engine catalog. https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED . Retrieved 2026-11-12.
12. sentinel-2-l2a STAC collection, Microsoft Planetary Computer. https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a . Retrieved 2026-11-12. Microsoft example notebook baseline-change.ipynb known only via search summary (fetch 429).
13. s2cloudless README, Sentinel Hub (GitHub). https://github.com/sentinel-hub/sentinel2-cloud-detector . Retrieved 2026-11-12.
14. Forum thread "Incorrect classification from SCL", CDSE forum, Mar-Jul 2025. https://forum.dataspace.copernicus.eu/t/incorrect-classification-from-scl/3455 . Retrieved 2026-11-12.
15. Legal notice on the use of Copernicus Sentinel Data and Service Information, European Commission DG GROW (PDF, undated). https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice . Retrieved 2026-11-12.
16. SCL labels also checked against Earth Engine page [10].
Search-only (not opened; cited as SECONDARY): ESA Living Planet Symposium 2022 presentation Enache (https://earth.esa.int/living-planet-symposium-2022-presentations/23.05.Monday/Santiago_del_Chile/1330-1510/05_Enache.pdf, 404 on fetch); Louis et al., Remote Sensing 2021, 13(1), 137 (https://mdpi.com/2072-4292/13/1/137, 403 on fetch); ESA L2A DQR 2022/2023 editions (sentinels.copernicus.eu documents); DLR Sen2Cor validation deck (elib.dlr.de/126367, 404).
