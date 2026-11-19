"""Label schema (version 3) and value vocabularies. Documented in data/labels/README.md.

Per technology (battery `bat`, PV `pv`) three events are recorded, following analysis plan 2.3 and 2.6:
  clear     first month with visible clearing, earthworks or ground works (`start_label`)
  struct    first month with visible structures, containers or panel rows (`uc_label`)
  complete  first month in which the structures look complete (`complete_label`)
Each event has `<tech>_<event>_month` (YYYY-MM, before_series, after_series or not_visible) and an optional
bracket `<tech>_<event>_earliest` / `_latest` (YYYY-MM, only with a YYYY-MM month, earliest <= month <= latest).
`not_visible` means the phase never shows as a separate step (for example no clearing phase before structures).
An empty month means "not determined" and is rejected for the active technologies of a positive class, so
that every positive item carries a full state sequence for the four-state HMM (`phase_sequence`).

Version 3 adds an optional confidence (1 to 3) per event, `<tech>_<event>_conf` (analysis plan 2.3). When the
labeller does not set it, it takes the item confidence at save time, so every active event always carries one.
The label row also carries `coord_coarse` (registry coordinate rounded to 1 or 2 decimals, never displayed) so
that evaluation can exclude those items.

Two passes: the pass-1 row (record_type `label`) holds Sentinel-only answers and is never voided. The pass-2
row (record_type `dop_review`) holds the answers after the DOP chip was shown plus identity and footprint
confirmation. `labels.read_two_pass` returns them side by side as `pre_dop_*` and `post_dop_*`.
"""

from __future__ import annotations

import itertools
import re

SCHEMA_VERSION = "3"
CLASSES = ("battery", "PV", "battery+PV", "other", "none", "unsure")
CLASS_KEYS = {"b": "battery", "p": "PV", "c": "battery+PV", "o": "other", "n": "none", "u": "unsure"}
POSITIVE_CLASSES = ("battery", "PV", "battery+PV")
BEFORE_SERIES = "before_series"
AFTER_SERIES = "after_series"
NOT_VISIBLE = "not_visible"
NOT_YET = AFTER_SERIES  # old name
SPECIAL_MONTHS = (BEFORE_SERIES, AFTER_SERIES, NOT_VISIBLE)
CONFIDENCES = (1, 2, 3)
COLOCATED = ("none", "pv", "battery", "other")  # other technology visible in the central area
DOP_IDENTITY = ("confirms", "contradicts", "cannot_tell")
DOP_FOOTPRINT = ("matches", "differs", "cannot_tell")

TECHS = ("bat", "pv")
EVENTS = ("clear", "struct", "complete")
PHASE_NAMES = ("U", "Cl", "UC", "Co")  # states 0..3 of bo.timeline.hmm


def event_columns() -> list[str]:
    return [f"{t}_{e}_{f}" for t in TECHS for e in EVENTS for f in ("month", "earliest", "latest")]


EVENT_COLUMNS = event_columns()
CONF_COLUMNS = [f"{t}_{e}_conf" for t in TECHS for e in EVENTS]
CONTENT_COLUMNS = ["site_class", "colocated", *EVENT_COLUMNS, *CONF_COLUMNS, "start_month", "complete_month", "confidence", "note"]
LABEL_COLUMNS = [
    "label_id", "record_type", "schema_version", "pass_id", "pass1_label_id", "queue_id", "labeller_id",
    "timestamp_utc", "app_version", "stratum", "is_relabel", "relabel_after_dop_seen", *CONTENT_COLUMNS, "coord_coarse",
    "dop_identity", "dop_footprint", "chip_stores", "revealed_before", "registry_date_exposed",
    "voids_label_id",
]
REVEAL_COLUMNS = ["queue_id", "labeller_id", "timestamp_utc", "app_version"]

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def is_month(value: str) -> bool:
    return bool(_MONTH.match(value or ""))


def month_index(value: str) -> int:
    """Months since year 0 for a YYYY-MM string, for differences."""
    if not is_month(value):
        raise ValueError(f"not a YYYY-MM month: {value!r}")
    return int(value[:4]) * 12 + int(value[5:7]) - 1


def active_techs(site_class: str, colocated: str = "none") -> tuple[str, ...]:
    """Technologies that carry their own dates: those in the class, plus a visible co-located one."""
    act = set()
    if site_class in ("battery", "battery+PV"):
        act.add("bat")
    if site_class in ("PV", "battery+PV"):
        act.add("pv")
    if colocated == "pv":
        act.add("pv")
    if colocated == "battery":
        act.add("bat")
    return tuple(t for t in TECHS if t in act)


def empty_events() -> dict[str, str]:
    return {c: "" for c in EVENT_COLUMNS}


def normalise_events(events: dict, site_class: str, colocated: str = "none") -> dict[str, str]:
    """Event columns of inactive technologies are emptied; missing keys become empty strings."""
    act = active_techs(site_class, colocated)
    out = empty_events()
    for c in EVENT_COLUMNS:
        if c.split("_")[0] in act:
            out[c] = str(events.get(c, "") or "")
    return out


def _threshold(month: str) -> float:
    if month == BEFORE_SERIES:
        return float("-inf")
    if month == AFTER_SERIES:
        return float("inf")
    return float(month_index(month))


def validate_events(events: dict, site_class: str, colocated: str = "none") -> None:
    act = active_techs(site_class, colocated)
    for c in EVENT_COLUMNS:
        if c.split("_")[0] not in act and events.get(c, ""):
            raise ValueError(f"{c} is set but {c.split('_')[0]} is not an active technology for this item")
    for t in act:
        known = []
        for e in EVENTS:
            m = events.get(f"{t}_{e}_month", "") or ""
            lo = events.get(f"{t}_{e}_earliest", "") or ""
            hi = events.get(f"{t}_{e}_latest", "") or ""
            if not m:
                if site_class in POSITIVE_CLASSES:
                    raise ValueError(f"{t}_{e}_month is not determined (use a month, before_series, "
                                     "after_series or not_visible)")
                continue
            if not (is_month(m) or m in SPECIAL_MONTHS):
                raise ValueError(f"{t}_{e}_month: {m!r} is not YYYY-MM, before_series, after_series or not_visible")
            for name, v in (("earliest", lo), ("latest", hi)):
                if v and not is_month(v):
                    raise ValueError(f"{t}_{e}_{name}: {v!r} is not YYYY-MM")
            if (lo or hi) and not is_month(m):
                raise ValueError(f"{t}_{e}: a range needs a YYYY-MM month")
            if lo and month_index(lo) > month_index(m):
                raise ValueError(f"{t}_{e}: earliest is after the month")
            if hi and month_index(hi) < month_index(m):
                raise ValueError(f"{t}_{e}: latest is before the month")
            if m != NOT_VISIBLE:
                known.append((e, _threshold(m)))
        for (e1, a), (e2, b) in itertools.pairwise(known):
            if b < a:
                raise ValueError(f"{t}: {e2} is before {e1}")


def event_confidences(events: dict, site_class: str, colocated: str, confidence: int) -> dict[str, str]:
    """`<tech>_<event>_conf` for the active technologies: the given value, else the item confidence.
    Inactive technologies stay empty. Raises ValueError for a value outside 1 to 3."""
    act = active_techs(site_class, colocated)
    out = {c: "" for c in CONF_COLUMNS}
    for c in CONF_COLUMNS:
        if c.split("_")[0] not in act:
            continue
        v = str(events.get(c, "") or "").strip()
        if v and v not in ("1", "2", "3"):
            raise ValueError(f"{c}: confidence must be 1, 2 or 3")
        out[c] = v or str(confidence)
    return out


def validate_form(site_class: str, colocated: str, events: dict, confidence: int, dop_identity: str = "",
                  dop_footprint: str = "") -> None:
    if site_class not in CLASSES:
        raise ValueError(f"unknown class {site_class!r}")
    if colocated not in COLOCATED:
        raise ValueError(f"unknown co-location value {colocated!r}")
    if confidence not in CONFIDENCES:
        raise ValueError("confidence must be 1, 2 or 3")
    if dop_identity and dop_identity not in DOP_IDENTITY:
        raise ValueError(f"unknown DOP identity answer {dop_identity!r}")
    if dop_footprint and dop_footprint not in DOP_FOOTPRINT:
        raise ValueError(f"unknown DOP footprint answer {dop_footprint!r}")
    validate_events(events, site_class, colocated)


def legacy_summary(events: dict, site_class: str, colocated: str = "none") -> tuple[str, str]:
    """`start_month` (earliest first-works month over active technologies) and `complete_month` (latest
    completion), kept as a coarse summary for the consistency check. Clearing, else structures."""
    starts, ends = [], []
    for t in active_techs(site_class, colocated):
        s = events.get(f"{t}_clear_month") or events.get(f"{t}_struct_month") or ""
        if s == NOT_VISIBLE:
            s = events.get(f"{t}_struct_month", "")
        starts.append(s)
        ends.append(events.get(f"{t}_complete_month", ""))

    def pick(vals, fn):
        dated = [v for v in vals if is_month(v)]
        if dated:
            return fn(dated, key=month_index)
        return next((v for v in vals if v), "")

    return pick(starts, min), pick(ends, max)


def validate_label(site_class: str, start: str, complete: str, confidence: int) -> None:
    """Coarse check kept for the summary columns."""
    if site_class not in CLASSES:
        raise ValueError(f"unknown class {site_class!r}")
    for name, v in (("start_month", start), ("complete_month", complete)):
        if v and not (is_month(v) or v in SPECIAL_MONTHS):
            raise ValueError(f"{name}: {v!r} is not YYYY-MM, before_series, after_series or not_visible")
    if confidence not in CONFIDENCES:
        raise ValueError("confidence must be 1, 2 or 3")
    if is_month(start) and is_month(complete) and month_index(complete) < month_index(start):
        raise ValueError("completion month is before start month")


def phase_sequence(row: dict, tech: str, months: list[str], *, use_brackets: bool = False) -> list[int]:
    """Monthly state sequence for the four-state HMM (`bo.timeline.hmm`): 0 U, 1 Cl, 2 UC, 3 Co, from the
    three events of one technology (`tech` is `bat` or `pv`). Months where the state cannot be determined
    (an undetermined event, or with `use_brackets` a month inside an event's earliest/latest range)
    get -1; `hmm.fit_supervised` marginalises -1 months and accepts skips between adjacent months
    (`hmm.split_labels`).

    A `not_visible` clearing event means the Cl phase is absent (clearing coincides with structures);
    a `not_visible` structures event means UC is absent; a `not_visible` completion never completes."""
    inf = float("inf")
    iv: dict[str, tuple[float, float] | None] = {}
    for e in EVENTS:
        m = row.get(f"{tech}_{e}_month", "") or ""
        if not m:
            iv[e] = None
        elif m == NOT_VISIBLE:
            iv[e] = "absent"  # type: ignore[assignment]
        elif m in (BEFORE_SERIES, AFTER_SERIES):
            iv[e] = (_threshold(m), _threshold(m))
        else:
            mi = month_index(m)
            lo, hi = mi, mi
            if use_brackets:
                lo = month_index(row.get(f"{tech}_{e}_earliest") or m)
                hi = month_index(row.get(f"{tech}_{e}_latest") or m)
            iv[e] = (float(lo), float(hi))
    # resolve absent events: completion -> never, structures -> with completion, clearing -> with structures
    if iv["complete"] == "absent":
        iv["complete"] = (inf, inf)
    if iv["struct"] == "absent":
        iv["struct"] = iv["complete"]
    if iv["clear"] == "absent":
        iv["clear"] = iv["struct"]
    out = []
    for mon in months:
        t = float(month_index(mon))
        state, unknown = 0, False
        for e in EVENTS:
            v = iv[e]
            if v is None:
                # undetermined: decided only if a later known event already passed (then it passed too)
                later = [iv[x] for x in EVENTS[EVENTS.index(e) + 1:] if iv[x] is not None]
                earlier = [iv[x] for x in EVENTS[:EVENTS.index(e)] if iv[x] is not None]
                if any(t >= w[1] for w in later):
                    state += 1
                elif any(t < w[0] for w in earlier):
                    pass
                else:
                    unknown = True
            elif t >= v[1]:
                state += 1
            elif t >= v[0]:
                unknown = True
        out.append(-1 if unknown else state)
    return out
