"""Feature frame to model input arrays (plan 6.1).

Input: a long frame from ``bo.features`` with ``ID_COLUMNS`` (``site_id``, ``month``) and allow-listed
feature columns. The frame is validated with ``assert_no_registry_inputs`` before anything is read.
Output per site: a complete calendar-month axis and a (T, d) array with NaN in months without a value.
Nothing is interpolated. Standardisation statistics come from ``fit_standardiser``, which takes the fold
map and refuses any row of the locked test fold 0 (development folds only, months up to 2025-10).

Registry fields: the only registry field that reaches the timeline is the site's registry technology,
used to select the technology-specific emission set (analysis plan v1.0, Sections 3.1 and 6.1) through
``emission_sets``. It never enters a model-input array: ``technology`` is not on the feature allow-list,
so ``assert_no_registry_inputs`` refuses it, like every other registry column, in ``to_series``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from bo.features.allowlist import FEATURE_COLUMNS
from bo.timeline.guard import TEST_FOLD, assert_no_registry_inputs, guard_folds

MAX_FEATURES = 6  # A73
# The one registry field the timeline may read (plan 3.1, 6.1), and the values it may take.
REGISTRY_FIELDS_TO_TIMELINE: tuple[str, ...] = ("technology",)
EMISSION_SETS: tuple[str, ...] = ("battery", "ground_pv")


@dataclass
class SiteSeries:
    site_id: str
    months: pd.PeriodIndex
    x: np.ndarray  # (T, d)
    features: tuple[str, ...]


@dataclass(frozen=True)
class Standardiser:
    features: tuple[str, ...]
    mean: np.ndarray
    sd: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.sd


def _as_fold_map(folds) -> dict[str, int]:
    if isinstance(folds, pd.DataFrame):
        from bo.timeline.splits import fold_map

        return fold_map(folds)
    if isinstance(folds, Mapping):
        return {str(k): int(v) for k, v in folds.items()}
    raise TypeError("folds must be a split table (bo.timeline.splits) or a site_id -> fold mapping")


def fit_standardiser(df: pd.DataFrame, features: list[str], folds, last_month: str = "2025-10"
                     ) -> Standardiser:
    """Mean and SD per feature over development-fold rows up to ``last_month`` (plan 6.1).

    ``folds`` is the split table of ``bo.timeline.splits`` (or a ``site_id -> fold`` mapping, e.g.
    ``splits.fold_map()``). Raises ``ValueError`` if any site of ``df`` has no fold or sits in the locked
    test fold 0: the caller must drop test-fold rows; they are never silently filtered.
    """
    assert_no_registry_inputs(df)
    fm = _as_fold_map(folds)
    sites = pd.Series(df["site_id"].astype(str).unique())
    missing = sites[~sites.isin(list(fm))]
    if len(missing):
        raise ValueError(f"{len(missing)} sites without a fold")
    test = sites[sites.map(fm) == TEST_FOLD]
    if len(test):
        raise ValueError(f"{len(test)} sites of the locked test fold {TEST_FOLD}: standardisation "
                         "statistics come from development folds only")
    m = pd.PeriodIndex(pd.to_datetime(df["month"]), freq="M")
    sub = df.loc[m <= pd.Period(last_month, "M"), features]
    sd = sub.std(ddof=0).to_numpy()
    if np.any(~np.isfinite(sd)) or np.any(sd <= 0):
        raise ValueError("a feature has zero or undefined spread in the fitting rows")
    return Standardiser(tuple(features), sub.mean().to_numpy(), sd)


def emission_sets(registry: pd.DataFrame, key: str = "site_id") -> dict[str, str]:
    """``site_id -> technology`` for the choice of emission set; the only registry read of the timeline.

    Only the ``key`` and ``technology`` columns are read; every other column of ``registry`` is ignored
    and cannot reach the return value. Values must be in ``EMISSION_SETS``.
    """
    cols = [key, *REGISTRY_FIELDS_TO_TIMELINE]
    sub = registry.loc[:, cols].copy()
    if sub[key].isna().any() or sub[key].duplicated().any():
        raise ValueError(f"{key} must be present and unique")
    bad = set(sub["technology"].dropna()) - set(EMISSION_SETS)
    if bad or sub["technology"].isna().any():
        raise ValueError(f"technology must be one of {EMISSION_SETS}; got {sorted(map(str, bad))}")
    return {str(k): str(t) for k, t in zip(sub[key], sub["technology"], strict=True)}


def group_by_emission_set(series: list[SiteSeries], tech: Mapping[str, str]) -> dict[str, list[SiteSeries]]:
    """Split site series by emission set. Only strings from ``EMISSION_SETS`` cross over."""
    out: dict[str, list[SiteSeries]] = {t: [] for t in EMISSION_SETS}
    for s in series:
        t = tech[s.site_id]
        if t not in out:
            raise ValueError(f"unknown emission set {t!r}")
        out[t].append(s)
    return out


def to_series(df: pd.DataFrame, features: list[str], folds: dict[str, int] | None = None,
              start: str | None = None, end: str | None = None,
              standardiser: Standardiser | None = None, freeze_path=None) -> list[SiteSeries]:
    """Validate the frame and return one series per site on a gap-free monthly axis.

    ``folds`` maps site_id to fold; sites of the locked test fold need the model freeze.
    """
    assert_no_registry_inputs(df)
    features = list(features)
    if not features or len(features) > MAX_FEATURES:
        raise ValueError(f"between 1 and {MAX_FEATURES} features (A73)")
    bad = [f for f in features if f not in FEATURE_COLUMNS]
    if bad:
        raise ValueError(f"features not on the allow-list: {bad}")
    if standardiser is not None and tuple(features) != standardiser.features:
        raise ValueError("standardiser fitted on other features")
    if folds is not None:
        present = {folds[s] for s in df["site_id"].unique() if s in folds}
        missing = set(df["site_id"].unique()) - set(folds)
        if missing:
            raise ValueError(f"{len(missing)} sites without a fold")
        if TEST_FOLD in present:
            guard_folds(present, freeze_path)
    d = df.copy()
    d["month"] = pd.PeriodIndex(pd.to_datetime(d["month"]), freq="M")
    if d.duplicated(["site_id", "month"]).any():
        raise ValueError("duplicate site-month rows")
    out = []
    for sid, g in d.groupby("site_id", sort=True):
        lo = pd.Period(start, "M") if start else g["month"].min()
        hi = pd.Period(end, "M") if end else g["month"].max()
        axis = pd.period_range(lo, hi, freq="M")
        x = g.set_index("month")[features].reindex(axis).to_numpy(float)
        if standardiser is not None:
            x = standardiser.transform(x)
        out.append(SiteSeries(str(sid), axis, x, tuple(features)))
    return out
