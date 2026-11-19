"""Author labels (schema v3) to per-month detector targets per technology (plan 2.3, 2.4, 2.6).

Reading (`primary_labels`)
--------------------------
Labels are read through `bo.labelling.labels`: voided rows dropped, blind relabels (`is_relabel`) dropped *before*
the "latest pass-1 row per item and labeller wins" rule (relabels serve the agreement check only), then the pass-2
row (`dop_review`) that names the chosen pass-1 row is attached. The caller must say which pass the targets come
from; there is no default:

* ``label_pass="pre_dop"``: pass-1 answers (Sentinel only). The only pass allowed for ``track="A"``.
* ``label_pass="post_dop"``: pass-2 answers (after the DOP chip was shown). Allowed for ``track="B"`` only. Items
  without a pass-2 row (DOP use-restricted state, no chip, pass 2 not yet done) are handled by the required
  ``missing_post_dop`` argument: ``"drop"`` or ``"use_pre_dop"``; ``label_pass_used`` records the source per item.

``registry_date_exposed`` (pass-1 flag OR pass-2 flag), ``coord_coarse`` (pass-1 flag OR pass-2 flag: the item's
registry coordinate was rounded to 1 or 2 decimals, schema v3), ``dop_identity`` and ``dop_footprint`` are carried
through as metadata so evaluation can exclude or stratify. The per-event confidences ``<tech>_<event>_conf`` (schema
v3) come from the same pass as the events. All of these are evaluation metadata only, never model inputs
(`bo.models.guards.LABEL_METADATA_COLUMNS` refuses them by name), and Track A targets never depend on them. Items
whose chosen class is ``unsure`` give no target.

Mapping (`monthly_targets`)
---------------------------
Each technology (``battery`` from the ``bat_*`` events, ``pv`` from the ``pv_*`` events) is its own target with its
own events; a co-located item never shares one date pair between technologies (plan 2.6). The technologies present
are `bo.labelling.schema.active_techs(site_class, colocated)`; an absent technology is 0 in every month.

For a present technology the three events (clear, struct, complete) define, for each k in 1..3, the first month
with state >= k (states 0 U, 1 Cl, 2 UC, 3 Co, as in `schema.phase_sequence`). A month t is 1 for level k if t is at
or after that month, 0 if before, NaN if the label does not fix it. ``before_series`` is minus infinity,
``after_series`` plus infinity; ``not_visible`` makes the level coincide with the next event (clearing with
structures, structures with completion) and a not-visible completion never happens; an undetermined (empty) event
is bounded by its determined neighbours. Levels are made consistent (state >= k implies state >= j for j < k).

Two mapping choices are parameters without defaults, because the author decides them in plan Section 13 before
any evaluation (assumption M1; M2 is void under schema v2 because each technology has its own dates):

* ``onset``: which level makes ``y = 1``. ``"clear"`` (first visible site works, Cl months positive; the old M1
  rule), ``"struct"`` (first visible structures, UC and Co positive; the literal reading of plan 2.4) or
  ``"complete"`` (Co only; the old M1 alternative).
* ``brackets``: how the optional earliest/latest brackets enter. ``"point"`` ignores them; ``"unknown"`` makes the
  months inside [earliest, latest) of an event NaN for that level; ``"midpoint"`` moves the event to the floor of
  the bracket midpoint (plan 5 sensitivity).

``state`` (0 to 3, NaN where not fixed) is returned alongside ``y`` for the timeline models. ``onset_conf`` (1 to
3, NaN if not fixed) is the labeller's confidence in the event that defines the onset level: the onset event itself,
or, if it is ``not_visible``, the next visible event it coincides with (a not-visible completion keeps its own
confidence). It is NaN for an absent technology or an undetermined onset event. ``coord_coarse`` is carried per row.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from bo.labelling.labels import effective_dop_rows, effective_rows, read_all_rows
from bo.labelling.schema import (
    AFTER_SERIES,
    BEFORE_SERIES,
    CONF_COLUMNS,
    CONTENT_COLUMNS,
    EVENTS,
    NOT_VISIBLE,
    SCHEMA_VERSION,
    active_techs,
    month_index,
    validate_events,
)

from .design import TECHNOLOGIES

Track = Literal["A", "B"]
LabelPass = Literal["pre_dop", "post_dop"]
Onset = Literal["clear", "struct", "complete"]
Brackets = Literal["point", "unknown", "midpoint"]
MissingPostDop = Literal["drop", "use_pre_dop"]

TRACK_PASSES: dict[str, tuple[str, ...]] = {"A": ("pre_dop",), "B": ("post_dop", "pre_dop")}
ONSETS: tuple[str, ...] = ("clear", "struct", "complete")
BRACKETS: tuple[str, ...] = ("point", "unknown", "midpoint")
TECH_CODE: dict[str, str] = {"battery": "bat", "pv": "pv"}  # design technology -> schema prefix
EVENT_FIELDS = [c for c in CONTENT_COLUMNS if c.startswith(("bat_", "pv_")) and c not in CONF_COLUMNS]
LABEL_KEEP = ("site_class", "colocated", *EVENT_FIELDS, *CONF_COLUMNS, "confidence", "labeller_id", "label_id",
              "label_pass_used", "registry_date_exposed", "coord_coarse", "dop_identity", "dop_footprint", "track")
TARGET_COLUMNS = ["site_id", "month", "technology", "y", "state", "present", "colocated_target", "site_class",
                  "colocated", "confidence", "onset_conf", "registry_date_exposed", "coord_coarse", "label_pass_used",
                  "onset", "brackets"]

_INF = math.inf


# ---------------------------------------------------------------------------------------------------- reading


def _two_pass(directory: Path | None, labeller_id: str | None) -> pd.DataFrame:
    """One row per (item, labeller): latest non-relabel pass-1 row plus its pass-2 row (``post_*``, NaN if none).

    Blind relabels are dropped before the latest row is taken, as in `labels.read_labels` (which no longer
    lets a relabel shadow the first-pass label). The pass-2 row is matched here through `pass1_label_id`."""
    allrows = read_all_rows(directory)
    pre = effective_rows(allrows)
    pre = pre[~pre["is_relabel"]]
    if labeller_id is not None:
        pre = pre[pre["labeller_id"] == labeller_id]
    pre = pre.groupby(["queue_id", "labeller_id"], sort=False).tail(1)
    post = effective_dop_rows(allrows)
    post = post[~post["is_relabel"]].groupby("pass1_label_id", sort=False).tail(1)
    post = post.add_prefix("post_")
    return pre.merge(post, left_on="label_id", right_on="post_pass1_label_id", how="left").reset_index(drop=True)


def primary_labels(directory: Path | None = None, labeller_id: str | None = None, key: str = "queue_id", *,
                   track: Track, label_pass: LabelPass, missing_post_dop: MissingPostDop | None = None
                   ) -> pd.DataFrame:
    """One label per item from one labeller and one explicit pass (see module docstring).

    `key` names the label column that matches the feature table's ``site_id`` (the app keys by ``queue_id``)."""
    if track not in TRACK_PASSES:
        raise ValueError(f"unknown track {track!r}")
    if label_pass not in TRACK_PASSES[track]:
        raise ValueError(f"track {track} targets cannot come from the {label_pass!r} pass "
                         f"(allowed: {TRACK_PASSES[track]}); Track A uses Sentinel-only pass-1 answers")
    if label_pass == "post_dop" and missing_post_dop not in ("drop", "use_pre_dop"):
        raise ValueError("label_pass='post_dop' needs missing_post_dop='drop' or 'use_pre_dop'")
    if label_pass == "pre_dop" and missing_post_dop is not None:
        raise ValueError("missing_post_dop applies to label_pass='post_dop' only")

    lab = _two_pass(directory, labeller_id)
    if lab["labeller_id"].nunique() > 1:
        raise ValueError("labels from several labellers; pass labeller_id")
    if key not in lab.columns:
        raise ValueError(f"labels have no column {key!r}")
    if lab[key].eq("").any() or lab[key].duplicated().any():
        raise ValueError(f"label key {key!r} is empty or not unique")
    bad = sorted(set(lab["schema_version"]) - {SCHEMA_VERSION})
    if bad:
        raise ValueError(f"label rows with schema_version {bad}; targets need schema {SCHEMA_VERSION}")

    has_post = lab["post_label_id"].notna()
    content = ["site_class", "colocated", *EVENT_FIELDS, *CONF_COLUMNS, "confidence", "label_id"]
    out = lab[[key, "labeller_id", *content]].copy()
    out["label_pass_used"] = "pre_dop"
    if label_pass == "post_dop":
        for c in content:
            out.loc[has_post, c] = lab.loc[has_post, f"post_{c}"]
        out.loc[has_post, "label_pass_used"] = "post_dop"
        if missing_post_dop == "drop":
            out = out[has_post]
    exposed = lab["registry_date_exposed"].eq(True) | lab["post_registry_date_exposed"].eq(True)
    out["registry_date_exposed"] = exposed.loc[out.index]
    coarse = lab["coord_coarse"].eq(True) | lab["post_coord_coarse"].eq(True)
    out["coord_coarse"] = coarse.loc[out.index]
    # DOP answers are evaluation metadata (KICKOFF 6.0); Track A targets never depend on them
    out["dop_identity"] = lab["post_dop_identity"].fillna("")
    out["dop_footprint"] = lab["post_dop_footprint"].fillna("")
    out["track"] = track
    out = out[out["site_class"] != "unsure"]
    out = out.rename(columns={key: "site_id"})[["site_id", *LABEL_KEEP]].reset_index(drop=True)
    out["confidence"] = out["confidence"].astype(int)
    return out


# ---------------------------------------------------------------------------------------------------- mapping


def _event(row: pd.Series, tech: str, event: str, brackets: str) -> tuple[float, float] | str | None:
    m = str(row.get(f"{tech}_{event}_month", "") or "")
    if not m:
        return None
    if m == NOT_VISIBLE:
        return "absent"
    if m == BEFORE_SERIES:
        return (-_INF, -_INF)
    if m == AFTER_SERIES:
        return (_INF, _INF)
    mi = month_index(m)
    lo = month_index(str(row.get(f"{tech}_{event}_earliest") or m))
    hi = month_index(str(row.get(f"{tech}_{event}_latest") or m))
    if brackets == "point":
        return (float(mi), float(mi))
    if brackets == "unknown":
        return (float(lo), float(hi))
    mid = float(math.floor((lo + hi) / 2))
    return (mid, mid)


def level_onsets(row: pd.Series, tech: str, brackets: str) -> list[tuple[float, float]]:
    """For k = 1, 2, 3: (lo, hi) month-index bounds of the first month with state >= k (plus or minus infinity
    outside the series). Undetermined bounds widen to the neighbouring determined events."""
    iv = {e: _event(row, tech, e, brackets) for e in EVENTS}
    if iv["complete"] == "absent":
        iv["complete"] = (_INF, _INF)
    if iv["struct"] == "absent":
        iv["struct"] = iv["complete"]
    if iv["clear"] == "absent":
        iv["clear"] = iv["struct"]
    out = []
    for i, e in enumerate(EVENTS):
        v = iv[e]
        if v is None:
            earlier = [iv[x][0] for x in EVENTS[:i] if iv[x] is not None]
            later = [iv[x][1] for x in EVENTS[i + 1:] if iv[x] is not None]
            v = (max(earlier, default=-_INF), min(later, default=_INF))
        out.append(v)
    return out  # type: ignore[return-value]


def _levels(t: np.ndarray, onsets: list[tuple[float, float]]) -> np.ndarray:
    """(3, n) array of level indicators: 1, 0 or NaN, made monotone across levels."""
    lv = np.full((3, len(t)), np.nan)
    for k, (lo, hi) in enumerate(onsets):
        lv[k, t >= hi] = 1.0
        lv[k, t < lo] = 0.0
    for k in range(3):  # state >= k implies every lower level; not >= k excludes every higher level
        lv[:k, lv[k] == 1] = 1.0
        lv[k + 1:, lv[k] == 0] = 0.0
    return lv


def onset_confidence(row: pd.Series, tech: str, onset: str) -> float:
    """Confidence (1 to 3) of the event that defines the `onset` level for `tech` (``bat`` or ``pv``): the onset
    event, or the next event it coincides with when it is ``not_visible``. NaN if the event is undetermined or
    carries no confidence."""
    i = EVENTS.index(onset)
    while i < len(EVENTS) - 1 and str(row.get(f"{tech}_{EVENTS[i]}_month", "") or "") == NOT_VISIBLE:
        i += 1
    if not str(row.get(f"{tech}_{EVENTS[i]}_month", "") or ""):
        return float("nan")
    v = str(row.get(f"{tech}_{EVENTS[i]}_conf", "") or "").strip()
    return float(v) if v else float("nan")


def technology_series(row: pd.Series, tech: str, months: pd.DatetimeIndex, *, onset: Onset, brackets: Brackets
                      ) -> tuple[np.ndarray, np.ndarray]:
    """(y, state) for one present technology (`tech` is ``bat`` or ``pv``) over `months`."""
    t = np.array([month_index(f"{m:%Y-%m}") for m in months], dtype=float)
    lv = _levels(t, level_onsets(row, tech, brackets))
    y = lv[ONSETS.index(onset)]
    state = np.where(np.isnan(lv).any(axis=0), np.nan, lv.sum(axis=0))
    return y, state


def monthly_targets(labels: pd.DataFrame, keys: pd.DataFrame, *, onset: Onset, brackets: Brackets
                    ) -> pd.DataFrame:
    """Long table (`TARGET_COLUMNS`): one row per labelled (site, month, technology) for the site-months in `keys`
    (the feature table's ``site_id`` and ``month``). Unlabelled sites are dropped. `labels` is the
    `primary_labels` output. `onset` and `brackets` are the author's mapping choices (no defaults)."""
    if onset not in ONSETS:
        raise ValueError(f"onset must be one of {ONSETS}")
    if brackets not in BRACKETS:
        raise ValueError(f"brackets must be one of {BRACKETS}")
    lab = labels.set_index("site_id")
    if lab.index.duplicated().any():
        raise ValueError("labels hold a site twice")
    rows = []
    for sid, g in keys[["site_id", "month"]].drop_duplicates().groupby("site_id", sort=True):
        if sid not in lab.index:
            continue
        r = lab.loc[sid]
        colocated = str(r.get("colocated", "") or "none")
        ev = {c: str(r.get(c, "") or "") for c in EVENT_FIELDS}
        validate_events(ev, r["site_class"], colocated)
        act = active_techs(r["site_class"], colocated)
        months = pd.DatetimeIndex(g["month"]).sort_values()
        for tech in TECHNOLOGIES:
            code = TECH_CODE[tech]
            if code in act:
                y, state = technology_series(r, code, months, onset=onset, brackets=brackets)
                oconf = onset_confidence(r, code, onset)
            else:
                y, state = np.zeros(len(months)), np.zeros(len(months))
                oconf = float("nan")
            rows.append(pd.DataFrame({
                "site_id": sid, "month": months, "technology": tech, "y": y, "state": state,
                "present": code in act, "colocated_target": len(act) > 1, "site_class": r["site_class"],
                "colocated": colocated, "confidence": int(r["confidence"]), "onset_conf": oconf,
                "registry_date_exposed": bool(r.get("registry_date_exposed", False)),
                "coord_coarse": bool(r.get("coord_coarse", False)),
                "label_pass_used": r.get("label_pass_used", ""), "onset": onset, "brackets": brackets}))
    return pd.concat(rows, ignore_index=True)[TARGET_COLUMNS] if rows else pd.DataFrame(columns=TARGET_COLUMNS)


def site_truth(targets: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Plan 2.4 at site level for the window [start, end]: positive (1) if y = 1 in at least one month, negative
    (0) if every month in the window is 0, unknown (NaN) otherwise or if the window holds no labelled month."""
    w = targets[(targets["month"] >= start) & (targets["month"] <= end)]

    def truth(y: pd.Series) -> float:
        if (y == 1).any():
            return 1.0
        if len(y) and (y == 0).all():
            return 0.0
        return float("nan")

    out = w.groupby(["site_id", "technology"])["y"].agg(truth).rename("truth").reset_index()
    return out


__all__ = ["BRACKETS", "ONSETS", "TARGET_COLUMNS", "TRACK_PASSES", "monthly_targets", "onset_confidence",
           "primary_labels", "site_truth"]
