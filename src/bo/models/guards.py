"""Circularity and leakage guards of the detector (plan Section 3 and 4).

Model inputs come from an explicit allow-list only:

* Track A: the imagery features of `bo.features.allowlist.FEATURE_COLUMNS`, and trailing window statistics of
  them named ``<feature>__<stat><months>`` (for example ``s1_vv_c_yoy__mean3``).
* Track B additionally: the DOP slot columns of `bo.models.trackb.DOP_FEATURE_COLUMNS`.

Every input column set passes four independent checks: the allow-list, the registry deny-list of
`bo.data.registry.registry_columns`, the name patterns of plan 3.2, and the label-metadata deny-list
`LABEL_METADATA_COLUMNS` (evaluation metadata from `bo.models.targets`, such as ``coord_coarse``, refused by name
even if an allow-list ever grew to include it). If `bo.timeline.assert_no_registry_inputs`
exists (written in parallel by the timeline owner), the Sentinel base columns are also passed through it.

Leakage guards: fold 0 never enters a fit; one site never sits in two folds; fitted rows end at DEV_END.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

from bo.data.registry import registry_columns
from bo.features.allowlist import FEATURE_COLUMNS
from bo.labelling.schema import CONF_COLUMNS
from bo.timeline.guard import CircularityError, assert_no_registry_inputs

from . import design

# Plan 3.2: any column whose name contains one of these is refused, allow-listed or not.
DENY_PATTERNS: tuple[str, ...] = ("reg_", "commission", "registr", "status", "mastr", "inbetrieb", "kwh",
                                  "power", "capacity")

# Label and target metadata (bo.models.targets): evaluation only, never a model input.
LABEL_METADATA_COLUMNS: tuple[str, ...] = (
    "y", "state", "present", "colocated_target", "site_class", "colocated", "confidence", "onset_conf",
    "registry_date_exposed", "coord_coarse", "label_pass_used", "dop_identity", "dop_footprint", "onset", "brackets",
    "labeller_id", "label_id", "track", *CONF_COLUMNS)

WINDOW_SEP = "__"
WINDOW_STATS: tuple[str, ...] = ("mean", "max", "min")
MAX_WINDOW_MONTHS = 12
_WINDOW_RE = re.compile(r"^(mean|max|min)(\d{1,2})$")

# Track B slot (defined here to avoid an import cycle with trackb.py, which re-exports it).
DOP_FEATURE_COLUMNS: tuple[str, ...] = ("dop_p_battery", "dop_p_pv", "dop_months_since_flight")


class LeakageError(RuntimeError):
    """A fit would use the test fold, months after DEV_END, or a site split across folds."""


def window_column(base: str, stat: str, months: int) -> str:
    return f"{base}{WINDOW_SEP}{stat}{months}"


def parse_column(col: str) -> tuple[str, str | None, int | None]:
    """(base feature, window stat, window months); stat and months are None for a base column."""
    if WINDOW_SEP not in col:
        return col, None, None
    base, suffix = col.split(WINDOW_SEP, 1)
    m = _WINDOW_RE.match(suffix)
    if not m:
        raise CircularityError(f"{col!r}: unknown window suffix {suffix!r}")
    return base, m.group(1), int(m.group(2))


def allowed_base_columns(track: str = "A") -> tuple[str, ...]:
    if track == "A":
        return FEATURE_COLUMNS
    if track == "B":
        return FEATURE_COLUMNS + DOP_FEATURE_COLUMNS
    raise ValueError(f"track must be 'A' or 'B', not {track!r}")


def _timeline_guard():
    try:
        from bo.timeline import assert_no_registry_inputs
    except ImportError:
        return None
    return assert_no_registry_inputs


def assert_model_inputs(columns: Iterable[str], track: str = "A") -> list[str]:
    """Raise `CircularityError` unless every column is an allowed model input. Returns the columns."""
    cols = list(columns)
    if not cols:
        raise CircularityError("no model input columns")
    if len(set(cols)) != len(cols):
        raise CircularityError("duplicate model input columns")
    lowered = {c: c.lower() for c in cols}
    hits = [c for c, lc in lowered.items() if any(p in lc for p in DENY_PATTERNS)]
    if hits:
        raise CircularityError(f"deny-listed name pattern in model inputs: {hits}")
    meta = [c for c in cols if parse_column(c)[0] in LABEL_METADATA_COLUMNS]
    if meta:
        raise CircularityError(f"label metadata in model inputs (evaluation only): {meta}")
    reg = registry_columns(pd.DataFrame(columns=cols))
    if reg:
        raise CircularityError(f"registry columns in model inputs: {reg}")
    allowed = set(allowed_base_columns(track))
    bases = []
    for c in cols:
        base, stat, months = parse_column(c)
        if base not in allowed:
            raise CircularityError(f"{c!r} is not on the track {track} allow-list")
        if stat is not None and (base in DOP_FEATURE_COLUMNS or not 1 <= months <= MAX_WINDOW_MONTHS):
            raise CircularityError(f"{c!r}: window statistics are allowed on Sentinel features, 1 to 12 months")
        bases.append(base)
    sentinel = sorted({b for b in bases if b in FEATURE_COLUMNS})
    if sentinel:
        assert_no_registry_inputs(sentinel)
    return cols


def assert_no_test_fold(folds: Iterable[int], what: str = "fit") -> None:
    """Plan 4.2: test-fold sites are never used in fitting, in any month."""
    f = pd.Series(list(folds))
    if f.isna().any():
        raise LeakageError(f"{what}: rows without a fold")
    if (f.astype(int) == design.TEST_FOLD).any():
        raise LeakageError(f"{what}: rows of the locked test fold {design.TEST_FOLD}")


def assert_dev_months(months: Iterable, what: str = "fit") -> None:
    """Plan 4.2: every fitted quantity uses months up to DEV_END only."""
    m = pd.DatetimeIndex(pd.Series(list(months)))
    if len(m) and m.max() > design.DEV_END:
        raise LeakageError(f"{what}: months after {design.DEV_END:%Y-%m} (temporal hold-out)")


def assert_site_in_one_fold(df: pd.DataFrame, site_col: str = "site_id", fold_col: str = "fold") -> None:
    n = df.groupby(site_col)[fold_col].nunique()
    bad = n[n > 1]
    if len(bad):
        raise LeakageError(f"sites in more than one fold: {list(bad.index[:5])}")


def assert_disjoint_sites(train: pd.DataFrame, test: pd.DataFrame, site_col: str = "site_id") -> None:
    both = set(train[site_col]) & set(test[site_col])
    if both:
        raise LeakageError(f"sites in both train and test: {sorted(both)[:5]}")
