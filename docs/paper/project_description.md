# Watching the Build-out: project description

Draft by `project-narrator`, 19 November 2026 (Phase 3 in progress). Each number has its source file in an HTML comment.
Before using a CV bullet, check that the work it describes is done: bullets with a `[needs result ...]` gap describe work planned for later phases.

## 1. One-line description

Tests whether free Sentinel imagery can date construction of German battery storage and solar parks before the official registry does.

## 2. Three-sentence description

The German Marktstammdatenregister records when energy units are registered and commissioned but not when construction starts, so public data cannot show how much battery and solar capacity is being built at a given time. This project uses free Sentinel-1 radar and Sentinel-2 optical imagery, open aerial orthophotos from the federal states and the registry itself to detect sites, date their construction phases and compare those dates with the registry dates, following an analysis plan that was frozen before any result existed. So far it has built and independently reviewed the registry ground truth (1,392 battery units of at least 1 MW and 7,742 ground-mounted PV units of at least 1 MWp<!-- docs/data_card_registry.md -->), the imagery pipelines for both tracks and a labelling app; there are no detection or lead-time results yet.

## 3. Project summary

Watching the Build-out asks three things. Can free Sentinel satellite imagery detect the construction of utility-scale battery storage and ground-mounted solar parks in Germany? How do the construction dates it finds compare with the dates in the national registry? What does the construction visible at a given time imply for operational capacity? Battery and solar capacity shape the daily price profile of the German power market, but the Marktstammdatenregister records registration and commissioning dates and no construction start.

The data are free Sentinel-1 and Sentinel-2 imagery, open orthophotos published by the federal states, the registry bulk export of 16 November 2026<!-- docs/data_card_registry.md -->, and OpenStreetMap and ESA WorldCover for negative examples. Public day-ahead prices from Energy-Charts and SMARD will be added later for a descriptive market comparison.

Registry units are grouped into sites. Each site gets monthly cloud-masked optical composites and radar medians, and the author's own labels are the reference for construction dates. A detector will classify site months, and a constrained hidden Markov model and Bayesian change-point detection will turn the monthly series into phase dates. Two tracks run on the same test sites: Sentinel alone across Germany, and Sentinel combined with orthophotos where the states publish them openly. The project adds a focus on timing rather than inventory, and a paired comparison of the two tracks.

Phases 0 to 2 are complete and independently reviewed, the analysis plan is frozen and labelling is starting. There are no detection or lead-time results yet.

## 4. Detailed description

### Goal and question

The project asks whether free Sentinel imagery can reliably detect the construction and completion of utility-scale battery storage and ground-mounted solar parks in Germany. It also asks how much earlier than the official registry the imagery sees them, and what the observed construction pipeline implies for operational capacity. Five hypotheses structure the work. All five are open questions:

* **H1:** Above what site size are sites detectable, measured separately for Sentinel alone and for Sentinel plus orthophotos?
* **H2:** Can the imagery separate undisturbed, cleared, under construction and complete, and recover the start and completion months?
* **H3:** Does the construction start seen from orbit come before registration and commissioning, by how much, and how often not?
* **H4:** How does battery capacity under construction compare with grid connection commitments?
* **H5:** Does growth in operational battery capacity coincide with narrower daily price spreads? This one is described only, with no causal claim.

[Motivation in your own words: connection to earlier satellite and OSINT work on tracking tankers, and to how fast Europe's energy system is changing]

### Why the build-out is hard to see

The registry has no construction date and keeps no status history. Past states have to be rebuilt from the dates in the current snapshot. In the export used here, 753 of 1,392 battery units of at least 1 MW are registered as planned<!-- docs/data_card_registry.md -->. Also, 11.3 % of battery units were registered more than a month after commissioning<!-- docs/data_card_registry.md -->. Of 1,199 battery sites with coordinates, 605 lie within 300 m of a ground-mounted solar site<!-- docs/data_card_registry.md -->, so one image can contain two construction episodes. The imagery has its own limits. Clouds and snow remove many winter months, and a small battery site covers only a few pixels. Even at the 20 m resolution of the national scan benchmark, a 1 MW battery site cannot be resolved<!-- results/imagery/scan_benchmark.md -->.

### Data

* **Registry (observed).** The Marktstammdatenregister bulk export of 16 November 2026<!-- docs/data_card_registry.md --> provides the ground truth. In scope are battery units from 1,000 kW gross and ground-mounted PV from 1,000 kW net<!-- docs/data_card_registry.md -->. That gives 1,241 battery sites and 5,790 PV sites<!-- results/registry/registry_sites_summary.csv -->. Published coordinates exist for 1,350 of the 1,392 battery units<!-- docs/data_card_registry.md -->.
* **Satellite imagery.** Sentinel-2 L2A and Sentinel-1 data come through Microsoft Planetary Computer and the free tier of Copernicus Sentinel Hub. An Earth Engine backend is being added. Only free quotas are used, and one series never mixes platforms.
* **Orthophotos (Track B).** Open orthophotos come from the state survey offices through their WMS services. Each state's licence is recorded. One state's service restricts external use, so it is kept out of all results.
* **Negative examples.** OpenStreetMap and ESA WorldCover supply hard and random negatives.
* **Prices.** Energy-Charts and SMARD day-ahead prices (CC BY 4.0) are planned for the market comparison and are not loaded yet.

### Method

Registry units are linked into sites by single linkage at 300 m<!-- docs/data_card_registry.md -->. Each site gets a chip with two monthly series. The Sentinel-2 series is a median of clear pixels selected with the scene classification layer, and it keeps the count of clear observations. The Sentinel-1 series holds VV and VH medians in dB from one fixed relative orbit. Features are spectral indices, contrast between the site centre and a surrounding ring, radar levels and change against the same month a year earlier. Each feature needs a written physical rationale.

The author labels site class and construction months in a local Streamlit app that hides all registry fields. A blind subset is relabelled to measure his consistency.

Detection starts with gradient boosting. A foundation model is tried only if that baseline leaves clear room for improvement. A strictly left-to-right four-state hidden Markov model dates the phases, and Bayesian online change-point detection runs alongside it. Missing months are modelled, not interpolated. Lead time is the registry date minus the detected start. It is estimated with methods that handle interval censoring, sites not yet registered and truncation at the export date.

### How the work is kept honest

* **Frozen plan.** The analysis plan was written and frozen with a stored hash before any label or model output existed. Any change goes into a deviations log.
* **Validation design.** Validation uses spatial blocks, a locked test fold and a temporal hold-out on the most recent year of imagery.
* **No registry data in the models.** Registry dates, status and capacity cannot enter detection. Code enforces this with an allow-list and a deny-list, both covered by tests. Registry dates are joined only after the model is frozen.
* **Independent review.** An independent reviewer gets the outputs and the specification but not the builders' reasoning, and reruns the tests. The reviews found a wrong Sentinel-1 orbit formula and results derived from the restricted orthophotos, and both were fixed. After the orbit fix, 0 of 83,262 radar scenes lie on a different orbit from the rest of their series<!-- results/imagery/s1_orbit_consistency.csv -->.
* **Checks against official figures.** Registry totals are compared with published statistics. Operating battery capacity rebuilt at a BNetzA reference date is 2.30 GW, against a published 2.4 GW<!-- results/registry/comparison_official_statistics.csv -->.
* **Traceable numbers.** Every number traces to a file and is labelled observed, detected or modelled.
* **Aggregated results only.** Results are published only in aggregated form, with no coordinates and no security-relevant detail.

### Status and next steps

Phases 0 to 2 are done:

* **Pilot set.** It holds 50 registry sites<!-- results/registry/pilot_v1_summary.csv --> and 100 negatives<!-- results/registry/negatives_v1_summary.csv -->.
* **Sentinel series.** Sentinel-1 series exist for 145 pilot chips<!-- results/imagery/pilot_v1_chip_summary.csv -->. Sentinel-2 series for most of them are still to be fetched within the free quota.
* **Orthophotos.** All 50 pilot sites have an orthophoto chip, and 38 of these have a known flight day<!-- results/imagery/dop_pilot_v1_coverage.csv -->.
* **National scan benchmark.** A streaming scan of one small state over one year read 1.91 GB in 5.3 minutes (measured)<!-- results/imagery/scan_benchmark.md -->. Scaled by area, all of Germany would need about 1.8 TB and 82 hours per year (modelled)<!-- results/imagery/scan_benchmark.md -->.

In progress: the feature set and the signature document, a first labelling queue of 410 chips<!-- results/labels/queue_round1_summary.csv --> with its imagery, and the Earth Engine chip backend.

Next steps:

* The author labels the first round, including a blind relabel subset.
* Phase 4 runs detection and timelines in both tracks and estimates lead time.
* Phase 5 covers discovery, the pipeline gap and capacity scenarios.
* Phase 6 adds the descriptive market link.

## 5. CV bullet drafts

**Variant A (technical)**

* Built a registry ground truth from the full Marktstammdatenregister export by grouping 1,392 battery units and 7,742 ground-mounted PV units into 1,241 and 5,790 sites<!-- results/registry/registry_sites_summary.csv -->. Rebuilt operating battery capacity at a BNetzA reference date: 2.30 GW against a published 2.4 GW<!-- results/registry/comparison_official_statistics.csv -->.
* Built Sentinel-1 and Sentinel-2 chip pipelines on Planetary Computer and Sentinel Hub with SCL cloud masking and one fixed radar orbit per site (0 of 83,262 scenes on another orbit<!-- results/imagery/s1_orbit_consistency.csv -->), plus a WMS orthophoto pipeline for the states with open aerial imagery.
* Pre-registered the evaluation (spatial block cross-validation, locked test fold, temporal hold-out, censored lead-time estimation) and built the gradient-boosted site detector it will evaluate (not yet trained on real labels) [needs result from Phase 4: recall and precision in the largest size class per track; minimum detectable site size].

**Variant B (energy and trading roles)**

* Reconstructed German large-battery capacity from the national registry (2.30 GW operating against BNetzA's published 2.4 GW at the same date<!-- results/registry/comparison_official_statistics.csv -->). Found 753 of 1,392 battery units of at least 1 MW still registered as planned<!-- docs/data_card_registry.md -->.
* Built the method to date battery and solar park construction from free satellite imagery and to measure the lead over registry commissioning [needs result from Phase 4, then rewrite as achieved: median lead time in months with interval; share of sites with zero or negative lead].
* Planned: compare battery capacity under construction with 2025 grid connection commitments [needs result from Phase 5: ratio with interval] and relate operational battery capacity to day-ahead price spreads descriptively [needs result from Phase 6: adjusted association, no causal claim].

## 6. Skills and tools used in the repository

* **Languages and tooling:** Python 3.12, JavaScript (Sentinel Hub evalscripts), uv with a lock file, Make, pytest, ruff.
* **Geospatial and imagery libraries:**
  * rasterio, xarray, Zarr and pyproj
  * geopandas, shapely and affine
  * pystac-client and planetary-computer
  * Earth Engine Python API (backend in progress)
  * scikit-image (morphology for the orthophoto footprint proposal tool)
  * osmium (OSM extract), Pillow
* **Data and analysis libraries:** pandas, NumPy, SciPy, PyArrow and Parquet, scikit-learn (nearest-neighbour search), matplotlib.
* **Application:** Streamlit, used for the local labelling app.
* **Data platforms and sources:**
  * Microsoft Planetary Computer (STAC, cloud-optimised GeoTIFF reads)
  * Copernicus Data Space Ecosystem (Sentinel Hub Process API)
  * Google Earth Engine (Community tier)
  * state orthophoto WMS services
  * Marktstammdatenregister bulk export
  * OpenStreetMap (Overpass, Geofabrik)
  * ESA WorldCover
* **Methods:**
  * STAC search and windowed COG reads
  * SCL cloud masking and monthly median compositing
  * orbit-consistent Sentinel-1 stacking
  * single-linkage spatial grouping of registry units into sites
  * stratified sampling by land cover
  * streaming scan design with quota and byte logging
  * pre-registration of the analysis plan
  * leakage guards (feature allow-list and deny-list) with unit tests

## Gaps

1. **CV A, bullet 3.** Detector recall and precision by track, and the minimum detectable site size. Filled in Phase 4.
2. **CV B, bullet 2.** Median lead time, its interval, and the share of zero or negative leads. Filled in Phase 4.
3. **CV B, bullet 3, first part.** The ratio of capacity under construction to commitments, with its interval. Filled in Phase 5.
4. **CV B, bullet 3, second part.** The spread association. Filled in Phase 6.
5. **Phase 3 numbers.** The count of labelled sites and the blind relabel agreement. Filled at the end of Phase 3 from `results/labels/relabel_agreement.csv`.
6. **Track comparison and decision table.** Not mentioned beyond the design. Filled in Phase 4.
7. **Motivation placeholder** in the detailed description. The author writes it.
