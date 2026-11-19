"""Gradient-boosted monthly detector per technology (Task A: is technology c present at this chip in this month).

scikit-learn `HistGradientBoostingClassifier` handles missing months natively (NaN goes to a learned branch, nothing
is imputed), which is why LightGBM is not needed. One binary model per technology gives p_c,t (plan 2.4); a chip with
both technologies is positive for both. Single months use ``windows=()``; short temporal windows add trailing
statistics of 2 to 12 months (`assemble.add_windows`).

Calibration: Platt scaling (sigmoid) fitted on out-of-fold scores of an inner split by spatial block inside the
training data (`CalibratedClassifierCV`, ``ensemble=False``). Tuning: inner cross-validation by block over the
training folds only (plan 4.4). Every fit refuses fold 0 and months after DEV_END.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold

from bo import paths

from . import design
from .assemble import design_matrix
from .guards import LeakageError, assert_dev_months, assert_no_test_fold, assert_site_in_one_fold

HYPERPARAMETERS = ("learning_rate", "max_iter", "max_leaf_nodes", "min_samples_leaf", "l2_regularization")


@dataclass(frozen=True)
class DetectorConfig:
    technology: str
    features: tuple[str, ...]
    windows: tuple[int, ...] = ()
    window_stats: tuple[str, ...] = ("mean",)
    track: str = "A"
    learning_rate: float = 0.05
    max_iter: int = 200
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 20
    l2_regularization: float = 1.0
    calibration: str = "sigmoid"
    inner_splits: int = 3
    seed: int = paths.SEED
    notes: dict = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        if self.technology not in design.TECHNOLOGIES:
            raise ValueError(f"technology must be one of {design.TECHNOLOGIES}")

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("notes")
        return d

    def hyperparameters(self) -> dict:
        return {k: getattr(self, k) for k in HYPERPARAMETERS}

    def component(self) -> str:
        return f"detector_{self.technology}_track{self.track}"


def _hgb(cfg: DetectorConfig) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=cfg.learning_rate, max_iter=cfg.max_iter, max_leaf_nodes=cfg.max_leaf_nodes,
        min_samples_leaf=cfg.min_samples_leaf, l2_regularization=cfg.l2_regularization,
        early_stopping=False, random_state=cfg.seed)


def _inner_splits(groups: np.ndarray, n: int) -> list[tuple[np.ndarray, np.ndarray]]:
    k = min(n, len(np.unique(groups)))
    if k < 2:
        raise LeakageError("inner split needs at least 2 spatial blocks in the training data")
    return list(GroupKFold(n_splits=k).split(np.zeros(len(groups)), groups=groups))


def training_rows(df: pd.DataFrame, cfg: DetectorConfig) -> pd.DataFrame:
    """Rows of `df` for technology c with a known target; asserts the leakage guards."""
    d = df[(df["technology"] == cfg.technology) & df["y"].notna()]
    assert_no_test_fold(d["fold"], "fit")
    assert_dev_months(d["month"], "fit")
    assert_site_in_one_fold(d)
    if d["y"].nunique() < 2:
        raise ValueError(f"{cfg.technology}: training rows hold one class only")
    return d


class Detector:
    """Fitted, calibrated detector for one technology."""

    def __init__(self, cfg: DetectorConfig):
        self.cfg = cfg
        self.model: CalibratedClassifierCV | None = None
        self.columns: list[str] = []

    def fit(self, df: pd.DataFrame) -> Detector:
        """`df`: feature rows joined with targets (``technology``, ``y``) and folds (``fold``, ``block_id``)."""
        d = training_rows(df, self.cfg)
        keys, x = design_matrix(d, self.cfg.features, self.cfg.windows, self.cfg.window_stats, self.cfg.track)
        y = keys["y"].astype(int).to_numpy()
        cv = _inner_splits(keys["block_id"].to_numpy(), self.cfg.inner_splits)
        self.model = CalibratedClassifierCV(_hgb(self.cfg), method=self.cfg.calibration, cv=cv,
                                            ensemble=False)
        self.model.fit(x.to_numpy(), y)
        self.columns = list(x.columns)
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calibrated p_c,t per row of `df` (one technology). Returns keys plus ``p``."""
        if self.model is None:
            raise RuntimeError("detector is not fitted")
        keys, x = design_matrix(df, self.cfg.features, self.cfg.windows, self.cfg.window_stats, self.cfg.track)
        if list(x.columns) != self.columns:
            raise ValueError("input columns differ from the fitted ones")
        out = keys.copy()
        out["p"] = self.model.predict_proba(x.to_numpy())[:, 1]
        return out


def oof_predictions(df: pd.DataFrame, cfg: DetectorConfig,
                    folds: Sequence[int] = design.DEV_FOLDS) -> pd.DataFrame:
    """Out-of-fold p_c,t on development folds: each fold is predicted by a model fitted on the other development
    folds, all rows up to DEV_END. Fold 0 is refused."""
    assert_no_test_fold(folds, "out-of-fold prediction")
    d = df[(df["technology"] == cfg.technology) & df["fold"].isin(folds) & (df["month"] <= design.DEV_END)]
    assert_no_test_fold(d["fold"], "out-of-fold prediction")
    parts = []
    for k in folds:
        train = d[d["fold"] != k]
        test = d[d["fold"] == k]
        if test.empty:
            continue
        det = Detector(cfg).fit(train)
        parts.append(det.predict(test))
    return pd.concat(parts, ignore_index=True)


def default_grid(base: DetectorConfig) -> list[DetectorConfig]:
    """Small grid ordered from simple to complex; ties in the tuning loss go to the earlier (simpler) entry."""
    grid = []
    for leaves in (7, 15):
        for it in (100, 300):
            for lr in (0.05, 0.1):
                grid.append(replace(base, max_leaf_nodes=leaves, max_iter=it, learning_rate=lr))
    return grid


def tune(df: pd.DataFrame, base: DetectorConfig, grid: Sequence[DetectorConfig] | None = None
         ) -> tuple[DetectorConfig, pd.DataFrame]:
    """Inner cross-validation by spatial block on the training rows only (plan 4.4). Loss: mean log loss of the
    calibrated monthly probability over inner folds. Returns the chosen configuration and the loss table."""
    d = training_rows(df, base)
    blocks = d["block_id"].to_numpy()
    splits = _inner_splits(blocks, base.inner_splits + 1)
    rows = []
    for i, cfg in enumerate(grid or default_grid(base)):
        losses = []
        for tr, te in splits:
            a, b = d.iloc[tr], d.iloc[te]
            if a["y"].nunique() < 2 or a["block_id"].nunique() < 2:
                continue
            p = Detector(cfg).fit(a).predict(b)
            losses.append(log_loss(p["y"].astype(int).to_numpy(), p["p"].to_numpy(), labels=[0, 1]))
        rows.append({"rank_simple": i, **cfg.hyperparameters(), "loss": float(np.mean(losses)),
                     "n_inner": len(losses)})
    table = pd.DataFrame(rows)
    best = int(table.sort_values(["loss", "rank_simple"]).iloc[0]["rank_simple"])
    return list(grid or default_grid(base))[best], table
