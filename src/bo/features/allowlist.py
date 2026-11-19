"""The only columns detection and timeline code may use as model inputs (task 3.2, circularity guard).

Every name is computed from the chip pixels of one site and one month (or the trailing months of the same
series). None is a registry field, date, capacity or site identity. ``tests/test_features.py`` checks that
``bo.data.registry.registry_columns`` and this list never intersect and that ``site_features`` returns
exactly ``ID_COLUMNS + FEATURE_COLUMNS``.

``ID_COLUMNS`` are join keys, not features: models must drop them.
``EXPERIMENTAL`` marks columns whose index formula is UNVERIFIED in ``docs/research/pv_spectral_indices.md``;
Phase 4 reports every headline metric with and without them (assumption F5).
Physical rationale per column: ``docs/research/signatures.md``.
"""

from __future__ import annotations

ID_COLUMNS: tuple[str, ...] = ("site_id", "month")

_S2_IDX = ("ndvi", "ndbi", "mndwi", "ndpi", "plastic", "r1108", "r1208", "vnir", "b11")
_S2_YOY = ("ndvi_c", "ndvi_ctr", "ndbi_c", "ndpi_c", "r1108_c", "vnir_c", "b11_c")

FEATURE_COLUMNS: tuple[str, ...] = (
    # Sentinel-2 coverage and quality (observation density is information, never imputed)
    "s2_qc_flag", "s2_valid_c", "s2_nobs_c", "s2_n_valid_12",
    # Sentinel-2 indices: centre median and centre minus ring
    *[f"s2_{i}_{k}" for i in _S2_IDX for k in ("c", "ctr")],
    # Sentinel-2 texture of B08 in the centre and its contrast with the ring
    "s2_b08_tex_c", "s2_b08_tex_ctr", "s2_b08_grad_c",
    # Sentinel-2 change against the same month one year earlier
    *[f"s2_{c}_yoy" for c in _S2_YOY],
    # Sentinel-2 temporal stability (trailing 12 months)
    "s2_ndvi_c_sd12", "s2_vnir_c_sd12",
    # Sentinel-1 coverage
    "s1_n_scenes", "s1_valid_c", "s1_n_valid_12",
    # Sentinel-1 levels (dB) and polarisation ratio (VV minus VH in dB)
    "s1_vv_c", "s1_vh_c", "s1_vvvh_c", "s1_vv_p90_c",
    "s1_vv_ctr", "s1_vh_ctr", "s1_vvvh_ctr",
    # Sentinel-1 change against the same month one year earlier
    "s1_vv_c_yoy", "s1_vh_c_yoy", "s1_vvvh_c_yoy", "s1_vv_ctr_yoy",
    # Sentinel-1 temporal stability (coefficient of variation in linear power, trailing 12 months)
    "s1_vv_c_cv12", "s1_vh_c_cv12",
)

EXPERIMENTAL: tuple[str, ...] = tuple(
    c for c in FEATURE_COLUMNS if any(c.startswith(f"s2_{i}_") for i in ("ndvi", "ndbi", "mndwi")))

assert len(set(FEATURE_COLUMNS)) == len(FEATURE_COLUMNS)
