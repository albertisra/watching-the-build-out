# Neighbouring-country registries of solar parks and battery storage
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Scope: registries of utility-scale commercial installations only. No personal data was collected. Many national pages returned 403 or could not be found with web search/fetch only, so several verdicts are UNVERIFIED and need a manual look. Only the French ODRE dataset was inspected at field level.

## Key facts
| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 1 | France ODRE national register (aggregated) | Dataset "registre national des installations de production et de stockage d'électricité (agrégé)"; 143,712 records; 50 fields incl. `filiere`, `typestockage`, `puismaxinstallee`, `puismaxinstalleedischarge`, `energiestockable`, `datemiseenservice`, `dateraccordement`, `codeinseecommune`, `commune`, `codeiris`, `gestionnaire`; licence Licence Ouverte v2.0 (Etalab); publisher RTE/Enedis/EDF SEI/ELD; DCAT periodicity "Mensuelle"; data processed 2026-11-10 | [1][2] | VERIFIED |
| 2 | France: coordinates | None. Location only by INSEE commune, IRIS, EPCI, département; the page states the finest permitted level is IRIS, annual time step; installations under 36 kW aggregated | [1][2] | VERIFIED |
| 3 | France: storage coverage | Fields `typestockage` and theme "Stockage" exist; actual value list not seen, so not confirmed that batteries are labelled | [2] | UNVERIFIED (values) |
| 4 | Switzerland BFE/Pronovo "Elektrizitätsproduktionsanlagen" | Production plants in operation, from the guarantee-of-origin system data supplied by Pronovo; >110,000 plants; location, technology, capacity; GPKG and CSV on data.geo.admin.ch, API on api3.geo.admin.ch; opendata.swiss terms link points to attribution-type OGD terms. Storage not confirmed. Dataset page itself returned 403 | [3] (search summary) | SECONDARY |
| 5 | Denmark Stamdataregister (Energistyrelsen) | Public Excel download historically available (DTU copy covers wind turbines to June 2019 with GSRN, connection date, kW, municipality code); regulation covers location, connection, capacity, energy source. Current file layout, coordinates and battery coverage not found; a 2025 draft order would widen reporting to more plant types for new plants | [4][5] | SECONDARY / UNVERIFIED for storage and coordinates |
| 6 | Netherlands RVO SDE++ | RVO "Feiten en cijfers" pages offer aggregated Excel downloads (progress, cash spend, budget); no project-level list of individual solar parks found | [6] | SECONDARY |
| 7 | Netherlands solar-park datasets | Kadaster maps solar parks >1,000 m2 from aerial photography (562 parks, >3,621 ha at end 2022, per a study); WUR research portal lists "Solar parks in the Netherlands" (Vittek & Krijgsveld, 14 Oct 2025; licence, format not seen); VU/DataverseNL 2022 solar-park detection dataset (2020 coverage); PDOK services are open data | [7] | SECONDARY |
| 8 | Netherlands battery register | No national public register of large batteries found | [7] | UNVERIFIED |
| 9 | Belgium | No official open unit-level register of solar parks or batteries found. Elia open data has aggregated solar generation estimates/forecasts and publishes battery information; OpenInfraMap/OSM lists plants (community-sourced, not official) | [8] | SECONDARY |
| 10 | Austria | Plant registration is via OeMAG/stromnachweis (E-Control); no public plant-level download found | [9] | UNVERIFIED |
| 11 | Poland URE | Public concession register (art. 43b Prawo energetyczne) and a register of small RES generators published on URE site; storage concession guide exists; unit coordinates not seen | [10] | SECONDARY |
| 12 | Czechia ERÚ | Licences for electricity production exist (licence needed for plants above small thresholds; list of production sites is a form); no public downloadable plant list found | [11] | UNVERIFIED |

## Details
- France is the only registry I opened. It is open, monthly, has storage-relevant fields (`typestockage`, discharge power, storable energy) and commissioning dates, but gives location only to commune/IRIS level and aggregates small plants. For satellite validation that means matching detections to a commune and capacity class, not to a site. Fields present are enough to build commune-level counts of storage and PV capacity by commissioning year. The licence (Licence Ouverte 2.0) permits reuse with attribution.
- Switzerland is the strongest candidate for unit-level coordinates (GPKG with geometry per plant, per search summary). Coverage is guarantee-of-origin registered plants, so utility-scale batteries may be absent (batteries are not producers); needs checking on data.geo.admin.ch. Switzerland is also outside the EU day-ahead zone and (per the EPEX summary) was not on 15-minute day-ahead at the 2025 switch, which weakens it for the price-spread side.
- Netherlands: no unit-level registry was found, but an open dataset of solar parks exists (WUR 2025, Kadaster-derived mapping), which can serve as reference polygons. Battery side is open. The NL market (EPEX NL zone) is coupled with DE in SDAC.
- Belgium, Austria, Poland, Czechia: nothing confirmed as a downloadable unit-level register with coordinates. Treat as UNVERIFIED; manual check of VREG/VEKA, CWaPE, Elia, E-Control, URE and ERÚ sites is needed.
- Denmark: Stamdataregister is the best-known public unit-level register for PV and wind (Excel). Whether it now includes batteries, and coordinates (historically municipality code only, per the DTU description) is unconfirmed.

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|---|---|---|---|---|
| V9 | "Repeat the detection for one neighbouring country with a usable public registry, for example the Netherlands or Belgium (verify the registry availability)" | No unit-level public registry with coordinates and storage found for NL or BE. NL has open solar-park mapping datasets (WUR/Kadaster) but not a registry with capacity and commissioning date. Better-documented alternatives: Switzerland (coordinates, plants in operation), France (storage fields, no coordinates), Denmark (PV register, unverified for coordinates/storage) | CORRECTED (NL/BE not confirmed; alternatives ranked below) | [1]-[8] |

## What this means for our method
Ranked recommendation (for satellite detection validated against a registry):
1. Switzerland: unit-level coordinates, GPKG/CSV, open; gaps are battery coverage and EU-market comparability. Verify on data.geo.admin.ch before committing.
2. Denmark: PV register with capacity and connection dates, DK1/DK2 in SDAC; verify current file for coordinates and battery category.
3. Netherlands: no registry, but a recent open solar-park polygon dataset (verify WUR licence) gives reference data for PV; battery validation would lack ground truth.
4. France: storage fields and open licence, but only commune/IRIS location, so site-level validation is not possible; usable only for area-level comparison.
5. Belgium, Poland, Czechia, Austria: not recommended until a registry is found.
If the aim is a quick credibility check of the detection pipeline, use the German MaStR plus a Swiss or Danish extension; avoid promising NL or BE in the proposal until a source is confirmed.

## Open questions
- Does the Swiss dataset include battery/storage units and what is its licence wording (page 403)?
- Current Danish Stamdataregister download: columns, coordinates, storage.
- WUR "Solar parks in the Netherlands" dataset: licence, geometry, DOI.
- Belgian regional registers (VREG/VEKA, CWaPE) and Elia data on batteries.
- ODRE `typestockage` and `filiere` values.

## Sources
1. ODRE dataset page, https://odre.opendatasoft.com/explore/dataset/registre-national-installation-production-stockage-electricite-agrege/information/, retrieved 2026-11-12.
2. ODRE API metadata, https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/registre-national-installation-production-stockage-electricite-agrege/, retrieved 2026-11-12.
3. BFE/opendata.swiss via search results: https://opendata.swiss/en/dataset/elektrizitatsproduktionsanlagen (page 403), 2026-11-12. Secondary.
4. DTU copy of Danish Stamdataregister wind data, https://data.dtu.dk/articles/Historic_data_of_wind_turbine_installations_in_the_whole_of_Denmark_from_the_Danish_Energy_Agency_Energistyrelsen_/7599698, via search.
5. Danish Stamdata order 2023 / 2025 consultation, https://www.retsinformation.dk/eli/lta/2023/623/pdf; https://www.lovguiden.dk/dokument/hoeringsportalen/hor-69729-udkast-til-ændring-af-bekendtgørelse-om-stamdataregistret-for-elproducerende-anlæg-m-v, via search.
6. RVO Feiten en cijfers SDE, https://www.rvo.nl/subsidies-financiering/sde/feiten-en-cijfers, via search.
7. WUR research portal / Kadaster / PDOK via search: https://research.wur.nl/en/datasets/ (403); https://research.vu.nl/en/datasets/replication-data-for-solar-park-detection-from-publicly-available/.
8. Elia open data, https://www.elia.be/grid-data/generation-data/solar-pv-power-generation-data; OpenInfraMap https://openinframap.org/stats/area/Belgium/plants (via search).
9. E-Control, https://www.e-control.at/en/statistik/e-statistik (via search).
10. URE, https://www.gramwzielone.pl/trendy/31419/ure-zaktualizowal-rejestr-malych-wytworcow (secondary, via search).
11. ERÚ, https://eru.gov.cz (forms and licence documents via search).
