"""Per-site, per-month feature matrix for the detector, from the tables of `make features`.

`load_features(name)` reads `data/processed/features/features_<name>.parquet` and checks that it holds exactly
``ID_COLUMNS + FEATURE_COLUMNS``. `add_windows` adds trailing window statistics (current month and the months
before it, never later months), computed on the gap-free monthly axis of each site; missing months stay missing
and a window with no valid month is NaN (nothing is interpolated). `design_matrix` returns the keys and the input
matrix after the allow-list and deny-list guards.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from bo import paths
from bo.features.allowlist import FEATURE_COLUMNS, ID_COLUMNS

from .guards import assert_model_inputs, parse_column, window_column

FEATURES_DIR = paths.PROCESSED / "features"


def check_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    if tuple(df.columns) != ID_COLUMNS + FEATURE_COLUMNS:
        extra = sorted(set(df.columns) - set(ID_COLUMNS + FEATURE_COLUMNS))
        missing = sorted(set(ID_COLUMNS + FEATURE_COLUMNS) - set(df.columns))
        raise ValueError(f"feature table columns differ from the allow-list: extra {extra}, missing {missing}")
    if df.duplicated(list(ID_COLUMNS)).any():
        raise ValueError("feature table has duplicate (site_id, month) rows")
    out = df.copy()
    out["month"] = pd.to_datetime(out["month"]).dt.to_period("M").dt.to_timestamp()
    return out


def load_features(name: str, directory: Path | None = None) -> pd.DataFrame:
    p = (directory or FEATURES_DIR) / f"features_{name}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"{p}: run `make features` first")
    return check_feature_table(pd.read_parquet(p))


def build_store_features(name: str, roots: Sequence[Path]) -> Path:
    """Run the physicist's feature build for one chip store (same as one line of `make features`)."""
    from bo.features.build import build

    return build(name, list(roots))


def add_windows(df: pd.DataFrame, columns: Iterable[str], windows: Sequence[int],
                stats: Sequence[str] = ("mean",)) -> pd.DataFrame:
    """Trailing window statistics per site. Column name ``<feature>__<stat><months>``.

    The window covers the current month and the ``months - 1`` calendar months before it on the gap-free axis,
    so a missing month shortens the window instead of being filled. A window without any valid value is NaN.
    """
    cols = list(columns)
    for w in windows:
        for stat in stats:
            parse_column(window_column(cols[0] if cols else "x", stat, w))
    out = df.sort_values(["site_id", "month"]).reset_index(drop=True)
    parts = []
    for _, g in out.groupby("site_id", sort=False):
        idx = pd.DatetimeIndex(g["month"])
        full = pd.date_range(idx.min(), idx.max(), freq="MS")
        frame = g[cols].astype("float64").set_axis(idx).reindex(full)
        pieces = []
        for w in windows:
            r = frame.rolling(w, min_periods=1)
            for stat in stats:
                a = getattr(r, stat)().reindex(idx)
                a.columns = [window_column(c, stat, w) for c in cols]
                pieces.append(a)
        parts.append(pd.concat(pieces, axis=1).set_axis(g.index))
    return pd.concat([out, pd.concat(parts)], axis=1)


def input_columns(features: Sequence[str], windows: Sequence[int] = (),
                  stats: Sequence[str] = ("mean",)) -> list[str]:
    cols = list(features)
    for w in windows:
        for stat in stats:
            cols += [window_column(c, stat, w) for c in features if c in FEATURE_COLUMNS]
    return cols


def design_matrix(df: pd.DataFrame, features: Sequence[str], windows: Sequence[int] = (),
                  stats: Sequence[str] = ("mean",), track: str = "A") -> tuple[pd.DataFrame, pd.DataFrame]:
    """(keys, X): keys are ``site_id`` and ``month`` (plus every non-input column of `df`), X the guarded inputs."""
    sentinel = [c for c in features if c in FEATURE_COLUMNS]
    work = add_windows(df, sentinel, windows, stats) if windows else df.sort_values(
        ["site_id", "month"]).reset_index(drop=True)
    cols = assert_model_inputs(input_columns(features, windows, stats), track=track)
    missing = [c for c in cols if c not in work.columns]
    if missing:
        raise ValueError(f"input columns absent from the table: {missing}")
    keys = work.drop(columns=[c for c in work.columns if c in set(FEATURE_COLUMNS) | set(cols)])
    return keys, work[cols].astype("float64")


def usable_month(df: pd.DataFrame) -> pd.Series:
    """A month has usable imagery if Sentinel-2 passed its quality flags with valid centre pixels, or Sentinel-1
    has valid centre pixels (assumption M4). Used for the 'at least 2 usable months' rule of plan 2.4."""
    def col(c: str) -> pd.Series:
        return df[c] if c in df else pd.Series(float("nan"), index=df.index)

    s2 = (col("s2_qc_flag").fillna(1) == 0) & (col("s2_valid_c").fillna(0) > 0)
    s1 = col("s1_valid_c").fillna(0) > 0
    return (s2 | s1).rename("usable")
