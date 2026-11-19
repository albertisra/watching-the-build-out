"""Labelling queue: loading, reproducible ordering and blind relabel insertion.

Queue view (the only queue file the labelling app reads, `bo.data.queue.write_view`): queue_id, lat, lon,
bundesland. No stratum, registry key, OSM category or land cover. The item key everywhere is queue_id (chips,
labels, relabels, reveals). The stratum is looked up from queue_round1_strata.parquet when a label row is
written (`bo.labelling.labels.stratum_of`). The review app and the development queue may still carry the
full queue columns; `stratum` is validated when present.
"""

from __future__ import annotations

import hashlib
import math
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from bo import paths

QUEUE_COLUMNS = ["queue_id", "lat", "lon", "bundesland"]
STRATA = ("positive_battery", "positive_pv", "hard_negative", "random_negative", "model_disagreement", "pilot")
CONFIG_PATH = paths.REPO_ROOT / "app" / "config" / "labelling.toml"


def load_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH, "rb") as fh:
        return tomllib.load(fh)


def validate_queue(q: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in QUEUE_COLUMNS if c not in q.columns]
    if missing:
        raise ValueError(f"queue lacks columns {missing}")
    if q["queue_id"].duplicated().any():
        raise ValueError("queue_id must be unique")
    bad = set(q["stratum"]) - set(STRATA) if "stratum" in q else set()
    if bad:
        raise ValueError(f"unknown strata {sorted(bad)}")
    return q


def load_queue(path: Path | None = None) -> pd.DataFrame:
    return validate_queue(pd.read_parquet(path or (paths.REPO_ROOT / load_config()["queue"]["file"])))


def load_view(path: Path | None = None) -> pd.DataFrame:
    """The blind queue view the labelling app reads (queue_id, lat, lon, bundesland)."""
    return validate_queue(pd.read_parquet(path or (paths.REPO_ROOT / load_config()["queue"]["view_file"])))


def order_queue(q: pd.DataFrame, seed: int = paths.SEED) -> pd.DataFrame:
    """Reproducible order: rows sorted by queue_id, then a seeded permutation. The result does not
    depend on the input row order. Strata are mixed so that runs reveal nothing about the class."""
    q = q.sort_values("queue_id").reset_index(drop=True)
    perm = np.random.default_rng(seed).permutation(len(q))
    return q.iloc[perm].reset_index(drop=True)


def _score(seed: int, site_id: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{site_id}".encode()).digest()[:8], "big")


def select_relabel(labelled: set[str] | list[str], revealed: set[str], fraction: float = 0.10,
                   seed: int = paths.SEED) -> list[str]:
    """Blind relabel subset: ceil(fraction * eligible) of the labelled sites that were never revealed,
    ranked by a seeded hash (reproducible, independent of order). Revealed sites are excluded."""
    eligible = sorted(set(labelled) - set(revealed))
    n = math.ceil(fraction * len(eligible)) if eligible else 0
    return sorted(sorted(eligible, key=lambda s: _score(seed, s))[:n], key=lambda s: _score(seed, s))


def build_session_queue(queue: pd.DataFrame, labelled: set[str], relabel_done: set[str],
                        revealed: set[str], fraction: float = 0.10, min_position: int = 10,
                        seed: int = paths.SEED, shuffle: bool = False) -> pd.DataFrame:
    """Ordered queue for one labeller: unlabelled sites in seeded order, with the still-due blind
    relabels inserted at seeded positions at or after `min_position`. Column `is_relabel` marks them."""
    # The round-1 queue file is already a seeded shuffle: keep its row order unless shuffle=True.
    ordered = order_queue(queue, seed) if shuffle else queue.reset_index(drop=True)
    pending = ordered[~ordered["queue_id"].isin(labelled)].assign(is_relabel=False)
    chosen = select_relabel(labelled & set(queue["queue_id"]), revealed, fraction, seed)
    due = [s for s in chosen if s not in relabel_done]
    items = [r for _, r in pending.iterrows()]
    rng = np.random.default_rng(seed + 1)
    by_site = queue.set_index("queue_id")
    for s in due:
        row = by_site.loc[s].copy()
        row["queue_id"] = s
        row["is_relabel"] = True
        lo = min(min_position, len(items))
        pos = int(rng.integers(lo, len(items) + 1))
        items.insert(pos, row)
    if not items:
        return pending
    return pd.DataFrame(items).reset_index(drop=True)[list(pending.columns)]


def make_test_queue(cfg: dict | None = None, seed: int = paths.SEED) -> pd.DataFrame:
    """Development queue drawn from the pilot tables (queue_id = pilot chip key). Fallback only; not the research queue."""
    cfg = cfg or load_config()
    n = cfg["test_queue"]
    pilot = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    neg = pd.read_parquet(paths.PROCESSED / "pilot" / "negatives_v1.parquet")
    parts = []
    for key, df, idcol, mask in (
        ("positive_battery", pilot, "pilot_id", pilot["subtype"] == "battery"),
        ("positive_pv", pilot, "pilot_id", pilot["subtype"] != "battery"),
        ("hard_negative", neg, "neg_id", neg["kind"] == "hard"),
        ("random_negative", neg, "neg_id", neg["kind"] != "hard"),
    ):
        d = df[mask].sort_values(idcol)
        d = d.sample(n=min(n[key], len(d)), random_state=seed)
        parts.append(pd.DataFrame({"queue_id": d[idcol].values, "lat": d["lat"].values,
                                   "lon": d["lon"].values, "bundesland": d["bundesland"].values}))
    q = pd.concat(parts, ignore_index=True)
    return validate_queue(q)
