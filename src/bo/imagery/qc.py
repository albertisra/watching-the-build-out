"""Per-month quality flags for Sentinel-2 composites (review finding I4). Months are flagged, never dropped.

``s2_flag_bright``: the clear-pixel median of the blue band (B02, else B03) over the chip exceeds 0.2. Snow,
haze and thin cloud that the SCL 4/5/6 rule lets through make winter composites this bright; normal land,
water and PV arrays do not (bare soil and white roofs can reach 0.2 only on a few pixels, not in the median).
``s2_flag_cld_disagree`` (Sentinel Hub stores only): the mean per-pixel count of CLD <= 30 percent is under half
the mean SCL 4/5/6 count, so the cloud-probability layer calls most of the 'clear' observations cloudy.
"""

from __future__ import annotations

import numpy as np

BRIGHT_THRESHOLD = 0.2
RANGE_MAX_REFLECTANCE = 1.0  # A89: a surface reflectance above 1 is outside the physical range
RANGE_CENTRE_RADIUS_M = 40.0  # same centre disk as the features (bo.features.spatial.CENTRE_RADIUS_M)


def flag_range(refl: np.ndarray, count: np.ndarray, res: float = 10.0) -> np.ndarray:
    """refl (T, B, H, W), count (T, H, W) -> bool (T,): centre-disk median of any band above 1.0 (A89).

    Only pixels with count > 0 and finite reflectance enter the median. Months with no such pixel are not flagged.
    """
    t, _, h, w = refl.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(yy - (h - 1) / 2.0, xx - (w - 1) / 2.0) * res
    disk = r <= RANGE_CENTRE_RADIUS_M
    out = np.zeros(t, bool)
    for i in range(t):
        ok = disk & (count[i] > 0)
        if not ok.any():
            continue
        for k in range(refl.shape[1]):
            v = refl[i, k][ok]
            v = v[np.isfinite(v)]
            if len(v) and np.median(v) > RANGE_MAX_REFLECTANCE:
                out[i] = True
                break
    return out


def flag_bright(refl: np.ndarray, count: np.ndarray, bands: list[str]) -> np.ndarray:
    """refl (T, B, H, W), count (T, H, W) -> bool (T,)."""
    band = "B02" if "B02" in bands else "B03" if "B03" in bands else None
    out = np.zeros(refl.shape[0], bool)
    if band is None:
        return out
    k = bands.index(band)
    for i in range(refl.shape[0]):
        v = refl[i, k]
        v = v[np.isfinite(v) & (count[i] > 0)]
        out[i] = bool(len(v) and np.median(v) > BRIGHT_THRESHOLD)
    return out


def flag_cld_disagree(count: np.ndarray, count_cld30: np.ndarray) -> np.ndarray:
    c = count.reshape(count.shape[0], -1).mean(axis=1)
    d = count_cld30.reshape(count_cld30.shape[0], -1).mean(axis=1)
    return (c > 0) & (d < 0.5 * c)


def add_flags(ds):
    """Add the flag variables to a chip dataset (in place) and return it."""
    if "s2_refl" not in ds:
        return ds
    bands = [str(b) for b in ds.band.values]
    ds["s2_flag_bright"] = (("month",), flag_bright(ds.s2_refl.values, ds.s2_clear_count.values, bands))
    ds["s2_flag_range"] = (("month",), flag_range(ds.s2_refl.values, ds.s2_clear_count.values,
                                                  float(ds.attrs.get("resolution_m", 10.0))))
    if "s2_clear_count_cld30" in ds:
        ds["s2_flag_cld_disagree"] = (("month",), flag_cld_disagree(
            ds.s2_clear_count.values, ds.s2_clear_count_cld30.values))
    ds.attrs["s2_flags"] = "s2_flag_bright (B02 or B03 clear-pixel median > 0.2), see qc.py; s2_flag_range (centre-disk median of any band > 1.0, A89); months are flagged, not dropped"
    return ds
