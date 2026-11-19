"""Monthly feature table for one chip series (64 x 64 at 10 m by default, any square size works).

Input: an ``xarray.Dataset`` in the chip-store layout (``docs/imagery_chip_store.md``), from
``bo.imagery.store.read_series`` so that one series never mixes platforms. Sentinel-1 or Sentinel-2 may be
absent; their columns are then NaN. Output: one row per month, columns ``ID_COLUMNS + FEATURE_COLUMNS``.

Missing data: a month without clear pixels gives NaN features and count 0. Months that fail the A40 quality
flags (``s2_flag_bright``, ``s2_flag_cld_disagree``) give NaN Sentinel-2 features and ``s2_qc_flag = 1``.
Nothing is interpolated. No registry attribute is read: the only inputs are pixels, the month axis and the
grid geometry stored in the chip attributes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import xarray as xr

from . import spatial, temporal
from .allowlist import FEATURE_COLUMNS, ID_COLUMNS
from .indices import compute_index

S2_INDICES = ("ndvi", "ndbi", "mndwi", "ndpi", "plastic", "r1108", "r1208", "vnir", "b11")


@dataclass(frozen=True)
class FeatureConfig:
    r_centre: float = spatial.CENTRE_RADIUS_M
    r_in: float = spatial.RING_INNER_M
    r_out: float = spatial.RING_OUTER_M
    min_valid_frac: float = spatial.MIN_VALID_FRAC


def _geometry(ds: xr.Dataset) -> tuple[int, float]:
    n = int(ds.sizes["y"])
    if int(ds.sizes["x"]) != n:
        raise ValueError("chip must be square")
    res = float(ds.attrs.get("resolution_m", 10.0))
    return n, res


def s2_quality_mask(ds: xr.Dataset) -> np.ndarray:
    """True for months whose Sentinel-2 composite fails a quality flag (A40)."""
    t = ds.sizes["month"]
    bad = np.zeros(t, bool)
    for v in ("s2_flag_bright", "s2_flag_cld_disagree", "s2_flag_range"):
        if v in ds:
            bad |= np.asarray(ds[v].values, bool)
    return bad


def s2_index_cube(ds: xr.Dataset, name: str) -> np.ndarray:
    """(T, H, W) index values with flagged months set to NaN."""
    refl = ds.s2_refl.values.astype("float64")
    bands = [str(b) for b in ds.band.values]
    cube = compute_index(name, refl, bands)
    cube[s2_quality_mask(ds)] = np.nan
    return cube


def site_features(ds: xr.Dataset, cfg: FeatureConfig | None = None, site_id: str | None = None
                  ) -> pd.DataFrame:
    cfg = cfg or FeatureConfig()
    n, res = _geometry(ds)
    centre, ring = spatial.disk_ring_masks(n, res, cfg.r_centre, cfg.r_in, cfg.r_out)
    months = pd.DatetimeIndex(ds.month.values)
    t = len(months)
    nan = np.full(t, np.nan)
    out: dict[str, np.ndarray] = {}
    mv = cfg.min_valid_frac

    # ---- Sentinel-2
    if "s2_refl" in ds:
        bad = s2_quality_mask(ds)
        out["s2_qc_flag"] = bad.astype(float)
        cnt = ds.s2_clear_count.values.astype("float64")
        cnt_c = cnt[:, centre]
        out["s2_nobs_c"] = np.where(bad, np.nan, np.median(cnt_c, axis=1))
        valid_c = None
        for name in S2_INDICES:
            cr = spatial.centre_ring(s2_index_cube(ds, name), centre, ring, mv)
            out[f"s2_{name}_c"], out[f"s2_{name}_ctr"] = cr["c"], cr["ctr"]
            if name == "vnir":
                valid_c = cr["valid_c"]
        out["s2_valid_c"] = np.where(bad, 0.0, valid_c if valid_c is not None else nan)
        b08 = s2_index_cube(ds, "b08")
        tex = spatial.texture_series(b08, centre, mv)
        tex_ring = spatial.texture_series(b08, ring, mv)
        out["s2_b08_tex_c"], out["s2_b08_grad_c"] = tex["tex"], tex["grad"]
        out["s2_b08_tex_ctr"] = tex["tex"] - tex_ring["tex"]
    else:
        out["s2_qc_flag"] = nan.copy()

    # ---- Sentinel-1
    if "s1_vv_db" in ds:
        vv = ds.s1_vv_db.values.astype("float64")
        vh = ds.s1_vh_db.values.astype("float64") if "s1_vh_db" in ds else np.full_like(vv, np.nan)
        for name, cube in (("vv", vv), ("vh", vh), ("vvvh", vv - vh)):
            cr = spatial.centre_ring(cube, centre, ring, mv)
            out[f"s1_{name}_c"], out[f"s1_{name}_ctr"] = cr["c"], cr["ctr"]
            if name == "vv":
                out["s1_valid_c"] = cr["valid_c"]
        out["s1_vv_p90_c"] = spatial.masked_quantile(vv, centre, 0.9, mv)
        out["s1_n_scenes"] = ds.s1_n_scenes.values.astype(float) if "s1_n_scenes" in ds else nan.copy()

    df = pd.DataFrame(out, index=months)

    # ---- temporal features (on the regular month axis, NaN never filled)
    def col(c):
        return df[c] if c in df else pd.Series(nan, index=months)

    for c in ("ndvi_c", "ndvi_ctr", "ndbi_c", "ndpi_c", "r1108_c", "vnir_c", "b11_c"):
        df[f"s2_{c}_yoy"] = temporal.yoy(col(f"s2_{c}"))
    df["s2_ndvi_c_sd12"] = temporal.trailing_std(col("s2_ndvi_c"))
    df["s2_vnir_c_sd12"] = temporal.trailing_std(col("s2_vnir_c"))
    df["s2_n_valid_12"] = temporal.trailing_count(col("s2_vnir_c"))
    for c in ("vv_c", "vh_c", "vvvh_c", "vv_ctr"):
        df[f"s1_{c}_yoy"] = temporal.yoy(col(f"s1_{c}"))
    df["s1_vv_c_cv12"] = temporal.trailing_cv_linear_db(col("s1_vv_c"))
    df["s1_vh_c_cv12"] = temporal.trailing_cv_linear_db(col("s1_vh_c"))
    df["s1_n_valid_12"] = temporal.trailing_count(col("s1_vv_c"))
    if "s2_refl" not in ds:
        df["s2_n_valid_12"] = np.nan
    if "s1_vv_db" not in ds:
        df["s1_n_valid_12"] = np.nan

    df = df.reindex(columns=list(FEATURE_COLUMNS))
    df.insert(0, "month", months)
    df.insert(0, "site_id", site_id or str(ds.attrs.get("site_id", "")))
    df = df.reset_index(drop=True)
    assert tuple(df.columns) == ID_COLUMNS + FEATURE_COLUMNS
    return df
