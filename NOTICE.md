# Notice: data credits for files in this repository

The code licence is in `LICENSE`. This notice covers the third-party data from which the tables in `results/`
and the figures in `figures/` are derived. The full list of sources, terms and access routes is in
`docs/data_sources.md`, and the attribution table is in `README.md`.

## Credits that apply to the committed tables and figures

* **Copernicus Sentinel-1 and Sentinel-2.** Contains modified Copernicus Sentinel data 2015 to 2026. Applies to
  every image panel, signature figure and feature table derived from Sentinel imagery.
* **Microsoft Planetary Computer, `sentinel-1-rtc`.** Sentinel-1 radiometric terrain correction processed by
  Catalyst, made available by Microsoft under CC BY 4.0. Applies to the pilot radar series (`v0` and
  Planetary Computer signature results and figures). Data modified (monthly medians, chip extraction).
* **Marktstammdatenregister (MaStR), Bundesnetzagentur.** © Bundesnetzagentur, Marktstammdatenregister,
  Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0, https://www.govdata.de/dl-de/by-2-0), data modified
  (filtered, aggregated, grouped into sites). Applies to `results/registry/`, to registry dates drawn in the
  signature figures of sites that are not in the labelling queue, and to every table that carries a registry
  date, status or capacity.
* **OpenStreetMap.** © OpenStreetMap contributors, Open Database Licence 1.0
  (https://www.openstreetmap.org/copyright). Applies to OSM-derived columns such as `outline_m2` and
  `osm_power`, to `figures/sanity/public_basis.csv` and to the outlines of public illustration sites. These are
  Produced Works under the ODbL; the underlying OSM extracts are not redistributed here.
* **ESA WorldCover 2021 v200.** Contains ESA WorldCover data © ESA WorldCover project 2021 / Contains modified
  Copernicus Sentinel data (2021) processed by ESA WorldCover consortium, CC BY 4.0. Applies to land cover
  strata of random negative points.
* **State orthophotos (DOP).** No orthophoto image is committed. Tables that describe DOP coverage or flight
  dates credit the state survey offices listed in `README.md`. Orthophotos of Mecklenburg-Vorpommern are
  restricted to internal use; nothing derived from them is committed.
* **Google Earth Engine.** Used as a processing platform on the non-commercial Community tier; no Earth Engine
  imagery is re-hosted. Cloud Score+ by Google, CC BY 4.0.

## What is not in this repository

Raw data, image chips, per-site coordinates and processed registry tables stay outside version control
(`data/raw`, `data/chips`, `data/processed`, `data/checkpoints`). Results are published as aggregates or as a
small number of illustration sites that are public through MaStR or OpenStreetMap.
