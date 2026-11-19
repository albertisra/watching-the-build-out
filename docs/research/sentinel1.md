# Sentinel-1 SAR: GRD/IW characteristics, orbit, constellation timeline, data availability, analysis-ready variants
Status: complete (with open items)   Retrieved: 2026-11-12   Author: literature-scout

## Key facts
| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | S1A launch | 3 April 2014 (first radar images 12 April 2014) | [1], [2] | VERIFIED |
| 2 | S1B launch | 25 April 2016 | [1] | VERIFIED |
| 3 | S1B anomaly | 23 December 2021: power-supply anomaly (platform supply to instrument electronics) stopped radar data delivery | [1], [3] | VERIFIED |
| 4 | S1B end of mission | Announced 3 August 2022 by ESA and the EC. (CDSE's product page says S1B "ended operations in July 2022"; the ESA article is more authoritative.) | [3], [1], [4] | VERIFIED; CDSE wording inconsistent |
| 5 | S1C launch | 5 December 2024 | [1] | VERIFIED |
| 6 | S1C data to users | First product set on CDSE announced 30 Jan 2025 (search summary); CDSE "initial access ... starting 26th March" 2025 (announcement dated 25 Mar 2025, observation scenario "close to the nominal one"); SentiWiki: "fully operational since early May 2025" | [1], [5], search | VERIFIED (26 Mar, May 2025); 30 Jan item SECONDARY |
| 7 | S1D launch | 4 November 2025 | [1] | VERIFIED |
| 8 | S1D user data / status | User data opened 17 April 2026 on CDSE; three-satellite phase 17 Apr to mid-June 2026 (S1A, S1C, S1D); SentiWiki: expected fully operational from mid-April 2026 replicating the S1C scenario; a search summary says "fully operational on 1 May 2026" | [1], [6], [7] | VERIFIED (17 Apr); 1 May SECONDARY |
| 9 | Orbit reconfiguration 2026 | 9-23 June: S1C manoeuvred from 1-day offset to 6-day offset from S1D (S1C operations suspended; coverage by S1A and S1D); 24 June: S1C resumes nominal ops, S1D adopts S1A's observation scenario; 6-day repeat restored 24 June | [7], [8] | VERIFIED |
| 10 | S1A end | Operations ended 29 June 2026 (planned date; last acquisitions that day); CDSE news dated 30 June 2026 announces "officially concluded its operations today, 30 June 2026". Final constellation S1C+S1D. | [7], [9], [1] | VERIFIED (29 vs 30 June differ by sources; ESA operations date is 29 June) |
| 11 | Observation periods (SentiWiki) | S1A only Apr 2014-Apr 2016; S1A+S1B May 2016-Dec 2021; S1A alone with adjusted scenario Sep 2022-Apr 2025; S1A+S1C May 2025-Jun 2026; S1C+S1D from end June 2026 | [1] | VERIFIED (as listed; Jan-Aug 2022 not listed but S1B was already lost) |
| 12 | Repeat cycle | One satellite: 12-day exact repeat, 175 orbits per cycle; two satellites: 6-day exact repeat; C/D configuration shifts the 6-day pattern by one day relative to A/B | [1], [7] | VERIFIED |
| 13 | Revisit over Europe with one satellite | No ESA page I opened states a Europe-specific figure. SentiWiki: one satellite maps the world in IW "once every 12 days"; ESA's Sentinel-1B end note gives no figure for S1A alone; CDSE (2025): "12-day repeat cycle under the one-satellite scenario, and some regions are not currently observed". An ESA presentation (not opened) is quoted as saying the S1A plan was adjusted only outside Europe because "in Europe all potential Sentinel-1A passes are already part of the standard plan". | [1], [3], [4], search | 12 d VERIFIED for orbit repeat; Europe statement SECONDARY |
| 14 | IW mode | 250 km swath, 3 sub-swaths (TOPSAR), single-look 5 x 20 m, incidence 29.1 to 46.0 degrees, polarisation HH+HV or VV+VH (dual) or HH/VV single; "primary mode over land" | [1] | VERIFIED |
| 15 | IW GRD HR product | pixel spacing 10 x 10 m; resolution 20.4x22.5 / 20.3x22.6 / 20.5x22.6 m (IW1/2/3, range x azimuth); looks 5 x 1; ENL 4.4/4.3/4.3; radiometric resolution 1.7 dB; 16-bit magnitude detected; absolute location accuracy (NRT) 7 m | [10] | VERIFIED |
| 16 | IW GRD MR product | 40 x 40 m, resolution about 88 x 90 m, looks 22 x 5, ENL about 81-84, 0.4-0.5 dB | [10] | VERIFIED |
| 17 | NESZ IW | Maximum -22 dB (specification, SentiWiki Table 5); actual noise vectors are annotated per product and vary with incidence angle | [1], [11] | VERIFIED (spec) |
| 18 | Orbit | Altitude 693 km; ascending-node local time 18:00; descending pass therefore about 06:00 (inference; an ESA handbook version reportedly labels 18:00 as descending, so the label is not fully consistent across ESA pages) | [1], search | Ascending 18:00 VERIFIED; descending 06:00 UNVERIFIED |
| 19 | GRD archive start | CDSE: GRD (packed/unpacked, SAFE+COG) from Oct 2014 (spatial extent "World"); Planetary Computer sentinel-1-grd and -rtc STAC temporal extents start 2014-10-10T00:28:21Z. IPF 002.36 deployed 1 Oct 2014. | [4], [12], [13], [14] | VERIFIED (dates); Germany-specific first systematic IW date OPEN |
| 20 | Thermal noise handling | The IPF does not subtract noise; it annotates noise vectors; users de-noise GRD by subtracting the noise vector scaled by the calibration LUT | [1], [11] | VERIFIED |
| 21 | IPF versions with noise/radiometry impact | 2.82 (28 Mar 2017): radiometric normalisation of the TOPS (IW/EW) processor. 2.90 (13 Mar 2018): azimuth noise annotation (Stripmap/Wave normalisation). 2.91 (26 Jun 2018): ranked-echo noise-power estimation begins. 3.10 (26 Jun 2019): consistent noise-level annotation for all L1 products incl. GRDM/GRDH. 3.40 (4 Nov 2021, quoted as 3.3.3/4.0 elsewhere in same paper): in-out-band power ratio. 3.51 (23 Mar 2022): elevation-pattern/noise vector misalignment fixed. 3.71 (19 Oct 2023): RFI-robust noise vectors; after this "high quality ... no (or just very minor) residual issues". | [11], [15] | VERIFIED |
| 22 | Orbit files | POEORB 5 cm (3D RMS 1 sigma) requirement; latency 20 days; RESORB 10 cm, 45 min; a Full Mission Reprocessing (FMR 2021) of POEORB corrected a GPS antenna reference-point change of July 2020 | [16] | VERIFIED |
| 23 | Planetary Computer sentinel-1-rtc | Radiometrically terrain-corrected gamma0 (Small flattening), IW only, processed by Catalyst, PlanetDEM, 10 m spacing, UTM, float32 COG per polarisation, nodata -32768, CC BY 4.0, STAC temporal extent from 2014-10-10 open-ended, bbox global; platforms listed: S1A, S1B, S1C (no S1D); access needs a Planetary Computer account to obtain SAS tokens (`msft:requires_account: true`) | [12] | VERIFIED (STAC metadata); real spatial/temporal completeness OPEN |
| 24 | Planetary Computer sentinel-1-grd | Original GRD, COG, HH/HV/VH/VV, noise/calibration XMLs; licence field "proprietary" linking Copernicus terms; temporal start 2014-10-10; platforms S1A, S1B, S1C. The asset description wrongly mentions "radiometric terrain correction applied" (our reading: likely a copy error) | [13] | VERIFIED (metadata) |
| 25 | CDSE RTC / backscatter | Sentinel Hub: beta0, sigma0, gamma0 (ellipsoid) and gamma0 terrain (RTC, Copernicus DEM 10/30/90 m, optional Lee filter); openEO: sigma0-ellipsoid with Copernicus 30 m DEM, no RTC, no speckle filter; on-demand CARD-BS (gamma0, 30 m DEM) and CARD-COH (12-day coherence); "Sentinel-1 RTC" follows CEOS CARD4L NRB, no speckle filtering | [4] | VERIFIED |
| 26 | CDSE S1 global monthly mosaics | S1SAR_L3_IW_MCM: VV+VH at 20 m, non-polar land, IW; radar-shadow observations filtered out; from Oct 2014; 16-bit COG via Sentinel Hub BYOC. (Product is only listed; statistic used for the monthly value was not stated.) | [4] | VERIFIED |
| 27 | Backscatter vs incidence angle | Backscatter generally decreases with incidence angle; stronger for smooth surfaces, weaker for vegetation (volume scattering); 175 relative orbits each have a characteristic projected local incidence angle; normalisation to 38 degrees with per-pixel slope (static -0.13 dB/degree where few orbits) | [17] | VERIFIED |
| 28 | Typical sigma0 (VV / VH, dB; Table 2 means of Sentinel-1 Global Backscatter Model, 2016-17 data) | urban/built-up -7.94 / -15.02 (large spread, corner reflections make urban "among the brightest targets"); agriculture -11.87 / -19.03; herbaceous -13.71 / -21.05; "bare vegetation" -15.75 / -22.98; open water -18.85 / -26.42; VH roughly 7 dB below VV | [17] | VERIFIED |
| 29 | Orbit stability | Radial orbit fluctuation about 50-60 m on average (relative orbit 168 example); projected local incidence angle standard deviation 0.005 degrees; relative-orbit geometry repeats so static layers per orbit suffice | [18] | VERIFIED |
| 30 | SAR signature of PV arrays and row orientation | No peer-reviewed or ESA source found that describes Sentinel-1 backscatter of ground-mounted PV arrays, including row-orientation dependence. Related, not PV: building backscatter depends on alignment with the look direction and double bounce; Plakman et al. (2022) used Sentinel-1 backscatter statistics from one period together with Sentinel-2 in a random-forest solar-park detector. | search, [19] | UNVERIFIED |

## Details

### GRD IW over land: what to process
- Product: Level-1 GRD, detected amplitude (phase lost), multi-looked, ground range, 16-bit [1], [10]. IW GRD HR: 10 m pixels but resolution about 20 x 22 m with only about 4.3 equivalent looks, so speckle is strong and the "10 m" pixel is oversampled by about 2 in range and 2.25 in azimuth [10]. Thermal noise is annotated but not removed; calibration LUTs for beta0, sigma0, gamma0 and DN are provided; the calibration equations are in ESA's separate document "Radiometric Calibration of S-1 Level-1 Products Generated by the S-1 IPF" (not opened) [11]. GRD products apply "a constant offset" with the calibration LUT [11].
- Standard chain: apply orbit file, remove thermal noise (subtract annotated noise vector, scaled by the same LUT), calibrate to sigma0 (ellipsoid) or beta0, geocode with DEM. For terrain-affected sites use radiometric terrain flattening to gamma0 (Planetary Computer RTC and CDSE Sentinel Hub RTC do this). Over flat German sites, ellipsoid sigma0 differs little from terrain-flattened gamma0 (inference; terrain effects matter in Alps, Harz, etc.).
- Noise: the IW NESZ specification is -22 dB maximum [1]; for dark targets (smooth water, some bare soil) and the VH channel, noise matters. Thermal-noise subtraction quality changed over time (see discontinuities).
- Polarisation over Germany: IW dual-pol VV+VH is the land default and the CDSE IW monthly mosaic carries VV and VH for non-polar land [4]; I did not find an ESA statement that every German acquisition is VV+VH (HH+HV is an allowed option in the product spec) [1]. Verify per scene.

### Orbit geometry
Sun-synchronous near-polar orbit at 693 km, 175 relative orbits per 12-day cycle (one satellite), ascending local time 18:00 [1]. Over Germany several relative orbits overlap (not quantified in any page opened) and both ascending (evening) and descending (morning, about 06:00, unverified) passes exist. IW incidence angle spans 29.1-46.0 degrees across the swath [1]. Backscatter depends on incidence angle, strongly for smooth surfaces [17], and flat/rough land cover changes sigma0 by several dB across a swath; therefore a time series must use the same relative orbit (same projected local incidence angle, same look direction, same sub-swath) per site, and ascending and descending data must not be mixed without normalisation. Orbit tube is tight (about 50-60 m radial) so repeat geometry is stable [18]. This justifies keeping one (or a fixed set of) relative orbit(s) per site, or normalising to a reference angle as in [17].

### Constellation timeline and what it means for observation density
| Period | Satellites | Exact repeat (per relative orbit, same direction) | Source |
|---|---|---|---|
| 3 Apr 2014 - Apr 2016 | S1A only | 12 d | [1] |
| 25 Apr 2016 - 23 Dec 2021 | S1A+S1B | 6 d | [1], [3] |
| 24 Dec 2021 - 4 Dec 2024 (S1B lost, S1C not yet launched; SentiWiki's "adjusted scenario" period listed as Sep 2022-Apr 2025) | S1A only | 12 d | [1], [4] |
| 5 Dec 2024 - Mar 2025 | S1A, S1C commissioning | mostly 12 d; S1C data opened 26 Mar 2025 | [5] |
| May 2025 - 16 Apr 2026 | S1A+S1C | 6 d (restored) | [1] |
| 17 Apr - 8 Jun 2026 | S1A+S1C+S1D (S1D with 1-day offset to S1C) | 6 d plus 1-day-offset samples | [6], [7] |
| 9 - 23 Jun 2026 | S1A+S1D (S1C manoeuvring) | partial | [7] |
| 24 Jun 2026 onward | S1C+S1D (S1A retired 29/30 Jun) | 6 d, pattern shifted by 1 day relative to the A/B era | [7], [8], [9] |
Arithmetic (derived, not sourced): 6-day repeat gives about 5 acquisitions per month per relative orbit and direction; 12-day gives about 2.5. Germany is covered by several relative orbits, so actual counts per site depend on the track; ESA publishes acquisition-plan KML files (mentioned on the CDSE page) which should be used to count real passes per site [5]. A 2022-2024 gap in temporal density is therefore expected in monthly medians (about halved sample count); medians over fewer samples are noisier.
Early S1A-only period (2014-2016): I found no source showing complete 12-day IW coverage over Germany from Oct 2014; the CDSE archive start (Oct 2014) is generic.

### Known product discontinuities
- IPF 2.82 (28 Mar 2017) normalised the TOPS processor; before it, signal and noise gains depended on processing configuration [11]. Data from Oct 2014 to Mar 2017 (IPF 2.36-2.72, per [15] deployment dates) therefore carry a radiometric/noise-gain inconsistency relative to later data; the size is not given in the sources opened.
- IPF 2.90 / 2.91 (Mar and Jun 2018) improved noise vectors (azimuth variation, ranked echoes). Before that, de-noising leaves sub-swath discontinuities (IW1-IW2 boundary visible in the paper's example) [11].
- IPF 3.10 (26 Jun 2019): noise normalisation across GRD levels; before, GRDM and GRDH noise vectors disagreed [11].
- Noise-vector calibration constants for IW were re-calibrated for IPF 3.7.x: updates for IW VH (reported rx pol V) of +0.095 dB (IW1), -0.026 dB (IW2), +0.323 dB (IW3) [11, Table 4]; the paper says it "will be possible to generate good-quality noise vectors for past S-1 products as well" with open-source tools [11]. Whether CDSE has reprocessed GRD for 2014-2018 was not found.
- Orbit files: precise orbits (POEORB) available after about 20 days; a GPS reference point change of July 2020 was corrected by FMR 2021 [16]. Geolocation absolute accuracy about 7 m (NRT) [10].
- S1C/S1D carry improved noise estimates from the start (paper lesson) and their calibration is a separate baseline (ETAD reprocessing from 18 Mar 2025, search summary) [11].

### Physics facts
- Corner reflections (double bounce) make urban areas "among the brightest targets"; urban sigma0 mean about -8 dB VV [17]. Strong returns from metal structures (offshore wind turbines, buildings) appear as bright points with ascending/descending-dependent layover displacement (offshore-wind study via search summary, not opened).
- Typical sigma0: bare/sparse vegetation about -16 dB VV, agriculture about -12 dB VV, smooth water about -19 dB VV [17]. A bare-soil site that becomes a gravel yard with steel structures should brighten noticeably, but bare-soil moisture and roughness changes also move sigma0 by several dB, so a single-date threshold is unreliable.
- Cross-pol VH "is highly sensitive to changes in vegetation densities and structure" (SentiWiki applications page); a PV park built on grassland removes volume scattering (VH drop expected; inference).
- PV row-orientation dependence: not found in any source; see item 30.

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|----|---------------------|---------|---------|--------|
| V5 | "Sentinel-1B failed and Sentinel-1C launched later (verify the dates and the effect on revisit time)" | S1B anomaly 23 Dec 2021; end of mission announced 3 Aug 2022; S1C launched 5 Dec 2024, data opened 26 Mar 2025, fully operational early May 2025. Revisit: 6 d (A+B, May 2016-Dec 2021), single-satellite 12 d (2022-Apr 2025, "some regions not currently observed" per CDSE; Europe likely kept covered per an ESA slide, secondary), back to 6 d from May 2025 (A+C), then C+D from 24/29 June 2026. S1D also launched (4 Nov 2025) and S1A retired. | CONFIRMED (dates added; also S1D/S1A) | [1], [3], [4], [5], [7], [9] |
| V5b (S1 part) | "covers Germany every few days, and goes back to 2015 to 2017" | S1 GRD from Oct 2014 (CDSE and PC extent 2014-10-10), earlier than claimed. Revisit "every few days" is wrong for 2022-Apr 2025 (12 d per relative orbit); true 6 d per relative orbit in 2016-2021 and from May 2025; more frequent only by combining overlapping orbits/directions. | CORRECTED | [4], [12], [1] |

## What this means for our method
1. Use IW GRD (or RTC) with a fixed relative orbit and direction per site; build monthly medians per orbit, then, if combining, normalise to a reference angle (about 38 degrees, slope about -0.13 dB/degree as a fallback) [17].
2. Expect uneven sample counts: about 5 per month per orbit in 2016-2021 and from May 2025 versus about 2.5 in 2022-Apr 2025. Store sample count per composite, and require a minimum count for a valid detection, or use 2-month windows in the S1A-only years.
3. For a consistent 2014/2015-2026 series, avoid mixing pre- and post-IPF-2.82 (28 Mar 2017) and pre-IPF-2.91/3.10 radiometry without denoising checks; prefer starting the quantitative time series at or after 26 Jun 2019 (IPF 3.10) or 2017-03-28 with a documented step test. Run a step-change test on invariant targets (e.g. airport or industrial roofs) at the IPF dates 2017-03-28, 2018-03-13, 2018-06-26, 2019-06-26.
4. Planetary Computer RTC is convenient (10 m, gamma0, CC BY 4.0) but needs an account and token, lists only S1A/B/C (no S1D) and its Germany completeness was not verified. Counting STAC items per month for the German bbox is the first test. CDSE offers RTC through Sentinel Hub and openEO and an IW monthly mosaic (20 m).
5. Do not rely on a PV-specific SAR signature; design the SAR branch as "new bright/metal structure plus loss of vegetation volume scattering" and validate on known MaStR sites. Report SAR as supporting evidence only until a signature is validated.
6. Credit line: "Contains modified Copernicus Sentinel data [years]" (see sentinel2.md). PC RTC adds CC BY 4.0 attribution to Microsoft/Catalyst (inference).

## Open questions
- Germany-specific number of relative orbits, and acquisition counts per month by period (use ESA acquisition plan KML or STAC counts).
- Descending local time over Germany (06:00 is an inference).
- Whether IW coverage over Germany was systematic from Oct 2014; the S1A-only 2014-2016 IW plan.
- Magnitude of radiometric steps at the IPF dates for 2014-2019 GRD; whether CDSE reprocessed it.
- Actual Germany coverage and date range in Planetary Computer sentinel-1-rtc and whether S1D is added.
- Units of PC RTC (linear power versus amplitude) not stated in STAC.
- PV array SAR signature in the literature (Plakman et al. 2022 full text returned HTTP 403).
- ESA "Radiometric Calibration of S-1 Level-1 Products" and the Level-1 product definition were not opened.
- Sentinel-1 observation scenario pages (sentiwiki observation-scenario URL 404, dragon3.esa.int did not resolve).

## Sources
1. S1 Mission, SentiWiki. https://sentiwiki.copernicus.eu/web/s1-mission . Retrieved 2026-11-12.
2. Sentinel-1A: a prime from first light to last, ESA/Copernicus. https://sentinels.copernicus.eu/web/success-stories/-/sentinel-1a-a-prime-from-first-light-to-last . Retrieved 2026-11-12.
3. Mission ends for Copernicus Sentinel-1B satellite, ESA, 3 Aug 2022. https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-1/Mission_ends_for_Copernicus_Sentinel-1B_satellite . Retrieved 2026-11-12.
4. Sentinel-1 documentation, Copernicus Data Space Ecosystem. https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel1.html . Retrieved 2026-11-12.
5. Sentinel-1C User Data Opening from 26th of March, CDSE news, 25 Mar 2025. https://dataspace.copernicus.eu/node/2232 . Retrieved 2026-11-12.
6. Sentinel-1D user data opening from 17 April 2026, Copernicus. https://sentinels.copernicus.eu/-/sentinel-1d-user-data-opening-from-17-april-2026 . Retrieved 2026-11-12.
7. Sentinel-1 orbital reconfiguration dates, CDSE news. https://dataspace.copernicus.eu/node/3949 . Retrieved 2026-11-12.
8. S1C/D Final Orbital Configuration Achieved, CDSE news, 24 Jun 2026. https://dataspace.copernicus.eu/node/4010 . Retrieved 2026-11-12.
9. Copernicus Sentinel-1A Satellite End of Operations After 12 Years of Service, CDSE news, 30 Jun 2026. https://dataspace.copernicus.eu/node/4026 . Retrieved 2026-11-12.
10. S1 Products, SentiWiki. https://sentiwiki.copernicus.eu/web/s1-products . Retrieved 2026-11-12.
11. Recchia A. et al., "Generating Accurate De-Noising Vectors for Sentinel-1: 10 Years of Continuous Improvements", Remote Sensing 17(20):3474, 17 Oct 2025, doi:10.3390/rs17203474 (open access; PDF read pp. 1-2, 11-21). Also S1 Processing, SentiWiki https://sentiwiki.copernicus.eu/web/s1-processing . Retrieved 2026-11-12.
12. sentinel-1-rtc STAC collection, Microsoft Planetary Computer. https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-rtc . Retrieved 2026-11-12.
13. sentinel-1-grd STAC collection, Microsoft Planetary Computer. https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-grd . Retrieved 2026-11-12.
14. (Merged with 12/13.)
15. IPF version history, SAR Mission Performance Cluster. https://sar-mpc.eu/processor/ipf/ . Retrieved 2026-11-12 (dates only, notes column empty).
16. S1 Processing, SentiWiki (orbit files, FMR 2021). https://sentiwiki.copernicus.eu/web/s1-processing . Retrieved 2026-11-12.
17. Bauer-Marschallinger B. et al., "The normalised Sentinel-1 Global Backscatter Model, mapping Earth's land surface with C-band microwaves", Scientific Data 8:277, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8553891/ . Retrieved 2026-11-12 (first 100 000 characters read).
18. Navacchi C. et al., "Utilising Sentinel-1's Orbital Stability for Efficient Pre-Processing of Radiometric Terrain Corrected Gamma Nought Backscatter", Sensors, 2023. https://pmc.ncbi.nlm.nih.gov/articles/PMC10346578/ . Retrieved 2026-11-12.
19. Plakman V., Rosier J., van Vliet J., "Solar park detection from publicly available satellite imagery", GIScience & Remote Sensing, 2022, doi:10.1080/15481603.2022.2036056; abstract via https://research.vu.nl/en/publications/solar-park-detection-from-publicly-available-satellite-imagery/ . Retrieved 2026-11-12 (full text 403).
Search-only (SECONDARY): CDSE/ESA items on S1C first products (30 Jan 2025) and S1D "fully operational 1 May 2026"; ESA presentation on S1A-only plan in Europe (earth.esa.int LPS 2022 Potin, 404); ESA Sentinel-1 data sheet (esamultimedia.esa.int/docs/S1-Data_Sheet.pdf) and handbook orbit page for 18:00 local time; offshore-wind Sentinel-1 study arXiv 2604.20822; archaeology Sentinel-1 double-bounce study arXiv 2101.11170.
