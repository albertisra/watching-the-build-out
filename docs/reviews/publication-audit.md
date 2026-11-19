# Pre-publication audit (public GitHub repository)

Reviewer: red-team-reviewer, 2026-11-19. Scope: every file not excluded by `.gitignore`.
Method: `git ls-files --others --exclude-standard` run against a scratch git dir (the repository's own `.git`
has no commits and nothing staged) gave 409 committable files, 32.8 MB in total. Every `.env` value
was compared byte-wise against all 409 files by a script that prints key names only, never values.
I viewed the sanity panels and signature figures (samples: Q010, P040, P009, aligned_yoy, confusers).

## Summary of what is fine

* `.env` and `.env.*` are ignored (`.gitignore:2-3`); `.env.example` holds names only, no values.
* No `.env` value (CDSE_CLIENT_ID, CDSE_CLIENT_SECRET, CDSE_USERNAME, CDSE_PASSWORD, EE_PROJECT) occurs in
  any committable file: 0 hits. No `ghp_`, `sk-`, `AKIA`, private key blocks, or personal e-mail.
  The only e-mail address is the public office address `geodatenservice@laiv-mv.de` (`docs/research/dop_sources.md:245`).
* `data/raw`, `data/chips`, `data/processed`, `data/checkpoints` are ignored symlinks; `.venv`, caches,
  `.DS_Store` and `.claude/settings.local.json` are ignored. The `.git` directory has no commits, so there is no history to scrub.
* No operator names, person names or street addresses in `results/`, `figures/`, `docs/`, `tests/`, `app/`
  (grep for GmbH, KG, AG, Herr, Frau, street patterns, Betreiber, ABR/SME numbers: no hits). The registry
  loader does not extract operator names or IDs (`src/bo/data/registry.py:22`, `registry_report.py:336`).
* No per-site grid operator or voltage level in any committed file; `results/registry/registry_grid_coverage.csv`
  holds counts only. No criticality ranking, no substation join, no security detail in figures.
* No Mecklenburg-Vorpommern DOP image in `figures/` (all committed PNGs are Sentinel composites or plots;
  no DOP chip or thumbnail is committed). No MV row in the four `results/imagery/dop_*.csv` files or in
  `results/labels/dop_queue_round1_coverage.csv`.
* No file is above 5 MB. Largest: `results/registry/capacity_monthly_by_state.csv` (2.6 MB),
  `results/imagery/quota_log.csv` (1.3 MB). No parquet, tif, zarr, nc or checkpoint is committable.
* Sentinel credit "Contains modified Copernicus Sentinel data ..." appears on every figure sampled; OSM credit
  on figures that draw OSM outlines or OSM negatives.
* Sample recomputed: 83,262 S1 scenes with 0 on another orbit (`results/imagery/s1_orbit_consistency.csv`),
  145 pilot chips (`results/imagery/pilot_v1_chip_summary.csv`), 1,241 and 5,790 sites
  (`results/registry/registry_sites_summary.csv`), 2.30 GW against 2.4 GW
  (`results/registry/comparison_official_statistics.csv` row 1), fold 0 = 82 of 410
  (`results/timeline/split_v1_summary.csv`). All match the README and project description.

## Findings

### PUB-B1 (blocker). Values derived from the use-restricted MV orthophoto service are quoted in committed docs

* `docs/reviews/phase-2-r3.md:63`: footprint areas detected on 4 MV DOP chips (panel array, container row,
  site pad in m2). `docs/reviews/phase-2-r3.md:64`: MV flight-date ranges read from the restricted service.
* `docs/research/dop_sources.md:100`: GetFeatureInfo answer from `mv_dop_info` for a pilot-site location
  (Befliegungsjahr, Befliegungszeitraum day, Bildflug lot).
* `docs/STATUS.md:171`: "36 with flight date (BY 20, MV 4, ...)" (count of MV chips with a flight date; low content, but derived from the service).
* The author decided (`docs/decisions_pending.md:13`, `docs/STATUS.md:148`) that nothing derived from MV DOP is
  published; the README promises the same (`README.md:97`). The service licence allows internal use only
  (`docs/data_sources.md`, MV row).
* Fix: redact the numeric values in `phase-2-r3.md:63-64` (keep "MV footprint areas and flight dates were
  present; removed"), replace the GetFeatureInfo example in `dop_sources.md:100` with "a day-level flight date is
  readable" without the values, and change `STATUS.md:171` to drop the MV count. Alternatively exclude
  `docs/reviews/phase-2-r3.md` from the public tree.

### PUB-B2 (blocker). Per-site registry coordinates are committed, contradicting the published scope statement

* `results/registry/coarse_unit_site_shift.csv`: 12 rows, each with a MaStR unit number (`PV-SEE...`), old and
  new lat/lon to 6 decimals, capacity class proxy (`n_units`) and federal state. These are public MaStR fields
  for utility-scale PV, so the privacy risk is low, but the file is not an aggregate and not an illustration,
  and ground-mounted PV operators include natural persons (farmers) whose names MaStR hides for that reason.
* `README.md:147` says "Site coordinates stay under `data/` and are not committed";
  `docs/paper/project_description.md:66` says "Results are published only in aggregated form, with no coordinates".
  Both are false while this file is committed.
* Fix: move `coarse_unit_site_shift.csv` to `data/processed/registry/` (git-ignored) and commit only an aggregate
  (count of shifted sites and shift quantiles by precision class). Same for `docs/reviews/phase-3-prep.md:80`
  ("54.3 / 12.9" for queue item L1-0012; coarse, but a per-site coordinate) and `docs/reviews/phase-3-prep.md:233`
  and `docs/STATUS.md:251` (MaStR unit numbers tied to queue ids; see also PUB-M4).

### PUB-M1 (major). No licence file, no NOTICE

* No `LICENSE`, `NOTICE` or `CITATION.cff` exists; `README.md:151` says "Code licence: [author to choose]".
  Without a licence a public repository is all rights reserved, and readers cannot reuse the code.
* The committed result tables carry MaStR (dl-de/by-2.0), OSM (ODbL) and Sentinel-derived content; the
  attribution currently lives only in the README table.
* Fix: add `LICENSE` for the code (author's choice, for example MIT or Apache-2.0; note that the GPL/AGPL
  packages are not dependencies, `docs/data_sources.md` Software section), and a `NOTICE` (or `results/README.md`)
  stating that `results/registry/*` is "© Bundesnetzagentur, Marktstammdatenregister, dl-de/by-2.0, data
  modified", that `figures/` contain modified Copernicus Sentinel data, and which files contain OSM-derived values
  (see PUB-M3) under ODbL.

### PUB-M2 (major). Figures that draw MaStR dates or Planetary Computer RTC lack the required credit

* `figures/signatures/P009_series.png` (and the other non-queue site figures that draw the red dashed MaStR
  commissioning line, from `results/labels/registry_date_exposed_queue_ids.csv` these are the 5 of 20 not in the
  queue: P009, P011, P042, P044, P048) and `figures/signatures/aligned_yoy.png` ("months since MaStR commissioning")
  carry only the Sentinel and OSM credits, no MaStR/dl-de/by-2.0 credit.
* The P-series figures and P-series sanity panels state "Planetary Computer (S1 gamma0)" chips; per
  `docs/data_sources.md` the PC `sentinel-1-rtc` product is CC BY 4.0 and needs a credit to Microsoft and
  Catalyst in addition to the Copernicus line. `README.md:71-77` also omits this credit.
* Fix: add "Registry dates: © Bundesnetzagentur, MaStR, dl-de/by-2.0" to every figure that draws a registry
  field, and "S1 RTC: Microsoft Planetary Computer / Catalyst, CC BY 4.0" to figures built from PC RTC; add the
  RTC row to the README attribution table. Regenerate with `make signatures`.

### PUB-M3 (major). OSM-derived per-site values sit in mixed tables without a licence statement

* `figures/sanity/public_basis.csv` (20 rows: OSM way/relation ids, tags, match distance), and the `outline_m2`
  and `osm_power` columns of `results/features/contrast_at_best_psf.csv` (204 rows),
  `results/features/contrast_fit_all.csv` (1,836 rows) and the same files under
  `results/features/signatures_ee_r1_sigma0/` (270, 2,430 rows), `signatures_sh_pc_gamma0/` (204, 1,836 rows)
  and `signatures_2026-11-18_frozen/`. `docs/data_sources.md` (Registry outputs, OSM row) requires OSM-derived
  files to be kept apart from MaStR-derived data and released under ODbL.
* For 20 illustration sites this is very likely an insubstantial extract, so the risk is low, but the files need
  the attribution and a statement.
* Fix: either drop `outline_m2`/`osm_power` from the committed copies (keep them in `data/processed`), or
  declare these files ODbL with "© OpenStreetMap contributors" in the NOTICE from PUB-M1.

### PUB-M4 (major). Blindness: committed files expose registry timing for queue sites

The author must not open these before finishing round 1 (and the blind relabel subset):
* `results/features/stability_before_after.csv` (40 rows), `results/features/scl_did_site_period.csv` (60 rows),
  `results/features/signatures_ee_r1_sigma0/stability_before_after.csv` (30),
  `results/features/signatures_sh_pc_gamma0/stability_before_after.csv` (40), and the frozen copies under
  `results/features/signatures_2026-11-18_frozen/`: before/after and pre/post periods split at the MaStR
  commissioning month, with month counts, for pilot ids that `results/features/signature_sites_fold0.csv` maps to
  queue ids (15 queue sites, for example Q010 = L1-0088: 13 months before, 25 after). From these the
  commissioning month of a queue site can be read off.
* `docs/STATUS.md:251` and `docs/decisions_pending.md:9-11`: queue item L1-0411 with its MaStR unit number,
  status "In Betrieb" and commissioning bucket "2025_2026".
* `docs/reviews/phase-3-prep.md:233`: a MaStR unit number in the same context.
* `figures/signatures/*`, `figures/signatures/ee_r1/*` and `figures/sanity/*` for the 15 ids in
  `results/labels/registry_date_exposed_queue_ids.csv`: the queue-site figures say "Registry fields not drawn", but
  they show the imagery-derived step (for example the VV rise in `figures/signatures/Q010_series.png`), which
  anchors the author's labels for those items.
* Publishing does not change the author's exposure (the files exist locally either way). Fix: list these paths
  in `data/labels/README.md` as "do not open before round 1 is complete", keep the 15 exposed ids excluded from
  the label-agreement and lead-time metrics as already planned, and redact the queue id to MaStR number link in
  `STATUS.md:251`.

### PUB-M5 (major). Planned results presented as achieved in the CV drafts

* `docs/paper/project_description.md:92`: "trained a gradient-boosted site detector reaching [needs result ...]";
  only the synthetic machinery exists (`results/models/synthetic_*.csv`, `"data"` column synthetic).
* `docs/paper/project_description.md:97-98`: "Dated battery and solar park construction ... and measured the
  lead ...", "Compared battery capacity under construction ...", "Related operational battery capacity ...".
  None of this exists yet (`README.md:5`, `README.md:57-59`).
* `docs/paper/project_description.md:66`: "Results are published only in aggregated form, with no coordinates"
  (false, PUB-B2).
* Fix: keep the drafts out of the public tree until Phase 4 to 6 fill them (move to a local, git-ignored
  `docs/paper/drafts/`), or rewrite them in the future tense as planned work. The surrounding text of the file is
  accurate (`project_description.md:12`, `:22`).

### PUB-m1 (minor). Absolute home path that reveals the user name

* `KICKOFF.md:10` and `KICKOFF.md:89` contain the full path `/Users/<user name>/Desktop/...`. No code file holds an
  absolute path (`src/bo/paths.py` uses relative paths; `~/Data/Power_Grid` appears only as documentation).
* `KICKOFF.md` must not be edited (`CLAUDE.md`). Fix: the author decides whether to publish `KICKOFF.md` as is,
  or keep it out of the public tree (add to `.gitignore` before the first commit) and point the README to
  `CLAUDE.md` instead.

### PUB-m2 (minor). Possibly real site coordinate in a test fixture

* `tests/test_imagery_core.py:77`: `lon, lat = 11.669333, 48.030372` (six decimals; `tests/test_dop.py:192` uses
  48.03, 11.67 "Bayern"). It looks like a registry site position.
* Fix: replace with a synthetic coordinate (for example 11.67, 48.03) or confirm it is a public MaStR/OSM site.

### PUB-m3 (minor). README status slightly overstates Phase 2

* `README.md:55` "done, reviewed" and `project_description.md:22` "Phases 0 to 2 are complete" against
  `docs/STATUS.md:12`: Phase 2 signed off "apart from author-pending items", Sentinel-2 pilot chips scheduled for
  December, DOP table gaps waiting for the author.
* Fix: "done, reviewed; Sentinel-2 pilot chips and DOP table gaps pending".

### PUB-m4 (minor). Duplicate and superseded result sets

* `results/features/signatures_2026-11-18_frozen/` (17 files) duplicates 15 files in `results/features/`
  byte-for-byte or nearly; `results/timeline/*_run1_unclipped.csv` are superseded runs. Not a licence or privacy
  issue, but they make traceability harder for a reader.
* Fix: keep them (they document the freeze) but add a one-line `README.md` in each folder saying which set is
  canonical.

### PUB-m5 (minor). Agent and orchestration files will be public

* `.claude/agents/*.md` (13 files), `CLAUDE.md` and `KICKOFF.md` describe the multi-agent build process and
  the CV and application purpose (`KICKOFF.md:478`, `:492`; `.claude/agents/project-narrator.md:27`).
  Nothing secret, but the author should decide consciously whether a job-application reader sees them.

### PUB-m6 (minor). Size

* Total committable size 32.8 MB in 409 files; the 57 PNGs in `figures/` account for 24.4 MB
  (`figures/sanity/` 20 panels of 0.3 to 1.0 MB). Acceptable for git; no file exceeds 5 MB. If the figures are
  regenerated often, consider Git LFS or committing only the final figure set.

## Tests

`uv run pytest` rerun by the reviewer on 2026-11-19: exit code 0, 405 passed, 1 skipped, 4 xfailed, 0 failed (184 s; counted from the progress dots, the summary line is suppressed by `addopts = "-q"` plus `-q`).

## Verdict

Not ready to publish. Blocking:
1. PUB-B1: redact MV DOP-derived values in `docs/reviews/phase-2-r3.md:63-64`, `docs/research/dop_sources.md:100`,
   `docs/STATUS.md:171`.
2. PUB-B2: move `results/registry/coarse_unit_site_shift.csv` to `data/processed/` (commit an aggregate), and
   correct `README.md:147` and `docs/paper/project_description.md:66` or make them true.

Before publishing also fix PUB-M1 (LICENSE and NOTICE), PUB-M2 (figure credits), PUB-M5 (CV drafts) and decide
PUB-m1 (`KICKOFF.md` home path).
