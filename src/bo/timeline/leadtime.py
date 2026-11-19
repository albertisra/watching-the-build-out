"""The only place where registry dates meet detected starts (plan 3.3 and 7.3).

Every entry point first calls ``require_model_freeze``: without ``results/timeline/model_freeze.json``
nothing here runs. The lead-time estimators themselves (NPMLE in ``bo.timeline.npmle``) take intervals
and know nothing about the registry.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bo.timeline.guard import require_model_freeze


def join_registry_dates(detected: pd.DataFrame, registry: pd.DataFrame, freeze_path=None
                        ) -> pd.DataFrame:
    """Join site registry dates to detected starts by ``site_id``. Refuses to run before the freeze."""
    require_model_freeze(freeze_path)
    return detected.merge(registry, on="site_id", how="left", validate="one_to_one")


def lead_interval(start_month_index: np.ndarray, registry_fractional_month: np.ndarray,
                  upper_bound: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Monthly interval censoring of plan 2.5: the true lead lies in (r - s - 1, r - s].

    ``upper_bound`` (censoring or truncation bound on the lead scale, e.g. T_x - s) clips the upper end:
    an observed event is known to lie below it, and leaving the interval unclipped breaks coarsening at
    random and biases the NPMLE (``results/timeline/simulation_diagnosis.md``, item 3).
    """
    s = np.asarray(start_month_index, float)
    r = np.asarray(registry_fractional_month, float)
    lo, hi = r - s - 1.0, r - s
    if upper_bound is not None:
        hi = np.minimum(hi, np.asarray(upper_bound, float))
        if np.any(~(lo < hi)):
            raise ValueError("an event lies at or above its censoring bound")
    return lo, hi
