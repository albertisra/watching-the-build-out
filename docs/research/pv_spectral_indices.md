# Spectral indices, PV spectra and detectability limits
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Coverage caveat: several MDPI and Nature article pages blocked fetching. Only formulas read in an opened source are marked VERIFIED. Others are UNVERIFIED.

## Key facts
| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | NDPI (Feng et al. 2024, Sci Data, DOI 10.1038/s41597-024-02994-x) | NDPI = (rho(SWIR1) - rho(NIR)) / (rho(NIR) - rho(SWIR2)) = (B11 - B8) / (B8 - B12). Paper: "PV panels show an obvious reflectance peak in Band-11", absorption in B8 and B12; NDPI in the top-10 features of both partitioned and national RF models; no numeric separability given | [1] | VERIFIED |
| 2 | Other indices in Feng et al. | NDVI (vegetation vs PV), SAVI, MNDWI (water), NDBI (buildings); formulas not reproduced in the page we read (standard definitions, see 3) | [1] | VERIFIED (use), formulas UNVERIFIED here |
| 3 | Standard definitions | NDVI=(B8-B4)/(B8+B4); NDBI=(B11-B8)/(B11+B8); MNDWI=(B3-B11)/(B3+B11); NDTI, BSI | not fetched this session | UNVERIFIED |
| 4 | PVSEI, "Development of a photovoltaic system extraction index for the detection of large PV plants using Sentinel-2 images" (tested Viterbo IT, Seville ES) | Exists; formula not obtained (ResearchGate 403) | [2] | UNVERIFIED (formula) |
| 5 | Czirjak 2017 (J. Appl. Remote Sens. 11(2) 026007): hyperspectral PV signature, introduced NSPI | existence per citing paper; original not opened | [3] | SECONDARY |
| 6 | Ji et al. 2021, RSE 266:112692, DOI 10.1016/j.rse.2021.112692 | nHI (hydrocarbon, points 1669, 1728, 1746 nm, threshold >0.18); NSPI (R1153 and R991, threshold >0.15; exact functional form not shown in our extract); aVNIR (500-1000 nm mean <2000, reflectance scaled); REND (R2100>R2200>R2300); PEP (650-860 nm peak, <200, excludes polyethylene); VPEP (470-630 nm, <200, excludes synthetic turf). Hyperspectral (HySpex 1.2 m), not Sentinel-2 | [3] | VERIFIED |
| 7 | Ji et al. performance | OA 92.8-99.3% on four 1.2 m subsets; producer accuracy 52.2-86.7%; user accuracy 64.5-72.5% where given; thin-film and small arrays missed | [3] | VERIFIED |
| 8 | Ibrahim and Gobin 2021, Remote Sensing 13(21):4195 (plastic-covered agricultural soil) | Sentinel Hub script: index = B02 / (1 - ((B02 + B03 + B08) / 3)); threshold 0.13; page text says B04 in the mean but code uses B03 (code authoritative). Not selective: bare soil and coasts appear | [4] | VERIFIED (script), paper UNVERIFIED (403) |
| 9 | PGI / PMLI / PGHI formulas | PGI from Landsat ETM+ VIS/NIR; PMLI from Landsat 5 SWIR; Senel et al. 2023 (IEEE JSTARS) benchmarked 8 Sentinel-2 indices and found PGHI best; formulas not retrieved | search summaries | UNVERIFIED |
| 10 | Indices used by Kruitwagen et al. | Not determined (paper not readable) | | UNVERIFIED |
| 11 | "PVI" (Zhang et al.) | Search returned only Perpendicular Vegetation Index, not a PV index; no Zhang/Wang/Xia/Chen PV-specific index found | search | UNVERIFIED |
| 12 | Plakman et al. 2022 did not use named indices | features = mean/SD/median of all 10 and 20 m S1 and S2 bands per segment | [5] | SECONDARY |

## Details
**Crystalline-Si PV spectrum (from Ji et al. 2021, airborne/lab library, 400-2500 nm):** low average reflectance in VNIR (500-1000 nm); steep reflectance rise from ~600 to 1150 nm following the silicon absorption edge (the paper's NSPI uses 991 and 1153 nm; the citing literature describes the steep rise between about 990 and 1150 nm); hydrocarbon absorption near 1.73 µm from EVA encapsulant; strong absorption near 2.2 µm (REND: 2100 > 2200 > 2300 nm). Confusers named by the paper: polyethylene roofing/surface and oil (also 1.73 µm), synthetic turf, roofing tiles and copper (NSPI alone), aluminium and ponds (HI alone). Bitumen and PVC give near-zero hydrocarbon index (separable). Comparison with bare soil, gravel, asphalt and water is not tabulated in the source we read: UNVERIFIED. Sentinel-2 cannot resolve 1.73 µm (B11 at ~1.61 and B12 at ~2.19 µm are broad); the 1.1 µm silicon edge falls between B8 (0.84) and B11 (1.61), so only NDPI-type contrasts between B8, B11 and B12 are accessible. The Feng et al. rule (B11 peak, B8 and B12 low) is an empirical Sentinel-2 statement, not a physics derivation.

**Detectability at 10 m.** Feng: blobs under 9 pixels (900 m2) removed; smallest Chinese ground PV about 30,000 m2. GRW (4.7 m): minimum 10,000 m2, object recall 19.6%. Kruitwagen: P 98.6%/R ~90% above 10,000 m2 (secondary). TZ-SAM threshold >500 kW. Ji et al. attribute misses to mixed pixels for small modules at 1.2 m. No source retrieved quantifies grass between rows, row orientation, sun angle or glint at 10 m: OPEN.

**SAR.** No paper retrieved describes the Sentinel-1 signature of PV parks directly. Evidence: Plakman et al. feed S1 backscatter statistics into RF and report it helps (best model used "radar backscatter properties of one period"); a Remote Sensing study (MDPI 14/24/6296, not opened, via search summary) found texture of NDBI, VV and VH among top features; an ESSD 2025 preprint on water-surface PV notes strong metallic backscatter and confusion with water. Quantitative VV/VH values: OPEN.

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|---|---|---|---|---|
| V7c | Spectral indices proposed for PV detection exist in the literature | NDPI (B11-B8)/(B8-B12) verified; NSPI/nHI (hyperspectral) verified in concept (Ji 2021, from Czirjak 2017); PVSEI exists, formula not obtained; no Sentinel-2 PGI/PMLI formula verified | CONFIRMED (NDPI, hyperspectral indices); OPEN (PVSEI formula, plastic indices) | [1][2][3][4] |

## What this means for our method
- Include NDPI, B11/B8, B12/B8, NDVI, NDBI, MNDWI as GBM features; they are cheap and one is published for exactly this task.
- Add the plastic-foil blue-ratio index (item 8) as a greenhouse-confuser feature, and add plasticulture/greenhouse hard negatives.
- Use time-series statistics (per-pixel median, SD across the year) because PV is temporally stable and bright in B11.
- 1 MWp (roughly 1-2 ha, about 100-200 pixels) sits well above the 9-pixel noise floor of Feng and above GRW's 10,000 m2 minimum, but sites near 1 MWp will be the most affected by mixed pixels.
- Check the formulas in rows 3, 4, 9 from the original papers before coding.

## Open questions
- PVSEI formula; Senel et al. 2023 and Ibrahim and Gobin formulas; Czirjak 2017 original; USGS/ECOSTRESS library entries for PV; any glint/orientation studies; Sentinel-1 PV signature numbers.

## Sources
1. https://pmc.ncbi.nlm.nih.gov/articles/PMC10864270/ (Feng et al. 2024), retrieved 2026-11-12
2. ResearchGate listing (403) https://www.researchgate.net/publication/386012952 ; existence via search summary
3. Ji et al. 2021 https://pmc.ncbi.nlm.nih.gov/articles/PMC8559660 , retrieved 2026-11-12; Czirjak via citing papers (search)
4. https://custom-scripts.sentinel-hub.com/sentinel-2/plastic_greenhouse/ (CC BY-SA 4.0), retrieved 2026-11-12
5. https://research.vu.nl/en/publications/solar-park-detection-from-publicly-available-satellite-imagery/ (via search summary)
