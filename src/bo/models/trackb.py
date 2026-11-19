"""Track B slot: DOP-derived inputs, the open-DOP evaluation subset, the paired track comparison, and the rule that
a Track A detection the DOP contradicts counts as an error (KICKOFF 6.0, plan 4.1 and 7.1).

The DOP classifier itself waits for labels. It must implement `DopReader`: for a set of sites it returns one row
per DOP flight with ``site_id``, ``flight_month`` and the slot columns ``dop_p_battery`` and ``dop_p_pv`` (detected
probabilities that the technology is visible in the central area at the flight). Flights from use-restricted states
(Mecklenburg-Vorpommern, `bo.imagery.dop.drop_restricted`) must already be removed by the reader.

Leakage rule for DOP inputs: a month t only sees the latest flight with flight month <= t (as-of join backwards),
never a later flight, because a later flight reveals the future state of the site.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

from bo import paths

from . import design
from .bootstrap import block_indices, replicate_draws
from .guards import DOP_FEATURE_COLUMNS

DOP_READ_COLUMNS = ("site_id", "flight_month", "dop_p_battery", "dop_p_pv")

__all__ = [
    "DOP_FEATURE_COLUMNS",
    "DopReader",
    "attach_dop",
    "dop_contradicted",
    "paired_difference",
    "track_b_subset",
]


class DopReader(Protocol):
    def read(self, site_ids: list[str]) -> pd.DataFrame:
        """One row per (site, flight) with `DOP_READ_COLUMNS`."""
        ...


def attach_dop(features: pd.DataFrame, dop: pd.DataFrame) -> pd.DataFrame:
    """Add the DOP slot columns to monthly rows by an as-of backward join per site (NaN before the first flight)."""
    missing = [c for c in DOP_READ_COLUMNS if c not in dop.columns]
    if missing:
        raise ValueError(f"DOP table lacks {missing}")
    clash = [c for c in DOP_FEATURE_COLUMNS if c in features.columns]
    if clash:
        raise ValueError(f"rows already carry {clash}")
    d = dop[list(DOP_READ_COLUMNS)].copy()
    d["flight_month"] = pd.to_datetime(d["flight_month"]).dt.to_period("M").dt.to_timestamp()
    left = features.reset_index(drop=True).assign(_row=lambda x: np.arange(len(x)))
    left = left.sort_values("month")
    right = d.sort_values("flight_month")
    m = pd.merge_asof(left, right, left_on="month", right_on="flight_month", by="site_id",
                      direction="backward", allow_exact_matches=True)
    months_since = (m["month"].dt.year - m["flight_month"].dt.year) * 12 + (
        m["month"].dt.month - m["flight_month"].dt.month)
    m["dop_months_since_flight"] = months_since.astype("float64")
    m = m.drop(columns=["flight_month"]).sort_values("_row").drop(columns="_row").reset_index(drop=True)
    return m


def track_b_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Targets in open-DOP states (needs the fold file's ``open_dop`` column, plan 4.1)."""
    if "open_dop" not in df.columns:
        raise ValueError("no open_dop column: the fold file must mark open-DOP sites (plan 4.1)")
    return df[df["open_dop"].fillna(False).astype(bool)]


def paired_difference(a: pd.DataFrame, b: pd.DataFrame, metric: str = "recall", block_col: str = "block_id",
                      n_boot: int = design.N_BOOT, level: float = 0.95, seed: int = paths.SEED) -> dict:
    """Track B minus Track A on exactly the same targets (paired), block bootstrap over shared blocks.

    `a`, `b`: one row per target with ``site_id``, ``technology``, ``truth``, ``detected`` and the block column.
    """
    from .metrics import METRICS

    key = ["site_id", "technology"]
    m = a[[*key, "truth", "detected", block_col]].merge(
        b[[*key, "truth", "detected"]], on=key, suffixes=("_a", "_b"), validate="one_to_one")
    if not (m["truth_a"].fillna(-1) == m["truth_b"].fillna(-1)).all():
        raise ValueError("tracks scored against different truth on the same target")
    m = m[m["truth_a"].notna()]
    fn = METRICS[metric]

    def diff(x: pd.DataFrame) -> float:
        ta = pd.DataFrame({"truth": x["truth_a"], "detected": x["detected_a"]})
        tb = pd.DataFrame({"truth": x["truth_a"], "detected": x["detected_b"]})
        return fn(tb) - fn(ta)

    est = diff(m)
    groups = block_indices(m[block_col])
    vals = []
    if len(m) >= design.MIN_N_INTERVAL and len(groups) >= 2:
        for draw in replicate_draws(len(groups), n_boot, seed):
            v = diff(m.iloc[np.concatenate([groups[j] for j in draw])])
            if np.isfinite(v):
                vals.append(v)
    a_ = (1 - level) / 2
    lo, hi = (np.quantile(vals, [a_, 1 - a_]) if vals else (np.nan, np.nan))
    return {"metric": metric, "difference_b_minus_a": est, "lo": float(lo), "hi": float(hi), "level": level,
            "n_targets": len(m), "n_blocks": len(groups), "n_boot_valid": len(vals),
            "interval": "paired spatial block bootstrap, percentile", "quantity_type": "detected"}


def dop_contradicted(track_a: pd.DataFrame, dop: pd.DataFrame, threshold: float = 0.5) -> pd.Series:
    """True where a Track A detection is contradicted by a DOP flight in or after its first detected month that
    shows the technology absent (dop_p_<tech> < threshold). `track_a`: one row per target with ``site_id``,
    ``technology``, ``detected`` and ``first_detected_month``."""
    d = dop[list(DOP_READ_COLUMNS)].copy()
    d["flight_month"] = pd.to_datetime(d["flight_month"]).dt.to_period("M").dt.to_timestamp()
    out = pd.Series(False, index=track_a.index, name="dop_contradicted")
    for i, r in track_a[track_a["detected"].astype(bool)].iterrows():
        f = d[(d["site_id"] == r["site_id"]) & (d["flight_month"] >= pd.Timestamp(r["first_detected_month"]))]
        p = f[f"dop_p_{r['technology']}"]
        out.loc[i] = bool(len(p) and (p < threshold).any())
    return out


def open_dop_flags(queue: pd.DataFrame) -> pd.DataFrame:
    """``queue_id`` and ``open_dop`` for queue rows: the state has an open DOP source and is not use-restricted.
    Same state set as the fold balancing of `bo.timeline.splits` (Mecklenburg-Vorpommern excluded)."""
    from bo.timeline.splits import open_dop_states

    states = open_dop_states()
    return pd.DataFrame({"queue_id": queue["queue_id"].to_numpy(),
                         "open_dop": queue["bundesland"].isin(states).to_numpy()})
