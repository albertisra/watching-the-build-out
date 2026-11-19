# Labels

Written by the labelling app (`make label`, `app/README.md`). Plain CSV, append-only: rows are never edited
or deleted, so the files diff cleanly in git. Back up by committing `data/labels/`.

## `labels.csv` (one row per decision, schema version 3)

| Column | Meaning |
|---|---|
| `label_id`, `schema_version` | 12-character random ID of the row; `3` |
| `record_type` | `label` (pass 1, Sentinel only, immutable, never voided), `dop_review` (pass 2, after the DOP chip was shown) or `void` (cancels a `dop_review` row named in `voids_label_id`) |
| `pass_id`, `pass1_label_id` | `pre_dop` or `post_dop`; a pass-2 row names the pass-1 row it follows |
| `queue_id`, `labeller_id`, `timestamp_utc`, `app_version` | item key (also the chip-store name), who, ISO 8601 UTC, `bo.labelling.APP_VERSION` |
| `stratum` | queue stratum, looked up from `queue_round1_strata.parquet` when the row is written. The app never holds it and never shows it |
| `is_relabel` | `True` for a blind relabel (same item again, earlier label not shown; no DOP pass) |
| `relabel_after_dop_seen` | on relabel rows, `True` if the labeller had already done pass 2 for that item, so its DOP chip was seen and the relabel is not Sentinel-only. `False` otherwise and on older files |
| `site_class` | `battery`, `PV`, `battery+PV`, `other`, `none`, `unsure` |
| `colocated` | other technology visible in the central area: `none`, `pv`, `battery`, `other` (plan 2.6). `pv` or `battery` makes that technology active and gives it its own dates |
| `bat_*`, `pv_*` events | per active technology and event (`clear`: first month of visible clearing or ground works, `struct`: first month of visible structures, containers or panel rows, `complete`): `<tech>_<event>_month` is `YYYY-MM`, `before_series`, `after_series` or `not_visible` (the phase never shows as a separate step); `<tech>_<event>_earliest` and `_latest` are the optional bracket (`YYYY-MM`, earliest <= month <= latest, only with a `YYYY-MM` month). Required for the active technologies of a positive class; empty for inactive ones |
| `start_month`, `complete_month` | derived coarse summary (earliest first works, latest completion) used by the blind-relabel agreement |
| `confidence` | 1 (low) to 3 (high), one per item |
| `dop_identity`, `dop_footprint` | pass 2 only: `confirms`, `contradicts`, `cannot_tell`; `matches`, `differs`, `cannot_tell` |
| `note` | free text, single line |
| `chip_stores` | chip store names, platform, chip code version; `dop=` is `chip`, `none` or `restricted` (use-restricted state, DOP never shown) |
| `revealed_before` | `True` if registry facts had been revealed for the item before this row (a reveal now locks the item, so this stays `False` in practice) |
| `registry_date_exposed` | `True` if the author saw this item's MaStR commissioning date in a signature figure before labelling (`results/labels/registry_date_exposed_queue_ids.csv`). Shown in no UI. Exclude from primary H2 and H3 or report a sensitivity |

Read rule: pass 1 rows cannot be voided. A second non-relabel pass-1 row for the same item and labeller is refused
(`DuplicatePass1Error`), so there is one first label per (`queue_id`, `labeller_id`). `bo.labelling.labels.read_labels`
excludes blind relabel rows (`is_relabel`) and returns that first label; relabels are read through `effective_rows`
for agreement only. `read_two_pass` returns `pre_dop_*` and `post_dop_*` columns side by side; the
pass-1 columns alone are the Sentinel-only label set for the Track A versus Track B comparison.
`bo.labelling.schema.phase_sequence(row, "bat" or "pv", months)` turns the events into the monthly 0 U, 1 Cl, 2 UC,
3 Co sequence for `bo.timeline.hmm.fit_supervised` (-1 where undetermined). The consistency check pairs the first
label with the first blind relabel (`bo.labelling.agreement.agreement`; `agreement_by_dop_exposure` splits the pairs by `relabel_after_dop_seen`).

## `reveals.csv`

One row per reveal of registry facts (`queue_id`, `labeller_id`, `timestamp_utc`, `app_version`). Reveals exist only in the
separate review mode (`make review`), never in the labelling session. A reveal locks the item: no further rows for it
are accepted from that labeller, and it leaves the blind relabel set.

Quantities in these files are the author's labels (observed by eye on imagery; they are the gold standard, not model output).
