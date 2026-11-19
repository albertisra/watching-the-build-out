"""Detector side of the shared model freeze (plan 3.3, 9). One freeze file, one lock, owned by `bo.timeline.guard`.

The freeze `results/timeline/model_freeze.json` is written once, when tuning of all components ends, through
`bo.timeline.guard.write_model_freeze` (which refuses to overwrite and checks the features against the allow-list).
This module only builds the record and checks it:

* `freeze_record` turns the per-component configurations (for example ``detector_battery_trackA``,
  ``detector_pv_trackA`` and the timeline model) into one record with the keys the timeline guard requires
  (``config_hash``, ``features``, ``hyperparameters``, ``date``) plus ``components``: per component its configuration,
  input columns, hyperparameters and their SHA-256. ``features`` holds the Sentinel base features only; window
  statistics and DOP slot columns are listed per component.
* `require_freeze` refuses any run on fold 0 if the file is absent or lacks the component, or if the configuration
  about to run differs from the frozen one (hash mismatch).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from bo import paths
from bo.features.allowlist import FEATURE_COLUMNS
from bo.timeline.guard import MODEL_FREEZE, FreezeError, load_model_freeze, write_model_freeze

from . import design
from .guards import assert_model_inputs, parse_column

FREEZE_PATH = MODEL_FREEZE

__all__ = [
    "FREEZE_PATH",
    "FreezeError",
    "config_hash",
    "freeze_record",
    "guard_test_fold",
    "require_freeze",
    "write_freeze",
]


def _canon(obj) -> object:
    return json.loads(json.dumps(obj, sort_keys=True, default=str))


def config_hash(config: Mapping) -> str:
    """SHA-256 of the configuration as canonical JSON (sorted keys, no whitespace)."""
    blob = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def freeze_record(components: Mapping[str, Mapping], now: str | None = None) -> dict:
    """`components`: name -> {"config": ..., "features": [...], "hyperparameters": {...}}."""
    comps = {}
    base: set[str] = set()
    for name, c in components.items():
        feats = assert_model_inputs(list(c["features"]), track="B")  # every component input is allow-listed
        base |= {parse_column(f)[0] for f in feats if parse_column(f)[0] in FEATURE_COLUMNS}
        comps[name] = {"config_hash": config_hash(c["config"]), "config": _canon(c["config"]),
                       "features": feats, "hyperparameters": _canon(c["hyperparameters"])}
    return {
        "config_hash": config_hash({n: v["config_hash"] for n, v in comps.items()}),
        "features": sorted(base),
        "hyperparameters": {n: v["hyperparameters"] for n, v in comps.items()},
        "date": now or datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": paths.SEED,
        "components": comps,
    }


def write_freeze(components: Mapping[str, Mapping], path: Path | None = None, now: str | None = None) -> Path:
    """Write the single freeze record (once; the timeline guard refuses a second write)."""
    return write_model_freeze(freeze_record(components, now), path)


def require_freeze(component: str, config: Mapping, path: Path | None = None) -> dict:
    """Return the frozen component entry; raise `FreezeError` if absent or if `config` differs from it."""
    rec = load_model_freeze(path)
    comp = rec.get("components", {}).get(component)
    if comp is None:
        raise FreezeError(f"component {component!r} is not in the model freeze: fold {design.TEST_FOLD} stays "
                          "locked (plan 3.3)")
    if comp["config_hash"] != config_hash(config):
        raise FreezeError(f"configuration of {component!r} differs from the frozen one (hash mismatch)")
    return comp


def guard_test_fold(folds: Iterable[int], component: str, config: Mapping, path: Path | None = None) -> None:
    """Call before any prediction or evaluation: if fold 0 is among `folds`, the freeze must exist and match."""
    if design.TEST_FOLD in {int(f) for f in folds}:
        require_freeze(component, config, path)
