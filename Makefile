# One command per stage. Stages are filled in phase by phase.
.PHONY: signatures label review pilot help setup test lint queue-view scan chips-s1 chips-s2 registry chips features models-synthetic detect timelines scenarios market figures all

help:
	@grep -E '^[a-z-]+:.*##' "$(MAKEFILE_LIST)" | sed 's/:.*##/ -/'

setup: ## create the pinned environment from uv.lock
	uv sync --frozen

test: ## run the test suite (required before every phase report)
	uv run pytest

lint: ## static checks
	uv run ruff check src tests

registry: ## registry sites, capacity series, data card; newest export, or EXPORT=path/to.zip
	uv run python -m bo.data.registry $(if $(EXPORT),"$(EXPORT)")

chips: ## chip stores for pilot and negative sites; START/END/IDS optional, e.g. make chips START=2024-01-01 END=2025-12-31
	uv run python -m bo.imagery.cli chips --sites data/processed/pilot/pilot_sites_v0.parquet data/processed/pilot/negatives_v0.parquet --start $(or $(START),2024-01-01) --end $(or $(END),2025-12-31) $(if $(IDS),--ids $(IDS)) --limit-gb $(or $(LIMIT_GB),10)

chips-s1: ## Sentinel-1 chips on Sentinel Hub for pilot v1 and negatives v1 (resumable, hard stop at 60 percent of the monthly quota)
	uv run python -m bo.imagery.shcli --sensor s1 --root data/chips/sh_v1_s1 --skip-roots data/chips/sh_v1 --stage sh_chips_s1

chips-s2: ## Sentinel-2 chips on Sentinel Hub, same sites; skips chips already stored, resumes after a quota stop
	uv run python -m bo.imagery.shcli --sensor s2 --root data/chips/sh_v1_s2 --skip-roots data/chips/sh_v1 --stage sh_chips_s2

queue: ## first-round labelling queue (needs `make registry`; Geofabrik extract in data/raw/osm/geofabrik/, WorldCover over the network)
	uv run python -m bo.data.queue $(if $(REFRESH_OSM),--refresh-osm)

queue-view: ## blind view of the queue for the labelling app (queue_id, lat, lon, bundesland; DOP index by queue_id); does not rebuild the queue
	uv run python -m bo.data.queue --view-only

scan: ## national scan benchmark on one state (default Bremen, 2024)
	uv run python -m bo.imagery.scan_cli --state $(or $(STATE),Bremen)

features: ## monthly feature tables (allow-list columns only) for the Sentinel Hub and Planetary Computer pilot stores
	uv run python -m bo.features.build --name sh_v1 --roots data/chips/sh_v1
	uv run python -m bo.features.build --name sh_v1_s1 --roots data/chips/sh_v1_s1
	uv run python -m bo.features.build --name pc_v0 --roots data/chips/v0
	uv run python -m bo.features.build --name ee_r1 --roots data/chips/ee_r1

models-synthetic: ## detector machinery on synthetic data only; writes results/models/synthetic_*.csv (not a result)
	uv run python -m bo.models.synthetic

signatures: ## signature figures, contrast and PSF fit, noise, minimum size prediction, cloud-mask and confuser checks
	uv run python -m bo.features.signatures
	uv run python -m bo.features.scl_did
	uv run python -m bo.features.confusers

detect timelines scenarios market figures: ## pipeline stages (not implemented yet)
	@echo "stage '$@' is not implemented yet; see docs/STATUS.md" && exit 1

all: registry chips features detect timelines scenarios market figures

pilot: ## redraw pilot v1 from the registry site table and recheck negatives (needs `make registry`)
	uv run python -m bo.data.pilot

label: queue-view ## start the labelling app (local, offline); see app/README.md
	uv run streamlit run app/label_app.py --server.address 127.0.0.1 --browser.gatherUsageStats false

review: ## post-labelling registry review (locks the labels of each item revealed); not for use while labelling
	uv run streamlit run app/review_app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
