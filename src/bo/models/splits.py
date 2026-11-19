"""Fold assignment reader (plan 4.1). The file is written by the split owner, not here.

Expected schema of `data/processed/splits/blocks_v1.parquet` (one row per site):

| column | meaning |
|---|---|
| ``queue_id`` (default key) | matches the ``site_id`` values of the feature table (chip-store name) |
| ``block_id`` | 50 km EPSG:3035 cell of the site's cluster medoid |
| ``fold`` | 0 to 4; 0 is the locked test fold |
| ``cluster_id`` (optional) | 2 km single-linkage cluster; a cluster sits in one block |
| ``open_dop`` (optional) | site lies in an open-DOP state; `bo.models.trackb.open_dop_flags` derives it |

The reader validates that every site has one fold, that blocks and clusters do not straddle folds, and that folds
lie in 0 to 4. Written by `bo.timeline.splits` (``queue_id, site_id, cluster_id, block_id, fold, role``); the
registry ``site_id`` is empty for negatives, so the queue ID is the key. Missing file: `SplitsMissingError` naming the producer.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bo.timeline.splits import SPLIT_FILE

from . import design
from .guards import LeakageError

SPLITS_PATH = SPLIT_FILE
REQUIRED = ("block_id", "fold")
OPTIONAL = ("cluster_id", "open_dop")


class SplitsMissingError(FileNotFoundError):
    pass


def validate_splits(s: pd.DataFrame, key: str = "queue_id") -> pd.DataFrame:
    missing = [c for c in (key, *REQUIRED) if c not in s.columns]
    if missing:
        raise ValueError(f"fold file lacks columns {missing} (plan 4.1 schema)")
    if s[key].isna().any():
        raise ValueError(f"fold file has rows without {key}")
    if s[key].duplicated().any():
        dup = s.loc[s[key].duplicated(), key].head(5).tolist()
        raise LeakageError(f"site listed more than once in the fold file: {dup}")
    if s["fold"].isna().any() or not s["fold"].astype(int).between(0, design.N_FOLDS - 1).all():
        raise ValueError(f"fold values must be 0 to {design.N_FOLDS - 1}")
    for grp in ("block_id", "cluster_id"):
        if grp in s.columns:
            n = s.groupby(grp)["fold"].nunique()
            if (n > 1).any():
                raise LeakageError(f"{grp} in more than one fold: {list(n[n > 1].index[:5])}")
    if "cluster_id" in s.columns:
        n = s.groupby("cluster_id")["block_id"].nunique()
        if (n > 1).any():
            raise LeakageError(f"cluster in more than one block: {list(n[n > 1].index[:5])}")
    out = s.copy()
    out["fold"] = out["fold"].astype(int)
    return out


def load_splits(path: Path | None = None, key: str = "queue_id") -> pd.DataFrame:
    p = path or SPLITS_PATH
    if not p.exists():
        raise SplitsMissingError(
            f"{p} does not exist. The fold assignment (plan 4.1, blocks_v1) is written by the split owner "
            "before labelling ends; the detector never draws its own folds.")
    return validate_splits(pd.read_parquet(p), key)


def attach_folds(df: pd.DataFrame, splits: pd.DataFrame, key: str = "queue_id") -> pd.DataFrame:
    """Add ``fold``, ``block_id`` (and optional columns) to rows keyed by ``site_id``. Every site needs a fold."""
    keep = [key, *REQUIRED, *[c for c in OPTIONAL if c in splits.columns]]
    s = splits[keep].rename(columns={key: "site_id"})
    clash = [c for c in keep[1:] if c in df.columns]
    if clash:
        raise ValueError(f"rows already carry {clash}")
    out = df.merge(s, on="site_id", how="left", validate="many_to_one")
    lost = out.loc[out["fold"].isna(), "site_id"].unique()
    if len(lost):
        raise LeakageError(f"{len(lost)} sites have no fold (first: {list(lost[:5])}); the split owner must add "
                           "them by block")
    out["fold"] = out["fold"].astype(int)
    return out
