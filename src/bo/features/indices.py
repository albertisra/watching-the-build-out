"""Spectral indices and band statistics on Sentinel-2 surface reflectance.

Rules (task 3.2, KICKOFF 6.2):
- Only formulas marked VERIFIED in ``docs/research/pv_spectral_indices.md`` carry ``status="verified"``.
  Standard indices whose formula the research note lists as UNVERIFIED (its fact 3: NDVI, NDBI, MNDWI)
  carry ``status="experimental"``. Plain band levels, band ratios and band means need no formula source.
- Inputs are reflectance (0 to about 1) with NaN for missing; NaN propagates, nothing is filled.
- B11 and B12 are 20 m bands replicated onto the 10 m grid (assumption A30), so any index that uses them
  has 20 m effective resolution.

Physical rationale for each index is in ``docs/research/signatures.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

# Denominator guard for ratio-type indices (assumption F3 in docs/assumptions.md): below this absolute
# value the index is set to NaN instead of returning an unbounded number.
DENOM_EPS = 0.02


def _safe_div(num: np.ndarray, den: np.ndarray, eps: float = DENOM_EPS) -> np.ndarray:
    num = np.asarray(num, dtype="float64")
    den = np.asarray(den, dtype="float64")
    out = np.full(np.broadcast(num, den).shape, np.nan)
    ok = np.isfinite(num) & np.isfinite(den) & (np.abs(den) >= eps)
    np.divide(num, den, out=out, where=ok)
    return out


def norm_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b), NaN where a + b is below the guard."""
    a = np.asarray(a, dtype="float64")
    b = np.asarray(b, dtype="float64")
    return _safe_div(a - b, a + b)


def ndpi(b08, b11, b12):
    """NDPI = (B11 - B08) / (B08 - B12). Feng et al. 2024 (VERIFIED, pv_spectral_indices.md fact 1).

    Not a normalised difference: unbounded, and the denominator B08 - B12 crosses zero where NIR and
    SWIR2 reflectance are equal (bare dry soil, some roofs). Guarded by DENOM_EPS.
    """
    b08 = np.asarray(b08, dtype="float64")
    return _safe_div(np.asarray(b11, dtype="float64") - b08, b08 - np.asarray(b12, dtype="float64"))


def plastic_ig(b02, b03, b08):
    """Plastic-covered soil index, Ibrahim and Gobin 2021 Sentinel Hub script (VERIFIED script,
    pv_spectral_indices.md fact 8): B02 / (1 - (B02 + B03 + B08) / 3)."""
    b02 = np.asarray(b02, dtype="float64")
    m = (b02 + np.asarray(b03, dtype="float64") + np.asarray(b08, dtype="float64")) / 3.0
    return _safe_div(b02, 1.0 - m)


def ndvi(b04, b08):
    """(B08 - B04) / (B08 + B04). EXPERIMENTAL: standard formula, listed UNVERIFIED in the note (fact 3)."""
    return norm_diff(b08, b04)


def ndbi(b08, b11):
    """(B11 - B08) / (B11 + B08). EXPERIMENTAL (fact 3)."""
    return norm_diff(b11, b08)


def mndwi(b03, b11):
    """(B03 - B11) / (B03 + B11). EXPERIMENTAL (fact 3)."""
    return norm_diff(b03, b11)


def ratio(a, b):
    """Plain band ratio a / b (guarded)."""
    return _safe_div(a, b)


def vnir_mean(b02, b03, b04, b08):
    """Mean VNIR reflectance. Motivated by the aVNIR criterion of Ji et al. 2021 (low mean 500 to 1000 nm
    reflectance of crystalline PV, fact 6); this is a band mean, not their hyperspectral threshold."""
    return np.mean(np.stack([np.asarray(x, dtype="float64") for x in (b02, b03, b04, b08)]), axis=0)


@dataclass(frozen=True)
class IndexDef:
    name: str
    bands: tuple[str, ...]
    func: Callable
    status: str  # "verified", "experimental" or "band" (level, ratio or mean; no formula to verify)
    source: str


INDEX_DEFS: dict[str, IndexDef] = {d.name: d for d in [
    IndexDef("ndpi", ("B08", "B11", "B12"), ndpi, "verified", "pv_spectral_indices.md fact 1"),
    IndexDef("plastic", ("B02", "B03", "B08"), plastic_ig, "verified", "pv_spectral_indices.md fact 8"),
    IndexDef("ndvi", ("B04", "B08"), ndvi, "experimental", "pv_spectral_indices.md fact 3 (UNVERIFIED)"),
    IndexDef("ndbi", ("B08", "B11"), ndbi, "experimental", "pv_spectral_indices.md fact 3 (UNVERIFIED)"),
    IndexDef("mndwi", ("B03", "B11"), mndwi, "experimental", "pv_spectral_indices.md fact 3 (UNVERIFIED)"),
    IndexDef("r1108", ("B11", "B08"), ratio, "band", "pv_spectral_indices.md, 'What this means'"),
    IndexDef("r1208", ("B12", "B08"), ratio, "band", "pv_spectral_indices.md, 'What this means'"),
    IndexDef("vnir", ("B02", "B03", "B04", "B08"), vnir_mean, "band", "pv_spectral_indices.md fact 6"),
    IndexDef("b08", ("B08",), lambda x: np.asarray(x, dtype="float64"), "band", "band level"),
    IndexDef("b11", ("B11",), lambda x: np.asarray(x, dtype="float64"), "band", "band level"),
]}


def compute_index(name: str, refl: np.ndarray, bands: list[str]) -> np.ndarray:
    """refl (..., B, H, W) with band axis at -3. Returns (..., H, W); all NaN if a band is missing."""
    d = INDEX_DEFS[name]
    if not all(b in bands for b in d.bands):
        shape = refl.shape[:-3] + refl.shape[-2:]
        return np.full(shape, np.nan)
    args = [refl[..., bands.index(b), :, :] for b in d.bands]
    return d.func(*args)
