"""Zarr chip store with full metadata (rule 8 of KICKOFF: cached chips with provenance)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from bo import paths

from . import CODE_VERSION
from .config import ChipConfig
from .geo import ChipGrid

CHIP_DIR = paths.CHIPS / "v0"


def git_hash() -> str:
    try:
        r = subprocess.run(["git", "-C", str(paths.REPO_ROOT), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5, check=False)
        return r.stdout.strip() or "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def site_path(site_id: str, root: Path | None = None) -> Path:
    return (root or CHIP_DIR) / f"{site_id}.zarr"


def build_dataset(
    site_id: str, grid: ChipGrid, cfg: ChipConfig, s2: dict | None, s1: dict | None, start: str,
    end: str,
) -> xr.Dataset:
    xs, ys = grid.xy_coords()
    months = (s2 or s1)["months"].astype("datetime64[ns]")
    data = {}
    coords = {"month": months, "y": ys, "x": xs}
    attrs = {
        "site_id": site_id,
        "crs_epsg": grid.epsg,
        "transform": list(grid.transform)[:6],
        "bounds_xy": list(grid.bounds),
        "chip_size_px": grid.size,
        "resolution_m": grid.res,
        "time_start": start,
        "time_end": end,
        "code_version": f"{CODE_VERSION}+{git_hash()}",
        "source": "planetary_computer",
        "attribution": "Contains modified Copernicus Sentinel data 2015-2026",
        "missing_months": "NaN with count 0; never interpolated",
    }
    if s2 is not None:
        coords["band"] = list(cfg.bands)
        data["s2_refl"] = (("month", "band", "y", "x"), s2["refl"])
        data["s2_clear_count"] = (("month", "y", "x"), s2["count"])
        data["s2_clear_count_alt"] = (("month", "y", "x"), s2["count_alt"])
        data["s2_n_passes"] = (("month",), s2["n_passes"])
        data["s2_n_passes_used"] = (("month",), s2["n_used"])
        attrs.update({
            "s2_collection": "sentinel-2-l2a (Planetary Computer)",
            "s2_clear_rule": cfg.clear_rule,
            "s2_alt_rule": "scl_blacklist (2,4,5,6,7)",
            "s2_tile_rule": "native UTM zone tiles preferred; neighbouring-zone tiles are warped only for passes "
                            "without a native tile (review m10)",
            "s2_offset_policy": "baseline >= 04.00: DN-1000, floor 0, /10000 per item; DN 0 = nodata",
            "s2_items_by_month": s2["items_by_month"],
            "s2_processing_baseline_by_item": s2["baselines"],
        })
    if s1 is not None:
        data["s1_vv_db"] = (("month", "y", "x"), s1["vv_db"])
        data["s1_vh_db"] = (("month", "y", "x"), s1["vh_db"])
        data["s1_count"] = (("month", "y", "x"), s1["count"])
        data["s1_n_scenes"] = (("month",), s1["n_scenes"])
        attrs.update({
            "s1_collection": "sentinel-1-rtc (Planetary Computer), gamma0 terrain flattened",
            "s1_relative_orbit": s1["relative_orbit"],
            "s1_pass_direction": s1["direction"],
            "s1_orbit_candidates_orbit_dir_ndates": s1["orbit_candidates"],
            "s1_items_by_month": s1["items_by_month"],
            "s1_speckle_filter": s1["speckle"],
            "s1_polarisations": s1["pols"],
        })
    ds = xr.Dataset(data, coords=coords, attrs=attrs)
    from .qc import add_flags

    return add_flags(ds)


def write_site(ds: xr.Dataset, site_id: str, root: Path | None = None) -> Path:
    p = site_path(site_id, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.rmtree(p)
    enc = {v: {"chunks": ds[v].shape} for v in ds.data_vars if ds[v].ndim >= 3}
    ds.to_zarr(p, mode="w", zarr_format=2, encoding=enc, consolidated=True)
    return p


def read_site(site_id: str, root: Path | None = None) -> xr.Dataset:
    return xr.open_zarr(site_path(site_id, root), consolidated=True)


def write_scene_log(df: pd.DataFrame, site_id: str, root: Path | None = None) -> None:
    d = (root or CHIP_DIR) / "scene_logs"
    d.mkdir(parents=True, exist_ok=True)
    df.assign(site_id=site_id).to_parquet(d / f"{site_id}.parquet")


def _unused():  # keep json/np imports honest for linters
    return json, np


class PlatformMixError(ValueError):
    """Raised when chips of different platforms (Sentinel Hub, Planetary Computer, Earth Engine) would be combined."""


def source_of(ds: xr.Dataset) -> str:
    """Platform of a store; stores written before the attribute existed are Planetary Computer stores."""
    return str(ds.attrs.get("source", "planetary_computer"))


def assert_single_platform(datasets) -> str:
    sources = {source_of(d) for d in datasets}
    if len(sources) > 1:
        raise PlatformMixError(f"refusing to combine platforms in one series: {sorted(sources)}")
    return sources.pop()


def read_series(site_id: str, roots: list[Path]) -> xr.Dataset:
    """One site's series from one or several store roots (for example the Sentinel-1 and Sentinel-2 roots of
    one platform). Refuses to combine Sentinel Hub with Planetary Computer stores and variables that overlap."""
    parts = [read_site(site_id, r).load() for r in roots if site_path(site_id, r).exists()]
    if not parts:
        raise FileNotFoundError(site_id)
    assert_single_platform(parts)
    if len(parts) == 1:
        return parts[0]
    clash = set.intersection(*[set(p.data_vars) for p in parts])
    if clash:
        raise ValueError(f"variables present in several stores: {sorted(clash)}")
    merged = xr.merge(parts, combine_attrs="drop_conflicts", compat="no_conflicts")
    return merged
