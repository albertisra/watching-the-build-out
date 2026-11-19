"""Append-only label store (CSV in data/labels/). Earlier rows are never rewritten.

Row types in `labels.csv`:
  label       pass 1, Sentinel-only answers. Immutable: it cannot be voided.
  dop_review  pass 2, answers after the DOP chip was shown (post_dop). May be voided (undo of pass 2 only).
  void        cancels a `dop_review` row named in `voids_label_id`.
Reading drops voided rows and keeps the latest remaining row per (item, labeller, record type).
After registry facts were revealed for an item (review mode) no further row for that item and labeller is
accepted: the reveal locks the labels.
"""

from __future__ import annotations

import csv
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from bo import paths

from . import APP_VERSION
from .schema import (
    CONTENT_COLUMNS,
    EVENT_COLUMNS,
    LABEL_COLUMNS,
    REVEAL_COLUMNS,
    SCHEMA_VERSION,
    event_confidences,
    legacy_summary,
    normalise_events,
    validate_form,
)

LABELS_FILE = "labels.csv"
REVEALS_FILE = "reveals.csv"
UNLOCKS_FILE = "review_unlocks.csv"
BOOL_COLUMNS = ("is_relabel", "relabel_after_dop_seen", "revealed_before", "registry_date_exposed", "coord_coarse")


class LockedError(ValueError):
    """Raised on a write that would change what an item's labels are."""


class DuplicatePass1Error(ValueError):
    """A second pass-1 row for the same item and labeller that is not a blind relabel."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _append(path: Path, columns: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="raise", lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in columns})
        fh.flush()


def _content(site_class, colocated, events, confidence, note) -> dict:
    ev = normalise_events(events or {}, site_class, colocated)
    validate_form(site_class, colocated, ev, confidence)
    conf = event_confidences(events or {}, site_class, colocated, confidence)
    start, comp = legacy_summary(ev, site_class, colocated)
    return {"site_class": site_class, "colocated": colocated, **ev, **conf, "start_month": start,
            "complete_month": comp, "confidence": confidence, "note": " ".join(str(note).split())}


_STRATA_MAP: dict[str, str] | None = None


def stratum_of(queue_id: str) -> str:
    """Queue stratum of an item, looked up at write time from the strata file (never held by the app).
    Empty if the file or the item is missing."""
    global _STRATA_MAP
    if _STRATA_MAP is None:
        p = paths.PROCESSED / "labels" / "queue_round1_strata.parquet"
        _STRATA_MAP = (dict(zip(*[pd.read_parquet(p, columns=["queue_id", "stratum"])[c] for c in ("queue_id", "stratum")]))
                       if p.exists() else {})
    return _STRATA_MAP.get(queue_id, "")


def dop_seen(queue_id: str, labeller_id: str, directory: Path | None) -> bool:
    """True if the labeller already did pass 2 (saw the DOP chip) for this item, voided or not."""
    df = read_all_rows(directory)
    return bool(((df["record_type"] == "dop_review") & (df["queue_id"] == queue_id)
                 & (df["labeller_id"] == labeller_id)).any())


def _check_unlocked(queue_id: str, labeller_id: str, directory: Path | None) -> None:
    if queue_id in revealed_sites(directory, labeller_id):
        raise LockedError("registry facts were revealed for this item; its labels are locked")


def append_label(*, queue_id, labeller_id, site_class, confidence, events=None, colocated="none", note="",
                 stratum="", is_relabel=False, chip_stores="", revealed_before=False,
                 registry_date_exposed=False, coord_coarse=False, directory: Path | None = None,
                 now: str | None = None) -> str:
    """Pass 1 (Sentinel only). Returns the label_id. A second pass-1 row for the same item and labeller is
    refused unless `is_relabel` (blind consistency check); pass 1 is final."""
    _check_unlocked(queue_id, labeller_id, directory)
    if not is_relabel:
        prior = effective_rows(read_all_rows(directory))
        if ((prior["queue_id"] == queue_id) & (prior["labeller_id"] == labeller_id) & ~prior["is_relabel"]).any():
            raise DuplicatePass1Error(f"item {queue_id} already has a pass-1 label from {labeller_id}; "
                                      "pass 1 is final and only a blind relabel may add a second row")
    content = _content(site_class, colocated, events, confidence, note)
    label_id = uuid.uuid4().hex[:12]
    stratum = stratum or stratum_of(queue_id)
    after_dop = bool(is_relabel) and dop_seen(queue_id, labeller_id, directory)
    _append((directory or paths.LABELS) / LABELS_FILE, LABEL_COLUMNS, {
        "relabel_after_dop_seen": after_dop,
        "label_id": label_id, "record_type": "label", "schema_version": SCHEMA_VERSION, "pass_id": "pre_dop",
        "queue_id": queue_id, "labeller_id": labeller_id, "timestamp_utc": now or _now(),
        "app_version": APP_VERSION, "stratum": stratum, "is_relabel": bool(is_relabel), **content,
        "chip_stores": chip_stores, "revealed_before": bool(revealed_before),
        "registry_date_exposed": bool(registry_date_exposed), "coord_coarse": bool(coord_coarse),
    })
    return label_id


def append_dop_review(*, pass1_label_id, queue_id, labeller_id, site_class, confidence, dop_identity,
                      dop_footprint, events=None, colocated="none", note="", stratum="", is_relabel=False,
                      chip_stores="", registry_date_exposed=False, coord_coarse=False,
                      directory: Path | None = None, now: str | None = None) -> str:
    """Pass 2 (after the DOP chip was shown): identity and footprint confirmation plus revised answers.
    Needs an existing pass-1 row of the same item and labeller; never touches it."""
    _check_unlocked(queue_id, labeller_id, directory)
    rows = effective_rows(read_all_rows(directory))
    if not ((rows["label_id"] == pass1_label_id) & (rows["queue_id"] == queue_id)
            & (rows["labeller_id"] == labeller_id)).any():
        raise ValueError("pass 2 needs a committed pass-1 label of the same item and labeller")
    if not dop_identity or not dop_footprint:
        raise ValueError("DOP identity and footprint answers are required in pass 2")
    content = _content(site_class, colocated, events, confidence, note)
    validate_form(site_class, colocated, content, confidence, dop_identity, dop_footprint)
    label_id = uuid.uuid4().hex[:12]
    stratum = stratum or stratum_of(queue_id)
    _append((directory or paths.LABELS) / LABELS_FILE, LABEL_COLUMNS, {
        "label_id": label_id, "record_type": "dop_review", "schema_version": SCHEMA_VERSION,
        "pass_id": "post_dop", "pass1_label_id": pass1_label_id, "queue_id": queue_id,
        "labeller_id": labeller_id, "timestamp_utc": now or _now(), "app_version": APP_VERSION,
        "stratum": stratum, "is_relabel": bool(is_relabel), **content, "dop_identity": dop_identity,
        "dop_footprint": dop_footprint, "chip_stores": chip_stores,
        "registry_date_exposed": bool(registry_date_exposed), "coord_coarse": bool(coord_coarse),
    })
    return label_id


def void_label(label_id: str, *, queue_id: str, labeller_id: str, directory: Path | None = None,
               now: str | None = None) -> None:
    """Undo of a pass-2 row. Pass-1 rows are immutable and cannot be voided."""
    rows = read_all_rows(directory)
    target = rows[rows["label_id"] == label_id]
    if target.empty:
        raise ValueError("no such label_id")
    if target.iloc[0]["record_type"] != "dop_review":
        raise ValueError("pass-1 labels are immutable and cannot be voided")
    _check_unlocked(queue_id, labeller_id, directory)
    _append((directory or paths.LABELS) / LABELS_FILE, LABEL_COLUMNS, {
        "label_id": uuid.uuid4().hex[:12], "record_type": "void", "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id, "labeller_id": labeller_id, "timestamp_utc": now or _now(),
        "app_version": APP_VERSION, "voids_label_id": label_id,
    })


def log_unlock(labeller_id: str, directory: Path | None = None, now: str | None = None) -> None:
    """Review mode was unlocked during an open round (config flag). One row per use of review mode."""
    _append((directory or paths.LABELS) / UNLOCKS_FILE, REVEAL_COLUMNS, {
        "queue_id": "*", "labeller_id": labeller_id, "timestamp_utc": now or _now(), "app_version": APP_VERSION,
    })


def log_reveal(queue_id: str, labeller_id: str, directory: Path | None = None,
               now: str | None = None) -> None:
    """Used by the post-labelling review mode only (`bo.labelling.review`)."""
    _append((directory or paths.LABELS) / REVEALS_FILE, REVEAL_COLUMNS, {
        "queue_id": queue_id, "labeller_id": labeller_id, "timestamp_utc": now or _now(),
        "app_version": APP_VERSION,
    })


def read_all_rows(directory: Path | None = None) -> pd.DataFrame:
    p = (directory or paths.LABELS) / LABELS_FILE
    if not p.exists():
        df = pd.DataFrame(columns=LABEL_COLUMNS, dtype=str)
        return df.astype({c: bool for c in BOOL_COLUMNS if c in df.columns})
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    for c in BOOL_COLUMNS:
        df[c] = df[c].str.lower().eq("true") if c in df else False  # files written before the column existed
    return df


def _not_voided(df: pd.DataFrame, record_type: str) -> pd.DataFrame:
    voided = set(df.loc[df["record_type"] == "void", "voids_label_id"])
    lab = df[(df["record_type"] == record_type) & ~df["label_id"].isin(voided)]
    return lab.reset_index(drop=True)


def effective_rows(df: pd.DataFrame) -> pd.DataFrame:
    """All pass-1 label rows (they cannot be voided), in file order."""
    return _not_voided(df, "label")


def effective_dop_rows(df: pd.DataFrame) -> pd.DataFrame:
    return _not_voided(df, "dop_review")


def read_labels(directory: Path | None = None, labeller_id: str | None = None) -> pd.DataFrame:
    """Latest first-pass row per (item, labeller). File order decides, not the clock.
    Blind relabels are excluded before the latest row is taken, so a relabel never replaces the label;
    relabels are read for agreement through `effective_rows`."""
    lab = effective_rows(read_all_rows(directory))
    lab = lab.loc[~lab["is_relabel"].astype(bool)]
    if labeller_id is not None:
        lab = lab[lab["labeller_id"] == labeller_id]
    return lab.groupby(["queue_id", "labeller_id"], sort=False).tail(1).reset_index(drop=True)


def read_two_pass(directory: Path | None = None, labeller_id: str | None = None) -> pd.DataFrame:
    """One row per (item, labeller): `pre_dop_*` from the latest pass-1 row, `post_dop_*` from the pass-2 row
    that refers to it (empty if there is none), plus `dop_identity` and `dop_footprint`."""
    allrows = read_all_rows(directory)
    pre = read_labels(directory, labeller_id)
    post = effective_dop_rows(allrows)
    post = post.groupby("pass1_label_id", sort=False).tail(1)
    keep = [*CONTENT_COLUMNS, "label_id", "timestamp_utc"]
    a = pre[["queue_id", "labeller_id", "label_id", "stratum", "is_relabel", "registry_date_exposed",
             "coord_coarse", *CONTENT_COLUMNS, "timestamp_utc"]].rename(columns={c: f"pre_dop_{c}" for c in keep})
    b = post[["pass1_label_id", "dop_identity", "dop_footprint", *keep]].rename(
        columns={c: f"post_dop_{c}" for c in keep})
    return a.merge(b, left_on="pre_dop_label_id", right_on="pass1_label_id", how="left").drop(
        columns="pass1_label_id").fillna("")


def has_dop_review(queue_id: str, labeller_id: str, directory: Path | None = None) -> bool:
    rows = read_two_pass(directory, labeller_id)
    r = rows[rows["queue_id"] == queue_id]
    return bool(len(r) and r.iloc[-1]["post_dop_label_id"])


def read_reveals(directory: Path | None = None) -> pd.DataFrame:
    p = (directory or paths.LABELS) / REVEALS_FILE
    if not p.exists():
        return pd.DataFrame(columns=REVEAL_COLUMNS)
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def revealed_sites(directory: Path | None = None, labeller_id: str | None = None) -> set[str]:
    r = read_reveals(directory)
    if labeller_id is not None:
        r = r[r["labeller_id"] == labeller_id]
    return set(r["queue_id"])


__all__ = ["EVENT_COLUMNS", "LockedError"]
