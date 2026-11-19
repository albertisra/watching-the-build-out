# Prior work on PV and BESS detection, and foundation models for Sentinel-1/2
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Coverage caveat: the Nature article pages (Kruitwagen 2021, Feng 2024, Dunnett 2020 figshare) and MDPI pages blocked automated fetching (303/403). For those, facts come from the official Zenodo record, the Oxford ORA abstract record, the Earth Engine community catalogue (secondary) or PMC copies. Statuses reflect this. The Satlas web app page gave no content.

## Key facts
| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | Kruitwagen et al., Nature 598, 604-610 (2021), DOI 10.1038/s41586-021-03957-7 | >10 kW commercial/industrial/utility PV; 68,661 facilities; 423 GW (-75/+77) end of 2018 | [1][2] | VERIFIED (abstract via ORA) |
| 2 | Kruitwagen imagery | Sentinel-2 and SPOT6/7 (per project summary); exact resolutions not read from the paper | [3] | SECONDARY |
| 3 | Kruitwagen accuracy | For installations >10,000 m2 (~600 kW): precision 98.6%, recall ~90%, IoU 90% (as quoted by the GEE catalogue, not read from the paper) | [4] | SECONDARY |
| 4 | Kruitwagen dataset | Zenodo 10.5281/zenodo.5005868, v1.0.0, 393.3 MB, licence "Creative Commons Attribution 4.0 International"; predicted_set 68,661 polygons (end 2018), training 36,882 OSM polygons, test 7,263, CV 6,281 | [2][4] | VERIFIED (Zenodo), counts SECONDARY |
| 5 | Kruitwagen dates | Zenodo page lists no install-date field; ORA abstract says dataset is enriched with "estimated installation dates" per catalogue | [2][4] | SECONDARY (field name UNVERIFIED) |
| 6 | Kruitwagen code | GitHub Lkruitwagen/solar-pv-global-inventory, licence "mit" per an aggregator; code also on Zenodo 5045001 | [5] | SECONDARY |
| 7 | Kruitwagen vintage | Snapshot end-2018 only; useless for 2019+ build-out | [4] | VERIFIED |
| 8 | SatlasPretrain (Bastani et al., ICCV 2023, arXiv:2211.15660) | 302M labels, 137 categories, 7 label types; Sentinel-2 + NAIP; paper CC BY 4.0 | [6] | VERIFIED |
| 9 | Satlas licences | Code Apache-2.0; "The foundation models and the new annotations are released under ODC-BY"; third-party imagery/labels keep original licences (Sentinel under ESA terms, OSM ODbL) | [7][8][9] | VERIFIED |
| 10 | Satlas pretrained weights (satlaspretrain_models) | Checkpoints under ODC-BY, code Apache-2.0. Sentinel-2: SwinB, SwinT, Resnet50, Resnet152, RGB (3 bands B4,B3,B2) or MS (9 bands), single-image (SI) and multi-image (MI); Sentinel-1: SwinB, 2 bands VV,VH; Landsat 8/9: SwinB, 11 bands; Aerial 0.5-2 m RGB SwinB. No parameter counts, no CPU guidance on the page. Weights-only download in the main repo: 1.5 GB | [8][7] | VERIFIED |
| 11 | Satlas solar-farm model | Repo contains config `configs/satlas_explorer_solar_farm.txt` and a precision/recall evaluation command; no published P/R and no product licence found; satlas.allen.ai page returned no content | [7] | UNVERIFIED (product details) |
| 12 | GloSoFarID (Yang & Rad, arXiv:2404.05180) | 13,703 samples (6,793 pos / 6,910 neg), 256x256x13 Sentinel-2 10 m, 2021-2023; US subset manually annotated, rest model-labelled from Kruitwagen-derived inventory; Zenodo 10939100, 10.2 GB, licence "Creative Commons Attribution 4.0 International"; no accuracy metrics on arXiv abstract page | [10][11][12] | VERIFIED (Zenodo, arXiv abstract), details SECONDARY (search snippet) |
| 13 | GloSoFarID labels are noisy | Global part is model-predicted, not hand-labelled; no dates; Germany coverage not confirmed | [12] | VERIFIED for noisy origin (per search summary), Germany UNVERIFIED |
| 14 | Global Renewables Watch (Robinson et al., arXiv:2503.14860) | PlanetScope quarterly RGB basemaps ~4.7 m; U-Net/ResNeXt-50 for solar; Q4 2017 to Q2 2024; per-feature estimated construction date and replaced land use; 86,410 solar PV installations and 375,197 wind turbines; labels from OSM + Kruitwagen + Dunnett, manual val/test | [13][14] | VERIFIED |
| 15 | GRW accuracy (Table 1, test) | Solar pixel level: precision 57.73%, recall 80.31%, F2 74.48%. Solar object level: precision 50.93%, recall 19.60%, F2 22.35%. Min solar size >10,000 m2. Country r2 vs IRENA 0.960 | [13] | VERIFIED |
| 16 | GRW licence/data | Repo licence MIT; data `solar_all_2024q2_v1.gpkg` in release v1.0 (GeoPackage, EPSG:3857). Data-specific licence not separately stated. Germany not mentioned in paper text | [13][14] | VERIFIED (repo MIT) |
| 17 | GRW cadence | Paper gives no future update schedule; a launch-era "twice a year" statement is secondary. Current release stops at 2024 Q2 | [13][14][15] | VERIFIED (no schedule), SECONDARY (older claim) |
| 18 | TZ-SAM (TransitionZero) | Q1 2024 Zenodo 11368204: 63,616 assets, 183 countries, licence "Creative Commons Attribution Non-Commercial 4.0 International"; fields id, geometry, capacity_mw, constructed_before, constructed_after; >80% of assets have dates; threshold ">500kW"; ~2,000 detections validated, ~1% false positives; "10-metre satellite imagery" (sensor not named) | [16][17] | VERIFIED |
| 19 | TZ-SAM cadence | Quarterly releases (GEE catalogue lists to 2025Q3; web search reports Q4 2025 released 2 Feb 2026 and Q1 2026 on 7 May 2026). Commercial licence separate | [17][18] | SECONDARY for 2026 releases |
| 20 | Dunnett et al. 2020, Sci Data 7:130, DOI 10.1038/s41597-020-0469-8 | Harmonised OSM-derived global wind/solar locations; dataset DOI 10.6084/m9.figshare.11310269; intended licence ODbL, figshare copy may display CC0; article CC BY | [19][20] | SECONDARY |
| 21 | Feng et al., Sci Data 2024, DOI 10.1038/s41597-024-02994-x (China 10 m PV map 2020) | Sentinel-2 RF on GEE with spectral+texture+slope/aspect; test set 10,000 samples: OA 89.13%, recall 0.9014, precision 0.8836; blobs <9 pixels removed => 900 m2 minimum; data CC BY 4.0 (Science Data Bank 10.57760/sciencedb.o00121.00001) | [21][22] | VERIFIED (PMC text), licence SECONDARY |
| 22 | Plakman, Rosier, van Vliet 2022, GIScience & RS 59(1):461-480, DOI 10.1080/15481603.2022.2036056 | Netherlands 2020; SNIC objects on Sentinel-2; mean/SD/median of all 10 and 20 m bands of S1 and S2 into random forest; OA 99.97%, kappa 0.90, producer accuracy solar 85.86%; replication data on DataverseNL | [23] | SECONDARY (search summary); not opened |
| 23 | Mayer et al., 3D-PV-Locator, Applied Energy 310:118469 (2022) | Rooftop PV from 10 cm NRW aerial imagery + 3D building data, validated vs German registry (~2/3 exact match for orientation classes); code github.com/kdmayer/3D-PV-Locator. Contrast only: rooftop, 10 cm, not usable at 10 m | [24] | SECONDARY |
| 24 | BESS detection | No published BESS detector or imagery dataset found (see Details) | searches | VERIFIED as "not found" by search, not as non-existence |
| 25 | Plasticulture Germany (Zenodo 14055243) | Sentinel-1+2 GEE workflow, Germany 2020, hexagon results; classes plastic-free / plastic-mulched / plastic covers above vegetation; licence "Creative Commons Attribution 4.0 International" | [25] | VERIFIED |
| 26 | Global-PCG-10 (Niu et al., ESSD 17, 5065-5088, 2025) | 10 m global plastic greenhouses 2020 from Sentinel-2; test OA 98.04%, PCG producer 85.12%, user 99.82%, F1 91.88%; data figshare 10.6084/m9.figshare.27731148; dataset licence not stated on article page (article CC BY 4.0) | [26] | VERIFIED |

## Foundation-model table (inputs and licences)
| Model | Licence of weights (quoted) | Params | Input | CPU / consumer GPU / MPS |
|---|---|---|---|---|
| SatlasPretrain (Swin-T/B, ResNet50/152) | "Checkpoints are released under" ODC-BY; code Apache-2.0 [8] | not stated on page (UNVERIFIED) | S2 RGB (3) or 9 bands; S1 VV,VH; normalisation: S2 /255 of 8-bit scaled values | not stated; Swin-T/ResNet50 are small ViT/CNN-class models, so CPU inference plausible but UNVERIFIED |
| Prithvi-EO-2.0-300M (NASA/IBM) | "Apache-2.0" [27] | 300M ("Pretrained 300M parameter model") | 6 HLS bands (Blue, Green, Red, Narrow NIR, SWIR 1, SWIR 2), pretrained on HLS V2 at 30 m, time series | page only says Colab fine-tune notebooks use a T4 GPU |
| Clay | Apache-2.0 for weights and code; docs CC-BY; embeddings ODC-BY [28][29] | not stated | multi-sensor incl. location/time (v1.5 latest); bands not on page | not stated |
| SSL4EO-S12 backbones | "The dataset and pretrained model weights are released under the CC-BY-4.0 license"; code Apache 2.0 [30] | ResNet18/50, ViT-S/16, ViT-B/L/H variants (counts UNVERIFIED) | S2 L1C 13 bands (/10000), S2 RGB, S1 2 bands | ResNet50 / ViT-S are CPU-feasible in general (UNVERIFIED on page) |
| DOFA | MIT (repo) [31] | ViT-base checkpoint (DOFA_ViT_base_e100.pth); count not stated | any channels given wavelengths in micrometres; S2 9 bands, S1 2 bands demo; 224x224 | not stated |
| TerraMind 1.0 (IBM/ESA) | "apache-2.0" on HF model cards [32] | tiny/small/base/large; counts not on pages (UNVERIFIED) | S2L2A (12 bands), S2L1C, S1GRD (2), S1RTC, DEM, RGB | docs (secondary) suggest tiny/small for local work [33] |
| Presto (NASA Harvest) | MIT [34] | not stated | pixel time series, S2+S1 (+ERA5, SRTM, Dynamic World), 1-24 timesteps | pixel-wise, light; hardware not stated |
| AlphaEarth Foundations embeddings | "CC-BY 4.0"; attribution "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind." [35] | n/a (precomputed, model weights not released per our reading, UNVERIFIED) | 64-d annual embedding, 10 m, 2017-2024, GEE | no inference needed; query GEE |
| TESSERA | Code MIT; weights and embeddings CC0 [36] | not stated | S2 L2A 10 bands + S1 RTC VV/VH, 128-d (v2 Matryoshka 16-128), 10 m, 2017-2025 | Linux/WSL only, macOS not supported; recommended >=128 GB RAM; 110x110 km took ~10 h on 128 cores + A30. Download of precomputed embeddings via geotessera is the realistic route |

## Details
**BESS.** Searches (two extended, one standard, English and German) found no paper, dataset or product that detects battery storage sites from satellite or aerial imagery. Only a figure caption (footprint of MWh-scale BESS measured manually from satellite images, e.g. Moss Landing) and a US patent application on generic "energy project status" CNN detection surfaced (secondary). Nearest analogues: substation detection with CI-dataset (aerial, dasci.es) and Mask R-CNN on Netherlands substations from OSM labels (Zenodo 10.5281/zenodo.10214168), WorldView-3 power-infrastructure pipeline (GitHub PI-detection), storage-tank labels for oil/gas well pads (Nature Communications 2024), and Sentinel-2 plasticulture/industrial mapping. All use sub-metre imagery except plasticulture. Containerised BESS of 1-50 MW occupy roughly a few hundred to a few thousand m2 (our own expectation, UNVERIFIED), i.e. 1-30 Sentinel-2 pixels, below the smallest sizes reported by any PV product (900 m2 in Feng; 10,000 m2 in GRW; ~500 kW in TZ-SAM).

**Germany and dates.** Kruitwagen (end 2018) is global and presumably includes Germany but its size is dated. TZ-SAM provides constructed_before/constructed_after bounds, the only global product with explicit date bounds usable as a prior; CC-BY-NC. GRW has estimated construction dates but is 4.7 m RGB and its object recall is 19.6%.

**Licence consequences.** Non-commercial public research: CC-BY-NC (TZ-SAM) is acceptable but derived labels published on GitHub carry NC and attribution. ODbL (Dunnett/OSM) is share-alike for derived databases. ODC-BY, CC-BY, CC0, MIT, Apache-2.0 weights are unproblematic with attribution.

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|---|---|---|---|---|
| V7 | Fine-tune a pretrained S2 / multi-sensor foundation model (licences, CPU/modest GPU) | All listed models have permissive licences (Apache-2.0, MIT, CC-BY, ODC-BY, CC0). Satlas Swin-T/ResNet50, SSL4EO ResNet50/ViT-S, DOFA-base, Presto, TerraMind tiny/small are plausibly CPU/modest-GPU; official pages only state T4 for Prithvi and Linux-only/large RAM for TESSERA. Parameter counts mostly not on pages. Prithvi pretrained at 30 m HLS, not native 10 m | CONFIRMED (licences); OPEN (hardware, param counts) | [8][27]-[36] |
| V7b | Kruitwagen 2021, Satlas solar labels, SatlasPretrain, GloSoFarID exist; any BESS work | Kruitwagen, SatlasPretrain, GloSoFarID confirmed. Satlas solar-farm product exists as config only; no accuracy/licence found. No BESS detection work found | CONFIRMED (3), OPEN (Satlas solar product), CONFIRMED-not-found (BESS) | [1]-[12] |

## What this means for our method
- BESS is novel: no label set, so positives must come from MaStR coordinates. Realistic expectation is site-level classification of cropped context at 10 m, not segmentation. Validate on very high-resolution orthophotos.
- For PV, Kruitwagen and TZ-SAM are weak-label sources (end 2018 and quarterly respectively); do not use them as ground truth for Germany without MaStR cross-check.
- Reported detection limits (10,000 m2 GRW; 900 m2 Feng; >500 kW TZ-SAM) suggest the 1 MWp threshold (~1-2 ha) is at the edge; expect lower recall near the bottom.
- Gradient boosting with spectral features is supported by Feng (RF, 89% OA) and Plakman (RF, S1+S2); both use balanced or oversampled samples, so report precision at realistic prevalence.
- Use Germany plasticulture (CC BY 4.0) and Global-PCG-10 as hard negatives.
- Embeddings (AlphaEarth CC-BY, TESSERA CC0) can be features for GBM at no inference cost; try them before fine-tuning.

## Open questions
- Exact Kruitwagen P/R by size band, bands and the date method: read the paper or ORA PDF (12 MB, too big for the fetch tool).
- Satlas solar farm product accuracy and terms; parameter counts and CPU timings for all models; TerraMind sizes.
- Global PV 2019-2022 Sci Data dataset (s41597-025-04985-y, 20 m) and a Fraunhofer IEE 2026 CNN+SVM Sentinel-2 PV paper were seen in search only and not opened.
- Plakman and Mayer details are from search summaries only.

## Sources
1. Kruitwagen et al. Nature 598:604-610, DOI https://doi.org/10.1038/s41586-021-03957-7 (nature.com blocked; not fetched), 2021-10-27
2. Zenodo record https://zenodo.org/records/5005868 (v1.0.0, 2021-10-27), retrieved 2026-11-12
3. Web search summary citing project GitHub, retrieved 2026-11-12
4. GEE community catalogue https://gee-community-catalog.org/projects/global_pv/ (updated 2021-10-28), retrieved 2026-11-12
5. https://github.com/Lkruitwagen/solar-pv-global-inventory (via search; direct fetch of another URL 404)
6. https://arxiv.org/abs/2211.15660
7. https://github.com/allenai/satlas
8. https://github.com/allenai/satlaspretrain_models
9. https://github.com/allenai/satlas/blob/main/SatlasPretrain.md ; DataLicense (ODC-By) https://github.com/allenai/satlas/blob/main/DataLicense
10. https://arxiv.org/abs/2404.05180 (v2 2024-08-26)
11. https://zenodo.org/records/10939100 (2024-04-08)
12. Web search summary of arXiv HTML https://arxiv.org/html/2404.05180v2
13. https://arxiv.org/html/2503.14860v1
14. https://github.com/microsoft/global-renewables-watch
15. https://gee-community-catalog.org/projects/grw/ (secondary, via search)
16. https://zenodo.org/records/11368204 (2024-05-29, modified 2025-01-17)
17. https://gee-community-catalog.org/projects/tzero/ (GEE last update 2025-12-09)
18. Web search summary of TransitionZero insights pages (release dates Q4 2025, Q1 2026), secondary
19. https://eprints.soton.ac.uk/439781/ (via search)
20. https://gee-community-catalog.org/projects/energy_farms/ (via search)
21. https://pmc.ncbi.nlm.nih.gov/articles/PMC10864270/ (Feng et al. 2024)
22. Search summary for data DOI/licence (Science Data Bank)
23. https://research.vu.nl/en/publications/solar-park-detection-from-publicly-available-satellite-imagery/ and doaj record (via search)
24. https://github.com/kdmayer/3D-PV-Locator and search summaries
25. https://zenodo.org/records/14055243
26. https://essd.copernicus.org/articles/17/5065/2025/
27. https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M
28. https://huggingface.co/made-with-clay/Clay
29. https://clay-foundation.github.io/model/index.html
30. https://github.com/zhu-xlab/SSL4EO-S12
31. https://github.com/zhu-xlab/DOFA
32. https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base
33. TerraTorch docs via search https://terrastackai.github.io/terratorch/1.2.1/guide/terramind (secondary)
34. https://github.com/nasaharvest/presto
35. https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL
36. https://github.com/ucam-eo/tessera
