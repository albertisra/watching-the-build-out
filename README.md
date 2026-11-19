# Watching the Build-out

Tests whether free Sentinel imagery can date construction of German battery storage and solar parks before the official registry does.

**Status, November 2026.** Registry ground truth, imagery pipelines, physical features and a labelling app are built and have been reviewed independently. The first round of hand labelling is about to start. There is no detection accuracy, no lead-time estimate and no capacity scenario yet. Everything below that describes those results is planned work.

## Question

The Marktstammdatenregister (MaStR) records when an energy unit is registered and when it is commissioned. It does not record when construction starts, so public data cannot show how much battery and solar capacity is being built at a given moment. Satellites see the land being cleared, the pads laid and the container rows or module tables appear. The project asks whether free imagery sees this reliably, how much earlier than the registry it sees it, and what the construction visible today implies for operational capacity over the next 12 to 24 months<!-- KICKOFF.md Section 2.2 -->.

In scope are utility-scale battery storage sites from 1 MW and ground-mounted solar parks from 1 MWp<!-- docs/data_card_registry.md -->. Five hypotheses structure the work. All five are open:

* **H1, detectability.** Above what site size can a site be detected with useful precision and recall, measured separately for each track and reported by technology, size, season and region?
* **H2, phases.** Can the monthly series separate undisturbed, cleared, under construction and complete, and recover the start and completion months?
* **H3, lead time.** Does the construction start seen from orbit come before MaStR registration and commissioning, by how many months, and how often is the lead zero or negative?
* **H4, pipeline gap.** How does battery capacity under construction at a given time compare with the grid connection commitments published for the same year?
* **H5, market link.** Does growth in operational battery capacity coincide with narrower daily day-ahead price spreads? This is described only. No causal claim will be made, and the remaining confounders will be named.

[Motivation: the author writes this paragraph in his own words.]

## Two tracks

Both tracks are evaluated on the same labelled test sites, the same spatial blocks and the same metrics. The comparison between them is one of the planned results. Neither track is a fallback for the other.

* **Track A, Sentinel only.** Sentinel-1 radar and Sentinel-2 optical imagery for all of Germany, fully automatic. It asks how far free imagery at 10 m resolution<!-- docs/research/sentinel2.md --> can go on its own.
* **Track B, Sentinel plus orthophotos.** Sentinel for timing, open aerial orthophotos (DOP) from the federal states at 20 to 40 cm<!-- docs/research/dop_sources.md --> for identity and footprint. It covers only the states that publish DOP openly. Orthophotos are flown every few years, so they confirm what a site is and how large it is, while the Sentinel series dates when it was built.

## Method in brief

1. **Registry ground truth (observed).** The MaStR bulk export of 16 November 2026<!-- docs/data_card_registry.md --> gives 1,392 battery units and 7,742 ground-mounted PV units in scope<!-- docs/data_card_registry.md -->. Units are grouped into sites by single linkage at 300 m<!-- docs/data_card_registry.md -->, which gives 1,241 battery sites and 5,790 PV sites<!-- results/registry/registry_sites_summary.csv -->. As a check against official figures, operating battery storage at the BNetzA reference date of 15 October 2025 rebuilds to 2.30 GW gross power against a published 2.4 GW, and to 3.11 GWh usable capacity against a published 3.2 GWh<!-- results/registry/comparison_official_statistics.csv -->.
2. **Imagery (observed).** Each site gets an image chip with a monthly Sentinel-2 median of clear pixels, selected with the scene classification layer, and a monthly Sentinel-1 median of VV and VH backscatter in dB from one fixed relative orbit. The number of clear observations is kept for every month. Months lost to cloud or snow stay missing and are modelled, never interpolated. Each series comes from one processing platform only.
3. **Features.** Spectral indices, the contrast between the site centre and a surrounding ring, texture, radar level and the VV minus VH difference, and change against the same month one year earlier. Each feature has a written physical rationale in `docs/research/signatures.md`, which also predicts a minimum detectable site size before any detector exists.
4. **Labels (observed, human interpretation).** The author labels site class and the months of clearing, first structures and completion in a local app that hides every registry field. The first pass shows Sentinel imagery only. A second pass shows the orthophoto, so Track A labels stay independent of Track B input. A blind 10 % subset<!-- docs/analysis_plan.md --> is relabelled to measure the author's own consistency. The first round holds 410 chips<!-- results/labels/queue_round1_summary.csv -->, stratified by technology, size, commissioning period and federal state, with hard negatives from OpenStreetMap (greenhouses, industrial yards, car parks, quarries, warehouse roofs) and random negatives stratified by ESA WorldCover class.
5. **Detection (detected, planned).** A gradient-boosted classifier per technology on site months. A pretrained foundation model is tried only if the baseline leaves clear room for improvement. Recall is reported as a curve against site size, not as one threshold.
6. **Timelines and lead time (detected, planned).** A strictly left-to-right four-state hidden Markov model and Bayesian online change-point detection turn the monthly features into phase dates. Lead time is the registry date minus the detected construction start, estimated with methods that handle interval censoring, sites not yet registered and truncation at the export date.
7. **Pipeline, scenarios and market link (modelled, planned).** Footprint is converted to MW and MWh with a calibration that depends on commissioning year. Capacity under construction is compared with connection commitments, and Monte Carlo scenarios give ranges for operational capacity. Day-ahead prices from Energy-Charts and SMARD are related to operational battery capacity descriptively.

Every quantity in the results is labelled observed (registry or market data), detected (model output from imagery) or modelled (nowcast or scenario).

## How the work is kept honest

* **Pre-registered plan.** `docs/analysis_plan.md` was written and frozen on 18 November 2026, before any label or model output existed. Its SHA-256 is stored in `results/timeline/analysis_plan_v1_sha256.txt`. Changes go only through the deviations log in Section 13 of the plan.
* **Spatial block validation with a locked test fold.** The 410 queue sites<!-- results/timeline/split_v1_summary.csv --> are grouped into 2 km clusters and assigned to 50 km blocks<!-- results/timeline/split_v1_summary.csv -->, which are split into 5 folds<!-- results/timeline/split_v1_summary.csv -->. Fold 0 (82 sites<!-- results/timeline/split_v1_summary.csv -->) is the test fold and is locked. Code refuses to evaluate on it without a recorded model freeze. The most recent 12 months of imagery<!-- docs/analysis_plan.md --> are held out as a temporal test.
* **Circularity guard.** Registry dates, status and capacity never enter detection or timeline models. An allow-list of feature columns and a deny-list of registry columns are enforced in code and covered by tests. Registry dates are joined only after the models are frozen, to measure lead time.
* **Simulation checks before real data.** The timeline models were tested on synthetic series against thresholds set in the plan. Not all checks passed<!-- results/timeline/simulation_checks.csv -->. The thresholds were not changed, and the diagnosis is in `results/timeline/simulation_diagnosis.md`.
* **Independent reviews.** A reviewer who sees only the outputs and the specification, not the builders' reasoning, checks each phase and reruns the tests. The reviews are in `docs/reviews/`. They found, among other things, a wrong Sentinel-1 orbit formula and results derived from use-restricted orthophotos. Both were fixed. After the orbit fix, 0 of 83,262 stored radar scenes lie on a different relative orbit from the rest of their series<!-- results/imagery/s1_orbit_consistency.csv -->.
* **Assumptions register.** Every modelling assumption is in `docs/assumptions.md` with its source, plausible range and the sensitivity test that covers it.

## Current status

| Phase | Content | State |
|---|---|---|
| 0 | Setup, research brief, assumptions and data source registers | done |
| 1 | Registry ground truth, data card, capacity series, comparison with official statistics | done, reviewed |
| 2 | Imagery pipelines for both tracks, national scan benchmark on one state | done, reviewed |
| 3 | Physical features, signature analysis, labelling app, first labelling queue | built; first labelling round about to start |
| 4 | Detection and timelines in both tracks, lead time, track comparison | code built and tested on synthetic data only; no result |
| 5 | Discovery scan, pipeline gap, capacity scenarios | planned |
| 6 | Descriptive market link | planned |
| 7 | Full independent review and research note | planned |
| 8 | One-command rebuild, licence, citation file, published benchmark data card | planned |

Phase 3 is complete only when at least 300 sites are labelled and the author's consistency on the blind subset is measured<!-- KICKOFF.md Section 7 -->. The detailed task log is `docs/STATUS.md`. Open decisions are in `docs/decisions_pending.md`.

## Data sources, licences and attribution

All sources are recorded with their terms in `docs/data_sources.md`. Only free services and free quotas are used.

| Source | Use | Licence and required attribution |
|---|---|---|
| Copernicus Sentinel-1 and Sentinel-2 | Monthly radar and optical series | Copernicus Sentinel data terms. "Contains modified Copernicus Sentinel data 2015 to 2026" |
| Marktstammdatenregister bulk export (Bundesnetzagentur) | Registry ground truth | Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0). "© Bundesnetzagentur, Marktstammdatenregister, dl-de/by-2.0, data modified (filtered, aggregated, grouped into sites)" |
| OpenStreetMap | Cross-check of positives, hard negatives | ODbL 1.0. "© OpenStreetMap contributors", https://www.openstreetmap.org/copyright. OSM-derived tables are kept apart from MaStR-derived tables |
| ESA WorldCover 2021 v200 | Land cover strata for random negatives | CC BY 4.0. "Contains ESA WorldCover data © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium" |
| Planetary Computer `sentinel-1-rtc` (pilot radar chips and some figures) | Terrain-corrected Sentinel-1 backscatter | CC BY 4.0. "Contains modified Copernicus Sentinel data", processed by Catalyst; credit to Microsoft and Catalyst under CC BY 4.0 |
| Energy-Charts (Fraunhofer ISE) and SMARD (Bundesnetzagentur) | Day-ahead prices, planned for Phase 6 | CC BY 4.0. "Bundesnetzagentur \| SMARD.de" and energy-charts.info |

Processing platforms: Microsoft Planetary Computer (STAC and cloud-optimised GeoTIFF reads), Sentinel Hub on the Copernicus Data Space Ecosystem (free tier), and Google Earth Engine (non-commercial Community tier; Cloud Score+ by Google, CC BY 4.0). Earth Engine imagery is not re-hosted. Radar series from different platforms use different calibrations and are never combined.

State orthophotos (Track B), with the attribution each licence requires:

| State | Licence | Attribution |
|---|---|---|
| Bayern (LDBV) | CC BY 4.0 | © Bayerische Vermessungsverwaltung (LDBV), CC BY 4.0, modified |
| Baden-Württemberg (LGL-BW) | dl-de/by-2.0 | LGL-BW (year of data) Datenlizenz Deutschland Namensnennung Version 2.0, www.lgl-bw.de |
| Berlin (SenStadt) | dl-de/zero-2.0 | none required |
| Brandenburg (LGB) | dl-de/by-2.0 | © GeoBasis-DE/LGB, dl-de/by-2-0 (Daten geändert) |
| Bremen (LGB HB) | CC BY | Quelle: Landesamt GeoInformation Bremen |
| Hessen (HVBG) | free use under HVGG | Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation (modified) |
| Niedersachsen (LGLN) | CC BY 4.0 | LGLN (year) Creative Commons Namensnennung 4.0 International |
| Nordrhein-Westfalen (Geobasis NRW) | dl-de/zero-2.0 | courtesy credit: Geobasis NRW |
| Rheinland-Pfalz (LVermGeoRP) | dl-de/by-2.0 | ©GeoBasis-DE / LVermGeoRP (year), dl-de/by-2-0, http://www.lvermgeo.rlp.de [Daten bearbeitet] |
| Sachsen (GeoSN) | dl-de/by-2.0 | Quelle: GeoSN, dl-de/by-2-0 |
| Sachsen-Anhalt (LVermGeo ST) | dl-de/by-2.0 | © LVermGeo ST, dl-de/by-2-0 (exact string to be confirmed with the provider) |
| Schleswig-Holstein (LVermGeo SH) | CC BY 4.0 | © GeoBasis-DE/LVermGeo SH/CC BY 4.0 |
| Thüringen (GDI-Th) | CC BY 4.0 | © GDI-Th |

Mecklenburg-Vorpommern orthophotos are not used: the state's service restricts external use, so they appear in no labelling view, no Track B input and no result or figure. Hamburg orthophotos are not used because the state's service mixes open aerial years with closed satellite years that cannot be told apart. Saarland orthophotos are not used because the service could not be accessed under open terms. The fee-based national BKG mosaic is not used.

## Repository layout

```
src/bo/data/        registry, OSM, labelling queue
src/bo/imagery/     STAC, Sentinel Hub and Earth Engine chips, orthophotos, national scan
src/bo/features/    spectral and radar features, signature analysis
src/bo/labelling/   label schema, storage, blind views
src/bo/models/      detectors, guards, synthetic checks
src/bo/timeline/    change points, hidden Markov model, lead time, spatial folds
app/                local labelling and review apps (Streamlit)
tests/              pytest suite
data/labels/        author labels (kept in the repository)
data/raw, data/chips, data/processed, data/checkpoints
                    symlinks to a data folder outside the repository, not committed
results/            small result tables, one folder per stage
figures/            figures (vector and PNG)
docs/               STATUS, analysis plan, assumptions, data sources, data cards,
                    research notes, reviews, paper drafts
notebooks/          exploration only, nothing canonical
```

## Reproducing

1. Install [uv](https://docs.astral.sh/uv/) and run `uv sync --frozen` (or `make setup`). The environment is pinned by `uv.lock`, Python 3.12.
2. Copy `.env.example` to `.env` and fill in your own credentials: a Copernicus Data Space Ecosystem account for Sentinel Hub, and optionally an Earth Engine project for non-commercial use. Planetary Computer needs no account. Code reads credentials from the environment at runtime and never prints them.
3. Create a data folder outside the repository (the default is `~/Data/Power_Grid/`) and link `data/raw`, `data/chips`, `data/processed` and `data/checkpoints` to it. Raw downloads, image chips and checkpoints never go into the repository.
4. Download the MaStR bulk export by hand from the MaStR download portal into `data/raw/mastr/`. The provider changes the file name daily to prevent scripted retrieval, so no script fetches it.
5. Run the stages:

| Command | What it does |
|---|---|
| `make test`, `make lint` | test suite and ruff |
| `make registry` | registry sites, capacity series and data card from the newest export |
| `make pilot` | pilot sites and negatives from the registry |
| `make queue`, `make queue-view` | first labelling queue (needs the Geofabrik Germany extract) and its blind view |
| `make chips`, `make chips-s1`, `make chips-s2` | chip stores on Planetary Computer and Sentinel Hub |
| `make features` | monthly feature tables, allow-listed columns only |
| `make signatures` | signature figures, contrast fits, minimum size prediction, cloud-mask and confuser checks |
| `make scan` | national scan benchmark on one state |
| `make models-synthetic` | detector machinery on synthetic data (not a result) |
| `make label`, `make review` | labelling app and post-labelling review app, local only |

The Earth Engine chips for the labelling queue are built with `uv run python -m bo.imagery.eequeue` and have no make target yet. The stages `detect`, `timelines`, `scenarios`, `market` and `figures` are not implemented, so `make all` stops there.

All imagery work stays inside free quotas: the Sentinel Hub free tier, the Earth Engine Community tier and anonymous Planetary Computer access. Quota use is logged in `results/imagery/quota_log.csv`. A full national scan has not been run.

## Responsible scope

The project covers utility-scale commercial energy infrastructure only. It excludes rooftops, private homes and anything that identifies a private person. Results are published as aggregates by federal state, district or month. Site coordinates stay under `data/` and are not committed. A single site appears only as an illustration, and only if it is already public through MaStR, OpenStreetMap or press coverage. The project does not extract or publish security-relevant site detail, does not rank sites by importance to the grid, and does not combine detections with grid topology. Operator names are not extracted from the registry.

## Licence

Code licence: MIT (`LICENSE`). Data keep their own licences; see `NOTICE.md` and the attribution tables above.

Data products derived from the sources above keep their source licences and attributions.
