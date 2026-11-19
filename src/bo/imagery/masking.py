"""Sentinel-2 clear-pixel masks from the scene classification layer (SCL)."""

from __future__ import annotations

import numpy as np

from .config import CLEAR_RULES, DEFAULT_CLEAR_RULE


def clear_mask(scl: np.ndarray, rule: str | tuple[int, ...] = DEFAULT_CLEAR_RULE) -> np.ndarray:
    """True where the SCL class is in the clear set of ``rule``.

    Clouds (8, 9), cirrus (10), cloud shadow (3), snow or ice (11), saturated (1) and no data (0)
    are never clear under any rule. Under the default rule (A5) classes 2 and 7 are not clear
    either.
    """
    classes = CLEAR_RULES[rule] if isinstance(rule, str) else tuple(rule)
    return np.isin(scl, classes)
