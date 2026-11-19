"""Centre versus ring contrast and texture on a chip grid.

The centre is the chip centre, which is the candidate location (registry coordinate for pilot sites, grid
cell for the national scan). No registry attribute sets a radius. Defaults are assumption F1
(``docs/assumptions.md``): centre disk radius 40 m, ring 150 to 300 m, the same geometry as the R3 test (A32).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

CENTRE_RADIUS_M = 40.0
RING_INNER_M = 150.0
RING_OUTER_M = 300.0
# A centre statistic needs at least this share of centre pixels valid (assumption F2).
MIN_VALID_FRAC = 0.5


def radius_map(n: int, res: float) -> np.ndarray:
    """Distance in metres of each pixel centre from the chip centre (n x n)."""
    c = (np.arange(n) + 0.5) * res - n * res / 2.0
    xx, yy = np.meshgrid(c, c)
    return np.hypot(xx, yy)


def disk_ring_masks(n: int, res: float, r_centre: float = CENTRE_RADIUS_M,
                    r_in: float = RING_INNER_M, r_out: float = RING_OUTER_M) -> tuple[np.ndarray, np.ndarray]:
    r = radius_map(n, res)
    return r <= r_centre, (r >= r_in) & (r <= r_out)


def masked_median(values: np.ndarray, mask: np.ndarray, min_valid_frac: float = MIN_VALID_FRAC
                  ) -> tuple[np.ndarray, np.ndarray]:
    """values (T, H, W) -> (median over mask per T, valid fraction per T). NaN below min_valid_frac."""
    v = values[:, mask]
    ok = np.isfinite(v)
    frac = ok.mean(axis=1) if v.shape[1] else np.zeros(values.shape[0])
    med = np.full(values.shape[0], np.nan)
    good = frac >= min_valid_frac
    if good.any():
        with np.errstate(all="ignore"):
            med[good] = np.nanmedian(v[good], axis=1)
    return med, frac


def masked_quantile(values: np.ndarray, mask: np.ndarray, q: float,
                    min_valid_frac: float = MIN_VALID_FRAC) -> np.ndarray:
    v = values[:, mask]
    frac = np.isfinite(v).mean(axis=1) if v.shape[1] else np.zeros(values.shape[0])
    out = np.full(values.shape[0], np.nan)
    good = frac >= min_valid_frac
    if good.any():
        out[good] = np.nanquantile(v[good], q, axis=1)
    return out


def centre_ring(values: np.ndarray, centre: np.ndarray, ring: np.ndarray,
                min_valid_frac: float = MIN_VALID_FRAC) -> dict[str, np.ndarray]:
    """Centre median, ring median, contrast (centre minus ring) and centre valid fraction, per month."""
    c, fc = masked_median(values, centre, min_valid_frac)
    r, _ = masked_median(values, ring, min_valid_frac)
    return {"c": c, "ring": r, "ctr": c - r, "valid_c": fc}


def local_std(img: np.ndarray, size: int = 3) -> np.ndarray:
    """Standard deviation in a size x size window over finite pixels; NaN where the window has fewer
    than size*size//2 + 1 finite pixels."""
    ok = np.isfinite(img)
    x = np.where(ok, img, 0.0)
    n = ndimage.uniform_filter(ok.astype(float), size, mode="constant") * size * size
    s1 = ndimage.uniform_filter(x, size, mode="constant") * size * size
    s2 = ndimage.uniform_filter(x * x, size, mode="constant") * size * size
    with np.errstate(all="ignore"):
        mean = s1 / n
        var = np.maximum(s2 / n - mean * mean, 0.0)
    out = np.sqrt(var)
    out[n < size * size // 2 + 1] = np.nan
    out[~ok] = np.nan
    return out


def grad_mag(img: np.ndarray) -> np.ndarray:
    """Sobel gradient magnitude per metre of pixel units (NaN where any neighbour is missing)."""
    ok = np.isfinite(img)
    x = np.where(ok, img, 0.0)
    gx = ndimage.sobel(x, axis=1, mode="nearest") / 8.0
    gy = ndimage.sobel(x, axis=0, mode="nearest") / 8.0
    g = np.hypot(gx, gy)
    bad = ndimage.minimum_filter(ok.astype(np.uint8), size=3, mode="nearest") == 0
    g[bad] = np.nan
    return g


def texture_series(values: np.ndarray, centre: np.ndarray, min_valid_frac: float = MIN_VALID_FRAC
                   ) -> dict[str, np.ndarray]:
    """values (T, H, W): centre median of 3x3 local std and of gradient magnitude, per month."""
    t = values.shape[0]
    ls = np.stack([local_std(values[i]) for i in range(t)]) if t else values
    gm = np.stack([grad_mag(values[i]) for i in range(t)]) if t else values
    return {"tex": masked_median(ls, centre, min_valid_frac)[0],
            "grad": masked_median(gm, centre, min_valid_frac)[0]}
