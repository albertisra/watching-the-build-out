"""Post-labelling review mode: registry facts for items whose labels are already committed.

Separate from the labelling session (`app/review_app.py`; `app/label_app.py` never imports this module).
Revealing locks the item: the reveal is logged first and `bo.labelling.labels` then refuses further label rows
for that item and labeller. A reveal needs a committed pass-1 label and, where the item has a visible DOP
chip, a committed pass-2 review.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path

import pandas as pd

from bo import paths

from . import labels


def reveal_facts(queue_id: str, queue_row: Mapping | None = None) -> dict:
    """Registry facts for one item (observed). `queue_row` is the full queue entry. Registry details are
    looked up by registry key; negatives have none."""
    facts: dict = {}
    row = queue_row or {}
    if row.get("stratum"):
        facts["queue stratum"] = str(row["stratum"])
    for k, label in (("bundesland", "federal state"), ("landkreis", "district"),
                     ("osm_category", "OSM category"), ("worldcover_class", "WorldCover class")):
        v = row.get(k)
        if v is not None and not pd.isna(v):
            facts[label] = str(v)
    key = row.get("site_id")
    if key is not None and not pd.isna(key):
        facts["registry key"] = str(key)
        t = pd.read_parquet(paths.PROCESSED / "registry" / "registry_sites.parquet",
                            columns=["site_id", "technology", "power_kw", "reg_status",
                                     "reg_commissioning_date_first"])
        r = t[t["site_id"] == key]
        if len(r):
            r = r.iloc[0]
            facts.update({
                "registry technology (observed)": str(r["technology"]),
                "registry power kW (observed)": float(r["power_kw"]),
                "registry status (observed)": str(r["reg_status"]),
                "registry first commissioning date (observed)": str(r["reg_commissioning_date_first"])[:10],
            })
    return facts


class RoundOpenError(ValueError):
    """Review mode is locked while the labeller still has unlabelled items in the round."""


def open_items(round_queue_ids: Collection[str], labeller_id: str, directory: Path | None = None) -> set[str]:
    """Round items without a committed pass-1 label of this labeller (blind relabels do not count)."""
    return set(round_queue_ids) - set(labels.read_labels(directory, labeller_id)["queue_id"])


def lock_and_reveal(queue_id: str, labeller_id: str, queue_row: Mapping, *, round_queue_ids: Collection[str],
                    allow_open_round: bool = False, dop_pending: bool = False,
                    directory: Path | None = None) -> dict:
    """Lock the item's labels, log the reveal, return the facts. Raises `RoundOpenError` while the round still
    has unlabelled items, unless `allow_open_round` (config flag `[review] allow_during_open_round`); that use
    is logged in review_unlocks.csv. Raises if there is no pass-1 label, or if a DOP pass-2 review is still
    pending for the item. Every reveal makes the item non-blind, which weakens the blind relabel set."""
    remaining = open_items(round_queue_ids, labeller_id, directory)
    if remaining and not allow_open_round:
        raise RoundOpenError(f"review is locked: {len(remaining)} items of this round are still unlabelled. "
                             "Set [review] allow_during_open_round = true in app/config/labelling.toml to override")
    mine = labels.read_labels(directory, labeller_id)
    if queue_id not in set(mine["queue_id"]):
        raise ValueError("no committed label for this item; nothing to review yet")
    if dop_pending and not labels.has_dop_review(queue_id, labeller_id, directory):
        raise ValueError("finish the DOP pass for this item before the registry review")
    if remaining:
        labels.log_unlock(labeller_id, directory)
    labels.log_reveal(queue_id, labeller_id, directory)
    return reveal_facts(queue_id, queue_row)
