# Decisions pending for the author (2026-11-19)

Nothing below has been applied. `docs/analysis_plan.md` is unchanged (hash in
`results/timeline/analysis_plan_v1_sha256.txt`); accepted items go into its deviations log (Section 13)
before any label is used for evaluation.

## Decided

1. **DECIDED 2026-11-19 (author): coarse-coordinate queue items.** Replace L1-0012 (1 decimal, about
   6.4 km uncertainty) with a seeded draw from the same stratum cell (new id L1-0411, since L1-0410 was already taken; logged in
   `results/labels/queue_round1_replacements.csv`). Keep L1-0138 (2 decimals, about 650 m) and exclude it
   from date metrics via the `coord_coarse` flag (still to be written into Section 13 with item 3).
2. **DECIDED 2026-11-19 (author): Mecklenburg-Vorpommern DOP.** Keep the downloaded chips and data on disk,
   but do not use them: not shown in the app, not used in Track B, nothing derived from them in `results/`
   or `figures/`. The author does not request permission from the state for now and may do so later.
   The existing guards (`bo.imagery.dop.restricted_states`, `drop_restricted`) stay in force.

## Analysis-plan deviations (Section 13)

3. **Label schema v3 mapping** (draft from the ml-engineer, fill the brackets):
   "2026-11-19, Sections 2.3/2.4/2.6: The app stores schema v3: per technology, clearing, structures and
   completion events, each with an optional earliest/latest bracket and its own confidence, plus
   before_series, after_series and not_visible. Targets are per technology; co-located items have no
   shared dates. Monthly y = 1 from the [clear/struct/complete] onset; brackets are handled by
   [point/unknown/midpoint]. Track A targets come only from pass 1 (Sentinel only). Track B targets come
   from [pass 1/pass 2]; items without pass 2 are [dropped/given pass 1]. Evaluation truth for the paired
   Track A vs B comparison is [X]. Items flagged registry_date_exposed (15, `results/labels/registry_date_exposed_queue_ids.csv`)
   and coord_coarse are [excluded/stratified]. Results seen: no."
4. **Common evaluation truth for the paired track comparison.** KICKOFF 6.0 counts DOP-contradicted
   Track A detections as errors, which argues for pass 2 as evaluation truth for both tracks, with a
   sensitivity analysis on pass 1. Recommendation: pass 2 as primary truth, pass 1 as sensitivity.
5. **Timeline simulation deviations P1 to P6** (`results/timeline/simulation_diagnosis.md`):
   P1 recovery threshold relative to the Bayes ceiling; P2 simulate the Erlang construction-phase variant;
   P3 drop BOCPD from the phase-recovery criterion; P4 judge NPMLE on bias and consistency, with
   acceleration; P5 clip lead intervals at their bound; P6 make the skip model primary if 20 % or more of
   starts skip clearing. Recommendation: accept P1, P3, P5; P2, P4, P6 are reasonable but your call.
   The combined-censoring NPMLE bias (about 3.3 SE) stays open before H3.

## Later

6. **Detector precision floor** (synthetic no-signal class flagged 66 of 111 negatives): decide before
   Phase 4 evaluation.
7. **Quota**: Sentinel Hub at 8,934 of the 9,500 PU cap for November; no further Sentinel Hub work
   until the December reset. Earth Engine about 70 of 150 EECU-h.
