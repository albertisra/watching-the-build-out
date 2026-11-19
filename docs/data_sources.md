# Data sources and licences

Rule 6 of `KICKOFF.md`: every source is recorded here with its licence and attribution before it is used.
Last update: 2026-11-18 (DOP rows added in Phase 2 Track B).

"Status" says how well the licence terms are established: VERIFIED means a scout read them on the provider's
own page; TO CONFIRM means the terms rest on a secondary source or were not found and must be confirmed by the
agent that first uses the source, before the first download.

## Registry and official statistics

| Source | Used for | Access | Licence and attribution | Status | Note |
|---|---|---|---|---|---|
| Marktstammdatenregister bulk export (Bundesnetzagentur) | Unit-level ground truth for storage and ground-mounted PV | Daily ZIP of XML, downloaded by hand through the MaStR download portal into `data/raw/mastr/`. No scripted retrieval: the provider changes the file name daily to prevent it | Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0). Derived data may be republished with attribution and a note that it was modified | VERIFIED | `docs/research/mastr.md`. Coordinate availability is the open risk R1 |
| BNetzA / SMARD publications on storage connection requests and commitments | H4 comparison | Published articles | CC BY 4.0, credit "Bundesnetzagentur \| SMARD.de" | VERIFIED for SMARD | `docs/research/bnetza_storage_stats.md` |
| OpenStreetMap | Cross-check of positives, hard negatives from land use, substations as context only | Overpass API, one cached request per bounding box (`src/bo/data/osm_features.py`, cache in `data/raw/osm/`); a Geofabrik Germany extract is the alternative for a national run | ODbL 1.0; attribution "© OpenStreetMap contributors" with link to https://www.openstreetmap.org/copyright; share-alike applies to derived databases, so OSM-derived files live in `data/processed/registry/osm/`, separate from MaStR tables | VERIFIED wording (`docs/research/mastr.md`, OSMF guidelines); test box fetched once on 2026-11-18, no national download yet | Overpass policy: sequential requests with delay, no scheduled use; generic user agent without contact details. Grid features are a coarse prior or context only (scope rule) |
| `open-mastr` (OpenEnergyPlatform) | Possible parser for the export | PyPI | AGPL-3.0-or-later | VERIFIED | Not a dependency. Decision pending (R11) |

## Imagery

| Source | Used for | Access | Licence and attribution | Status | Note |
|---|---|---|---|---|---|
| Copernicus Sentinel-2 L2A | Monthly optical composites | Planetary Computer STAC `sentinel-2-l2a`; CDSE STAC `sentinel-2-l2a` | Copernicus Sentinel data terms; credit "Contains modified Copernicus Sentinel data [Year]" | VERIFIED | `docs/research/sentinel2.md` |
| Copernicus Sentinel-1 GRD | Monthly backscatter medians | Planetary Computer STAC `sentinel-1-grd`; CDSE STAC `sentinel-1-grd` | Copernicus Sentinel data terms, same credit | VERIFIED | `docs/research/sentinel1.md` |
| Planetary Computer `sentinel-1-rtc` | Terrain-corrected backscatter, if usable | Planetary Computer STAC | CC BY 4.0 | TO CONFIRM | Flagged as requiring an account; anonymous blob read untested; Sentinel-1D not listed |
| Microsoft Planetary Computer (platform) | Main route for the national scan | Public STAC API, anonymous SAS tokens | Platform terms of use | TO CONFIRM | Official terms page was not opened by the scout. No documented numeric rate limits |
| Copernicus Data Space Ecosystem (platform) | Second route; needs the author's account | STAC, S3, Sentinel Hub, openEO | CDSE terms; free-tier quotas in `docs/research/access_platforms.md` | VERIFIED for quotas, recheck before hard-coding | Needs `.env` |
| Google Earth Engine (platform) | Used (Track A queue chips, `data/chips/ee_r1`) | Earth Engine API | Non-commercial terms; Community tier, 150 EECU-hours per month, no billing account | VERIFIED | Opted in by the author 2026-11-18; Community tier only; S1 is sigma0 (not gamma0), so EE and Sentinel Hub series are never mixed |
| State orthophotos (DOP), per federal state | Track B identity and footprint | WMS 1.3.0 GetMap and GetFeatureInfo per state (`src/bo/imagery/dop.py`); throttled to one request per second; every response cached in `data/raw/dop/<state>/` | Per state, see the rows below. The fee-based BKG national mosaic is excluded | VERIFIED per state (`docs/research/dop_sources.md`, 2026-11-18) | Chips and site coordinates stay under `data/`; only aggregates in `results/`. Required attribution for published figures: list the states used with the strings below |
| DOP Bayern (LDBV), incl. historical 2003 to 2025 | Pilot chips, flight date via `by_dop20_info` | `geoservices.bayern.de/od/wms/dop/v1/dop20`, `.../dop40`, `.../histdop/v1/histdop` | CC BY 4.0. Attribution: appropriate credit, licence link, indication of changes; we use "© Bayerische Vermessungsverwaltung (LDBV), CC BY 4.0, modified" | VERIFIED | Max 6000 x 6000 px |
| DOP Baden-Württemberg (LGL-BW) | Pilot chips (no flight date in service) | `owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C` | Datenlizenz Deutschland Namensnennung 2.0. "LGL-BW (2024) Datenlizenz Deutschland - Namensnennung - Version 2.0, www.lgl-bw.de" (year of data in brackets) | VERIFIED | |
| DOP Brandenburg (LGB) | Pilot chips (flight-date layer fails) | `isk.geobasis-bb.de/mapproxy/dop20c/service/wms` | dl-de/by-2.0. "© GeoBasis-DE/LGB, dl-de/by-2-0 (Daten geändert)"; add "© Geoportal Berlin, dl-de/by-2-0" if Berlin is included | VERIFIED | |
| DOP Berlin (SenStadt), Bremen (LGB HB), Thüringen (GDI-Th) | Coded, no pilot site | `gdi.berlin.de/services/wms/truedop_2024`; `geodienste.bremen.de/wms_dop20_2023`; `geoproxy.geoportal-th.de/geoproxy/services/DOP20` | Berlin dl-de/zero-2.0 (no attribution); Bremen CC BY, "Quelle: Landesamt GeoInformation Bremen"; Thüringen CC BY 4.0, "© GDI-Th" | VERIFIED | |
| DOP Mecklenburg-Vorpommern (LAiV M-V) | Pilot chips, flight date via `mv_dop_info` | `www.geodaten-mv.de/dienste/adv_dop` | NOT open data. Service metadata (CSW, 2026-11-18): INSPIRE 13(1)(e) access restriction; internal use allowed, other external use needs permission and may be charged (AGNB AfGVK). Attribution when used: \"© GeoBasis-DE/M-V <Jahr der letzten Datenlieferung>\" | VERIFIED (restricted) | Chips stay in `data/`, never published or committed; author to decide: request permission or drop MV |
| DOP Niedersachsen (LGLN) | Pilot chips, flight date `BF_DATUM` | `opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms` | CC BY 4.0. "LGLN (<year>) Creative Commons Namensnennung 4.0 International" | VERIFIED | |
| DOP Nordrhein-Westfalen (Geobasis NRW) | Pilot chips, flight date `Bildflugdatum` | `www.wms.nrw.de/geobasis/wms_nw_dop` | dl-de/zero-2.0, no conditions. Courtesy credit "Geobasis NRW" | VERIFIED | Native 10 cm |
| DOP Rheinland-Pfalz (LVermGeoRP) | Pilot chips (production date only) | `geo4.service24.rlp.de/wms/rp_dop20.fcgi` | dl-de/by-2-0. "©GeoBasis-DE / LVermGeoRP (Jahr des Datenbezugs), dl-de/by-2-0, http://www.lvermgeo.rlp.de [Daten bearbeitet]" | VERIFIED | |
| DOP Sachsen (GeoSN) | Pilot chips, flight date via `sn_dop_020_info` | `geodienste.sachsen.de/wms_geosn_dop-rgb/guest` | dl-de/by-2-0. "Quelle: GeoSN, dl-de/by-2-0" | VERIFIED | Max 4096 px |
| DOP Sachsen-Anhalt (LVermGeo ST) | Pilot chips, flight date from tile index `dop_aktualitaet.zip` | `www.geodatenportal.sachsen-anhalt.de/wss/service/ST_LVermGeo_DOP_WMS_OpenData/guest` | dl-de/by-2-0 (open-data page). We use "© LVermGeo ST, dl-de/by-2-0" | VERIFIED (string TO CONFIRM) | DOP10 restricted, not used |
| DOP Schleswig-Holstein (LVermGeo SH) | Pilot chips (no flight date in service) | `dienste.gdi-sh.de/WMS_SH_DOP20col_OpenGBD` | CC BY 4.0. "© GeoBasis-DE/LVermGeo SH/CC BY 4.0" | VERIFIED | |
| DOP Hessen (HLBG/HVBG) | Chips, flight date via `he_dop_rgb_info` | `www.gds-srv.hessen.de/cgi-bin/lika-services/ogc-free-images.ows` | HVGG §24, §18: free, any use without restriction or condition; if a credit is given it must state modifications. We use \"Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation (modified)\" | VERIFIED | MaxWidth 3000, chips at 0.25 m |
| DOP Hamburg (LGV), Saarland (LVGL) | Not used | Hamburg `geodienste.hamburg.de/wms_dop_zeitreihe_unbelaubt` | Hamburg dl-de/by-2.0 for aerial years, but the service includes closed Maxar satellite years that cannot be told apart; Saarland not obtainable (403, Geoportal default charges) | OPEN | see `dop_sources.md` |

## Market data

| Source | Used for | Access | Licence and attribution | Status | Note |
|---|---|---|---|---|---|
| Energy-Charts API (Fraunhofer ISE) | DE-LU day-ahead prices, solar generation, load | `https://api.energy-charts.info`, `/price` with `bzn=DE-LU` | Licence string returned with each DE-LU response: "CC BY 4.0 (creativecommons.org/licenses/by/4.0) from Bundesnetzagentur \| SMARD.de". Credit both SMARD and energy-charts.info; store the licence field of every response | VERIFIED | 2 requests per minute on `/price` |
| SMARD (Bundesnetzagentur) | Cross-check of prices and generation | `chart_data` JSON (filter 4169 for DE-LU day-ahead) and CSV export | CC BY 4.0, credit "Bundesnetzagentur \| SMARD.de" | VERIFIED | SMARD states it is reviewing the licensing of wholesale prices; recheck in Phase 6 |
| DWD open data | Temperature control, if needed | DWD open data server | CC BY 4.0 per scout | TO CONFIRM | Terms page was not readable |
| Gas and carbon prices | Control variables | none found | none found that allows our use | OPEN | Risk R9. Do not use EEX data without a licence |
| ENTSO-E Transparency Platform | Not used | n/a | n/a | n/a | Only if the author adds a token and asks |

## Reference datasets and models

| Source | Used for | Licence | Status | Note |
|---|---|---|---|---|
| Kruitwagen et al. 2021 global PV inventory (Zenodo 5005868) | Cross-check of PV positives up to 2018 | CC BY 4.0 | VERIFIED for licence | Accuracy figures are secondary |
| GloSoFarID | Possible extra PV samples | CC BY 4.0 | VERIFIED for licence | Partly model-labelled |
| Global Renewables Watch | Cross-check, has construction dates | Repository MIT | TO CONFIRM data licence | Release ends 2024 Q2 |
| TransitionZero TZ-SAM | Cross-check only | CC BY-NC 4.0 | VERIFIED | Non-commercial; do not redistribute derived data from it |
| SatlasPretrain weights | Foundation model, only if the baseline needs it | ODC-BY | VERIFIED | Compute needs open (V7) |
| Other foundation models (Prithvi-EO-2.0, Clay, SSL4EO-S12, DOFA, TerraMind, Presto, satellite embeddings) | Same | Permissive, per table in `docs/research/pv_bess_detection.md` | TO CONFIRM individually before use | |

## Software

Python packages are pinned in `uv.lock`. Licences of packages with copyleft terms are checked before they are added
(for example `scikit-survival` is GPL-3.0-or-later and `open-mastr` is AGPL-3.0-or-later; neither is installed).

## Registry outputs (Phase 1)

| Source | Used for | Access | Licence and attribution | Status | Note |
|---|---|---|---|---|---|
| MaStR derived tables (`data/processed/registry/registry_units.parquet`, `registry_sites.parquet`, `results/registry/*.csv`) | Registry ground truth, capacity series | `make registry` on the export in `data/raw/mastr/` | dl-de/by-2.0. Attribution: "© Bundesnetzagentur, Marktstammdatenregister, dl-de/by-2.0, data modified (filtered, aggregated, grouped into sites)" | Provider's exact attribution string still an open question | Operator names and IDs are not extracted. Coordinates only under `data/processed`. Run on a partial export first (2026-11-18); see `docs/data_card_registry.md` |
| OSM-derived files (`data/processed/registry/osm/`) | Comparison with the registry | `python -m bo.data.osm_features` | ODbL 1.0, "© OpenStreetMap contributors" | VERIFIED | Keep apart from MaStR-derived data; a public release of these files must be under ODbL |

## Imagery pipeline (Phase 2, `src/bo/imagery/`)

Added 2026-11-18 by the imagery engineer. Attribution carried in every figure, table and chip store that derives
from imagery: **"Contains modified Copernicus Sentinel data 2015-2026"** (sensing years actually used; the chip
stores carry it in their metadata). Raw redistribution would need "Copernicus Sentinel data [Year]". Source of the
wording: `docs/research/sentinel2.md` fact 24 and `docs/research/access_platforms.md` fact 23.

| Source | Used for | Access | Licence, terms and attribution | Status | Note |
|---|---|---|---|---|---|
| Planetary Computer `sentinel-2-l2a` | Chips, monthly composites, national scan benchmark | Public STAC API without account; COG reads with SAS tokens obtained anonymously through the `planetary-computer` package (`pc.sign`), tokens re-requested per read and cached by the package | Sentinel data under the Copernicus terms (collection licence "proprietary" with link to them); platform terms: "Supplemental Terms of Use for Microsoft Planetary Computer Previews" (research note: tokens not to be transferred or monetised, production use at own risk; the page itself was not readable by the scout) | VERIFIED for access on 2026-11-18, platform terms TO CONFIRM by the author | No documented rate limits. We use at most 12 reader threads and retry with back-off. Stores are raw-baseline reflectance with the offset applied per item (see assumptions R5) |
| Planetary Computer `sentinel-1-rtc` | Chips: monthly VV and VH medians on one fixed relative orbit | Same anonymous STAC and SAS route; the collection flag `msft:requires_account: true` did not block blob reads on 2026-11-18 | CC BY 4.0, processed by Catalyst (PlanetDEM); credit "Contains modified Copernicus Sentinel data [Year]" plus the CC BY 4.0 credit to Microsoft and Catalyst | VERIFIED (anonymous read tested for 2015 to 2025 scenes) | Gamma0 terrain flattened, linear power, 10 m, UTM, nodata -32768. `sentinel-1-grd` on the same platform is not cloud-optimised or geocoded, so it was not used |
| CDSE Sentinel Hub Statistical API | R3 test only (daily SCL class and cloud-probability statistics over small polygons; no pixels downloaded) | `https://sh.dataspace.copernicus.eu/api/v1/statistics`, bearer token from the CDSE account password grant with the public client `cdse-public` (variables `CDSE_USERNAME`, `CDSE_PASSWORD` from `.env`) | CDSE terms and the Copernicus Sentinel data terms; free tier 10,000 requests and 10,000 processing units per month (`docs/research/access_platforms.md` facts 7 and 8) | VERIFIED. The OAuth client in `.env` (`CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`) was rejected with `invalid_client` on 2026-11-18, the author may want to recreate it in the dashboard | Usage in `results/imagery/quota_log.csv` |
| Natural Earth admin-1 (10 m) | Federal state outlines for stratified random negatives and for the benchmark state | One download, `data/raw/ne/ne_10m_admin_1_states_provinces.zip` | Public domain (naturalearthdata.com terms) | VERIFIED by the engineer from the Natural Earth terms page convention; low spatial accuracy (about 1 km) is fine for stratification | Not a boundary source for any published statistic |
| OpenStreetMap through Overpass API | Hard negatives (greenhouses, industrial land, car parks, quarries, warehouses), the public-basis check for the sanity panels, and the outlines of the 20 public illustration sites (one `out geom` request on 2026-11-18, cached in `data/raw/osm/public_basis_geom.json`, used only to measure contrast, PSF and cloud-mask behaviour in `bo.features.signatures` and `scl_did`, never as a feature) | A few requests (one per category, 8 random 0.35 x 0.22 degree cells; one for the panel candidates), responses cached under `data/raw/osm/`, 15 s pause between requests, descriptive User-Agent, no repeats when the cache exists. Overpass usage policy: well below the limits of 10,000 queries and 1 GB per day | ODbL 1.0, "(c) OpenStreetMap contributors"; the negatives table is a derived database and carries the credit | VERIFIED | Coordinates of negatives stay in `data/processed/` (not committed) |

## Sentinel Hub on CDSE for server-side chips (Phase 2, second pass)

Added 2026-11-18. Process API (`https://sh.dataspace.copernicus.eu/api/v1/process`) and Statistical API, collections
`sentinel-2-l2a` and `sentinel-1-grd`. Terms: CDSE terms and the Copernicus Sentinel data legal notice (as above);
free tier 10,000 requests and 10,000 processing units per month, 300 per minute (`docs/research/access_platforms.md`
facts 7 and 8). Authentication: client-credentials grant with the OAuth client in `.env` is tried first; it returned
`invalid_client` on 2026-11-18, so the code falls back to the account password grant with the public client
`cdse-public`. Credentials are read from the environment only. Output derived from it carries
"Contains modified Copernicus Sentinel data [Year]". Sentinel-1 here is gamma0 terrain-flattened with the Copernicus
30 m DEM, which differs from the Planetary Computer RTC product (PlanetDEM); the two must not be mixed in one series.

## Labelling queue (Phase 3, `src/bo/data/queue.py`)

| Source | Used for | Access | Licence and attribution | Status | Note |
|---|---|---|---|---|---|
| OpenStreetMap, Geofabrik `germany-latest.osm.pbf` | National hard negatives (greenhouses, industrial land, car parks, quarries, warehouses), A64 | One download of 4.89 GB (4,885,720,802 bytes, below the 5 GB stop limit) from https://download.geofabrik.de/europe/germany-latest.osm.pbf on 2026-11-18, stored once in `data/raw/osm/geofabrik/` | ODbL 1.0. Attribution "© OpenStreetMap contributors", https://www.openstreetmap.org/copyright. The candidate table and queue negatives are derived databases and carry the credit; they stay in `data/processed/labels/` | VERIFIED | Replaces Overpass for the national query. Read with the GDAL OSM driver through pyogrio |
| ESA WorldCover 10 m, 2021, v200 (Planetary Computer collection `esa-worldcover`) | Land cover class at random negative points, A65 | STAC search, then windowed reads of single pixels from the signed COG asset `map`; no tiles stored | CC BY 4.0 (collection licence field on Planetary Computer). Attribution "Contains ESA WorldCover data (c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium" (as given in the collection description) | VERIFIED licence field and tile coverage on 2026-11-18 | The 2020 v100 release is also in the collection; v200 (2021) is used |

## Google Earth Engine for chips (Phase 3, task 3.5)

Added 2026-11-19. Free non-commercial project on the Community tier (150 EECU-hours per month, no billing account;
`docs/research/access_platforms.md` facts 35 to 38). Collections `COPERNICUS/S2_SR_HARMONIZED`, `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`
(CC-BY-4.0, Google) and `COPERNICUS/S1_GRD`. Access: `earthengine-api`, `ee.data.computePixels` to numpy, no export of imagery;
batch exports to a probe asset only for cost measurement, deleted afterwards. Project id from `.env` (`EE_PROJECT`), never written to
results. Terms: Earth Engine terms (non-commercial research use, own results and code may be published; raw Earth Engine imagery is not
re-hosted). Credit "Contains modified Copernicus Sentinel data [Year]" plus Cloud Score+ credit to Google.
