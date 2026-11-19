"""Surface reflectance from L2A digital numbers, including the processing-baseline offset.

Docs: ``docs/research/sentinel2.md`` facts 13 to 15 and ``docs/research/access_platforms.md``
fact 33. For baseline >= 04.00 (operational 2022-01-25) reflectance is
``(DN + BOA_ADD_OFFSET) / 10000`` with ``BOA_ADD_OFFSET = -1000``; DN 0 is no data.
Planetary Computer serves the raw (unharmonised) values, so the offset is applied here per item
from ``s2:processing_baseline``, not by acquisition date. Do not apply it to platforms that
already harmonise (Google Earth Engine ``S2_SR_HARMONIZED``, Sentinel Hub default).
"""

from __future__ import annotations

import numpy as np

from .config import BOA_ADD_OFFSET, OFFSET_BASELINE, QUANTIFICATION


def parse_baseline(baseline: str | float | None) -> tuple[int, int]:
    """'05.10' -> (5, 10). Raises ValueError for missing or malformed values."""
    if baseline is None:
        raise ValueError("processing baseline missing")
    s = str(baseline).strip()
    parts = s.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"cannot parse processing baseline {baseline!r}")
    return int(parts[0]), int(parts[1])


def needs_offset(baseline: str | float | None) -> bool:
    return parse_baseline(baseline) >= OFFSET_BASELINE


def dn_to_reflectance(
    dn: np.ndarray, baseline: str | float | None, harmonised_input: bool = False
) -> np.ndarray:
    """Convert L2A DN to reflectance on the pre-04.00 convention.

    DN 0 becomes NaN. Values are floored at 0 for both baselines so old (clipped) and new
    (offset) scenes share one convention; this removes the +0.1 step at 2022-01-25.
    With ``harmonised_input=True`` the platform has already applied the offset and none is applied.
    """
    dn = np.asarray(dn)
    out = dn.astype(np.float32)
    nodata = dn == 0
    if not harmonised_input and needs_offset(baseline):
        out = out + np.float32(BOA_ADD_OFFSET)
    out = np.maximum(out, 0.0) / np.float32(QUANTIFICATION)
    out[nodata] = np.nan
    return out
