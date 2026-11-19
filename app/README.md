# Labelling app

Quick start (the app runs offline on `127.0.0.1`, reads chips from `data/chips/`, writes `data/labels/`):

1. `make label` opens the app in the browser. Enter your labeller ID in the sidebar.
2. `make label` first runs `make queue-view`, which writes `data/processed/labels/queue_round1_view.parquet` (queue_id, lat, lon, bundesland) and a DOP index keyed by queue_id. The app reads only these two files, in file order (already a seeded shuffle), and the Earth Engine stores `data/chips/ee_r1` (one platform for the whole round). Items are keyed by queue_id, which is never shown. Only if the queue file is missing does a development queue from the pilot tables appear (the sidebar says so). The app never loads the full queue, the strata file, registry keys, OSM category or land cover; the stratum is looked up from the strata file only when a label row is written. Each item opens on the first month with clear Sentinel-2 observations; the whole series stays navigable.
3. Look at the filmstrip (S2 true and false colour, S1 VV and VH; `n` = clear observations, B/D = quality flags).
4. Class: `b` battery `p` PV `c` battery+PV `o` other `n` none `u` unsure. `w` cycles "other technology visible nearby"
   (none, PV, battery, other); a visible co-located technology gets its own dates (`t` switches technology).
5. Events per technology: `s` clearing / ground works here, `d` structures here, `e` complete here. `h` before series,
   `j` after series, `m` not visible (focused event; `f` cycles the focus), `a` / `l` optional earliest / latest month,
   `0` all events before series, `9` all after series, `x` clear focused, `X` clear all. Left/right move the cursor, up/down 12 months.
6. `1 2 3` confidence. Click outside the note box before using keys.
7. Pass 1 (Sentinel only): `Enter` commits the answers. They are written immutably; there is no undo.
   Pass 2 (only where a DOP chip exists; never for Mecklenburg-Vorpommern): the DOP chip appears. `y` identity and footprint
   confirmed, `k` contradicts, `q` cannot tell, `i` footprint answer, revise answers if needed, `Enter` saves and goes on.
8. The labelling session is blind: no registry data, no stratum, no queue ID or site ID, no size, and no reveal button.
   Registry facts exist only in the separate review mode (`make review`), which locks an item's labels before it shows anything.
9. About 10 % of already labelled sites return later without their earlier label. Agreement:
   `uv run python -c "from bo.labelling import labels, agreement as a; print(a.agreement_by_dop_exposure(labels.effective_rows(labels.read_all_rows())))"` (a relabel after the labeller did pass 2 for that item is flagged `relabel_after_dop_seen` and is not a Sentinel-only repeat)
10. Labels: `data/labels/README.md`. Back up by committing `data/labels/`.

DOP images show the flight date only when it is a known day.
Logic is in `src/bo/labelling/`, config in `app/config/labelling.toml`, tests in `tests/test_labelling*.py`.
