"""Circularity and leakage guards for the timeline models (analysis plan v1.0, Section 3).

* ``assert_no_registry_inputs`` checks a model-input frame against the feature allow-list, the registry
  deny-list and a set of forbidden name fragments (plan 3.2).
* ``require_model_freeze`` refuses to continue without ``results/timeline/model_freeze.json``. It is
  called before any registry date is joined (``bo.timeline.leadtime``) and before anything touches the
  locked test fold 0 (plan 3.3).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from bo.data.registry import registry_columns
from bo.features.allowlist import FEATURE_COLUMNS, ID_COLUMNS
from bo.paths import RESULTS

TIMELINE_RESULTS = RESULTS / "timeline"
MODEL_FREEZE = TIMELINE_RESULTS / "model_freeze.json"
TEST_FOLD = 0
FREEZE_KEYS = ("config_hash", "features", "hyperparameters", "date")

# Plan 3.2: name fragments that never enter a timeline model, case-insensitive.
FORBIDDEN_FRAGMENTS = (
    "reg_", "commission", "registr", "status", "mastr", "inbetrieb", "kwh", "power", "capacity")
_FORBIDDEN_RE = re.compile("|".join(re.escape(f) for f in FORBIDDEN_FRAGMENTS), re.IGNORECASE)
# Named explicitly in plan 3.2; it also matches the "registr" fragment.
NEVER_INPUT = ("other_registered_sites_in_chip",)


class CircularityError(ValueError):
    """A registry field, or a column outside the imagery allow-list, reached a timeline model."""


class FreezeError(RuntimeError):
    """A step that needs the frozen model (registry join, test fold) ran before the freeze."""


def forbidden_columns(columns: Iterable[str]) -> dict[str, str]:
    """Map each offending column name to the reason it is refused."""
    cols = [str(c) for c in columns]
    deny = set(registry_columns(pd.DataFrame(columns=cols)))
    allowed = set(FEATURE_COLUMNS) | set(ID_COLUMNS)
    bad: dict[str, str] = {}
    for c in cols:
        if c in NEVER_INPUT:
            bad[c] = "named never-input column (plan 3.2)"
        elif c in deny:
            bad[c] = "on the registry deny-list (bo.data.registry.registry_columns)"
        elif _FORBIDDEN_RE.search(c):
            bad[c] = "matches a forbidden name fragment"
        elif c not in allowed:
            bad[c] = "not on the feature allow-list (bo.features.allowlist)"
    return bad


def assert_no_registry_inputs(df: pd.DataFrame | Iterable[str]) -> None:
    """Raise ``CircularityError`` if any column could carry registry timing, status or size.

    Accepts a frame or a list of column names. ID columns (``site_id``, ``month``) are join keys and pass.
    """
    cols = list(df.columns) if isinstance(df, pd.DataFrame) else list(df)
    bad = forbidden_columns(cols)
    if bad:
        detail = "; ".join(f"{c}: {r}" for c, r in sorted(bad.items()))
        raise CircularityError(f"refused model inputs: {detail}")


def load_model_freeze(path: Path | None = None) -> dict:
    """Return the freeze record, or raise ``FreezeError`` if it is absent or incomplete."""
    p = Path(path) if path is not None else MODEL_FREEZE
    if not p.is_file():
        raise FreezeError(
            f"{p.name} not found: the model is not frozen (plan 3.3). Registry dates cannot be "
            "joined and the test fold cannot be touched before tuning ends and the freeze is written.")
    rec = json.loads(p.read_text())
    missing = [k for k in FREEZE_KEYS if k not in rec]
    if missing:
        raise FreezeError(f"{p.name} lacks keys {missing}")
    return rec


def require_model_freeze(path: Path | None = None) -> dict:
    """Guard for the registry join and for any test-fold run."""
    return load_model_freeze(path)


def guard_folds(folds: Iterable[int], freeze_path: Path | None = None) -> None:
    """Refuse to touch the locked test fold 0 without the model freeze."""
    if TEST_FOLD in {int(f) for f in folds}:
        require_model_freeze(freeze_path)


def write_model_freeze(record: dict, path: Path | None = None) -> Path:
    """Write the freeze record once. Refuses to overwrite an existing freeze."""
    p = Path(path) if path is not None else MODEL_FREEZE
    missing = [k for k in FREEZE_KEYS if k not in record]
    if missing:
        raise FreezeError(f"freeze record lacks keys {missing}")
    assert_no_registry_inputs(list(record["features"]))
    if p.exists():
        raise FreezeError(f"{p.name} exists; a model is frozen once (plan 3.3)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, indent=2, sort_keys=True))
    return p
