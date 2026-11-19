# CLAUDE.md

Working rules for "Watching the Build-out". Condensed from `KICKOFF.md`, which is the
full specification and must not be edited. If this file and `KICKOFF.md` disagree, `KICKOFF.md` wins.

## Project

Detect construction and completion of utility-scale battery storage (BESS, from 1 MW) and
ground-mounted solar parks (from 1 MWp) in Germany from free imagery, measure the lead time
over the Marktstammdatenregister (MaStR), and turn the observed pipeline into capacity scenarios.

- Track A: Sentinel-1 and Sentinel-2 only, all of Germany, fully automatic.
- Track B: Sentinel for timing plus open state orthophotos (DOP, 20 to 40 cm) for identity and size.
- Both tracks use the same labelled test sites, spatial blocks and metrics. Neither is a fallback.
- Hypotheses H1 to H5 are in `KICKOFF.md` Section 2.3. Test them, do not assume them.

Standard: a remote sensing scientist would not dismiss it and a power trader would find it useful.
Correct beats impressive.

## Non-negotiable rules

1. **No invented numbers.** Every number in a report, figure or text comes from code in this
   repository and traces to a file. Never fill gaps from memory.
2. **Verify first.** Anything marked *(verify)* is a working assumption until a primary source
   confirms it. Sources go in `docs/research/`. The register of verify items is in `docs/assumptions.md`.
3. **Assumptions register.** Every modelling assumption goes in `docs/assumptions.md` with value,
   source, plausible range and the sensitivity test that covers it.
4. **Label every quantity** as observed (registry, market data), detected (model output from
   imagery) or modelled (nowcast, scenario). Never present detected or modelled as observed.
5. **Responsible scope.**
   - Utility-scale commercial infrastructure only. No residential rooftops, private homes or
     anything that identifies private individuals. Do not geocode private persons.
   - Publish aggregates (federal state, district, month). Single sites only as illustrations and
     only if already public through MaStR, OSM or press coverage.
   - No security-relevant site detail (fencing gaps, access points, protective equipment). No
     ranking of sites by grid criticality. No combination of detections with grid topology that
     resembles a target list. OSM grid features are a coarse prior or context only.
   - If a task drifts that way: stop, do not do it, log it in `docs/STATUS.md`.
6. **Licences.** Respect Copernicus, ODbL, MaStR, Energy-Charts, SMARD, DOP and model licences.
   Never scrape basemaps whose terms forbid it. Never use the fee-based BKG mosaic.
   Record every source in `docs/data_sources.md` before using it.
7. **Secrets.** Credentials live only in `.env` (git-ignored). The author fills it in himself.
   Never ask for credentials in chat, never read `.env` values into the conversation, never print
   them. Code reads them from the environment at runtime (`python-dotenv`).
8. **Data location.** The repository is on the Desktop and may sync to iCloud.
   `data/raw`, `data/chips`, `data/processed`, `data/checkpoints` are symlinks to
   `~/Data/Power_Grid/`. Only code, documents, small result tables, labels and figures stay in
   the repository. `data/labels/` stays inside the repository.
9. **Paths.** Quote paths in shell commands and Makefile rules. In code, import paths from
   `bo.paths` (pathlib, relative to the repository root). No hard-coded absolute paths.
10. **Reproducibility.** Pinned environment (`uv.lock`), fixed seeds (`bo.paths.SEED`), immutable
    raw data, cached chip store, derived data rebuildable with one command (`make <stage>`).
11. **Tests.** Unit tests for index calculations, cloud masking, coordinate transforms, chip
    extraction and change-point code. Loaders get schema and range checks. Run `make test` before
    every phase report.
12. **Compute and cost.** CPU-feasible methods first. Stream or process server-side for large areas.
    Stop and ask before paid GPU time, before exceeding any free quota, and before any download
    above 50 GB. Log quota use.
13. **Stop conditions.** Stop and report if a data source is unavailable or forbids our use; do not
    silently substitute. Stop if a result looks too good to be true: suspect leakage.

## Method guards

- **Circularity guard.** Detection and timeline models never use registry dates as inputs.
  Registry dates serve only to measure lead time afterwards.
- **Leakage guard.** Spatial block cross-validation (blocks of about 50 km or by federal state)
  plus a temporal hold-out of the most recent 12 months. One site never sits in both train and test.
- **Missing months** (cloud, snow) are modelled explicitly, never interpolated away.
- **Sentinel-1** uses one fixed relative orbit per site. Do not mix orbits in one series.
- **Super-resolution** output is a model feature only, never evidence of what is on the ground.
- **Market link** is descriptive. No causal claims; name the remaining confounders.
- **Pre-registration.** Analyses go into `docs/analysis_plan.md` before results are inspected.
- Intervals everywhere: block bootstrap or Bayesian.

## Orchestration

- The main session is the orchestrator: plan, decompose, delegate, integrate, decide.
- One responsibility per subagent. Briefs are self-contained: goal, input paths, output paths,
  acceptance criteria, constraints. Subagents do not share context.
- Subagents communicate through files: research in `docs/research/`, code in `src/`, data in
  `data/`, results in `results/`, reviews in `docs/reviews/`.
- Each subagent returns at most 300 words: what it did, file paths, key numbers with file
  references, open problems, confidence.
- Run independent work in parallel.
- `red-team-reviewer` gets outputs and the specification only, never the builder's reasoning, and
  never reviews its own work.
- If a Sonnet agent fails review twice, reassign the task to an inherit-model agent.
- Keep `docs/STATUS.md` current: phase, task, owner, status, blockers, decisions.

| Model | Agents |
|---|---|
| inherit | `remote-sensing-physicist`, `ml-engineer`, `changepoint-statistician`, `market-analyst`, `red-team-reviewer`, `writer` |
| sonnet | `literature-scout`, `registry-data-engineer`, `imagery-engineer`, `orthophoto-engineer`, `labeling-tool-builder`, `figure-maker` |

## Phases

One phase at a time. After each phase, report (format below) and wait for the author's approval.

0 setup and research brief · 1 registry ground truth · 2 imagery pipelines (parallel with 1) ·
3 physics features and labelling · 4 detection and timelines, MVP cut · 5 discovery, pipeline and
scenarios · 6 market link · 7 independent review and write-up · 8 polish.
Acceptance criteria per phase are in `KICKOFF.md` Section 7.

## Phase report format

1. What was done, in five sentences or fewer.
2. Key results, each with its file path.
3. Decisions made and assumptions added, with links to the register.
4. Open problems, labelling tasks for the author, anything needing his decision.
5. Plan for the next phase with estimates of effort, token use and imagery quota use.

## Layout and commands

```
src/bo/{data,imagery,features,models,timeline,market}/   code
app/            labelling app          tests/        pytest
data/labels/    author labels (in repo; other data/* are symlinks)
results/        small result tables    figures/      vector + PNG
docs/           STATUS, assumptions, analysis_plan, data_sources, research/, reviews/, paper/
notebooks/      exploration only, nothing canonical
```

- `uv sync --frozen` builds the environment. Add packages with `uv add <pkg>` so `uv.lock` stays pinned.
- `make test` runs the suite, `make lint` runs ruff, `make <stage>` runs a pipeline stage.
- Commit only when the author asks.

## Writing rules for anything published under the author's name

Paper, summary, README and CV text follow `KICKOFF.md` Section 8:

- No dashes as punctuation (no em dash, en dash, or hyphen used as a dash). Rewrite the sentence.
  Hyphens inside compound words are fine.
- Direct, grounded prose. No filler, no AI-sounding constructions, no colon that only restates.
- No arguing for the author's qualifications.
- Every sentence must mean something exact, have a meaningful opposite, and not fit any other project.
- State limitations plainly. Prefer understatement.
- Leave the motivation paragraph as a placeholder for the author.
- Every number cites its results file in an HTML comment.
