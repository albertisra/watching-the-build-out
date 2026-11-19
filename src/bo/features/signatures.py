"""Signature analysis on public pilot sites and the minimum detectable size prediction (task 3.2).

Run: ``uv run python -m bo.features.signatures [--platform sh_pc|ee_r1|all]`` (``make signatures`` runs both).
Each platform writes its tables to its own directory (``PLATFORMS[...]["out"]``) and its figures to its own figure
directory. No new imagery is read: only existing chip stores, never mixed in one series.

Platforms and backscatter convention (review m1):
* ``sh_pc``: Sentinel Hub ``sh_v1`` / ``sh_v1_s1`` (Q sites) and Planetary Computer ``v0`` (P sites); Sentinel-1 is
  **gamma0, terrain flattened**. Tables in ``results/features/signatures_sh_pc_gamma0/``.
* ``ee_r1``: Google Earth Engine store of the round-1 queue (``data/chips/ee_r1``), the store Phase 4 features come
  from; Sentinel-1 is **sigma0, ellipsoid terrain correction, not flattened** (``bo.imagery.eechips``). Only the
  signature sites that are queue items have an ee_r1 chip. Tables in ``results/features/signatures_ee_r1_sigma0/``.
The tables directly under ``results/features/`` from 2026-11-18 are the original prediction (sh_pc stores as they
were before the A42 masking and the Sentinel-1 refetch); a copy is kept in ``signatures_2026-11-18_frozen/``.

What uses registry information, and why it is allowed: the MaStR commissioning month (observed) selects
the "before" and "after" months for measuring contrast. It never enters a feature (``bo.features.site`` reads
pixels only). Blindness (review M4): figures never draw registry dates, status or capacity, nor the technology or
outline size, for a site that matches a round-1 queue item (registry key, else within max(100 m, coordinate
uncertainty), ``bo.labelling.exposure.match_to_queue``); figures aligned on commissioning use non-queue sites only.
Registry-date comparisons for queue sites stay in the result tables. OSM outlines (ODbL) of the public sites are
used to measure contrast and the effective point spread function, again outside the feature code.

Quantities: chip values are observed measurements (monthly composites); contrasts, PSF widths, noise
quantiles and minimum sizes derived here are *modelled* (physical prediction), not detections.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio import features as rfeatures
from rasterio.transform import Affine
from scipy import ndimage
from shapely.ops import transform as shp_transform

from bo import paths
from bo.imagery import store

from . import spatial
from .indices import compute_index
from .osm_geom import public_outlines
from .site import s2_quality_mask, site_features
from .temporal import to_regular, yoy

OUT = paths.RESULTS / "features"
FIG = paths.FIGURES / "signatures"
ROOTS = {"Q": [paths.CHIPS / "sh_v1"], "P": [paths.CHIPS / "v0"]}
QUEUE_FILE = paths.PROCESSED / "labels" / "queue_round1.parquet"
SPLIT_FILE = paths.PROCESSED / "splits" / "blocks_v1.parquet"
PLATFORMS = {
    "sh_pc": {"name": "Sentinel Hub (Q sites, sh_v1) and Planetary Computer (P sites, v0)",
              "s1_convention": "gamma0",
              "s1_note": "gamma0 terrain flattened (Sentinel Hub: Copernicus 30 m DEM; Planetary Computer RTC)",
              "out": OUT / "signatures_sh_pc_gamma0", "fig": FIG},
    "ee_r1": {"name": "Google Earth Engine, round-1 queue store ee_r1 (COPERNICUS/S2_SR_HARMONIZED, COPERNICUS/S1_GRD)",
              "s1_convention": "sigma0",
              "s1_note": "sigma0 in dB, ellipsoid-based terrain correction, not terrain flattened (bo.imagery.eechips)",
              "out": OUT / "signatures_ee_r1_sigma0", "fig": FIG / "ee_r1"},
}
FINE = 10  # sub-pixels per 10 m pixel for rasterising outlines (1 m)
PSF_SIGMAS_M = (0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0)
SEASONS = {"summer": (4, 5, 6, 7, 8, 9), "winter": (10, 11, 12, 1, 2, 3)}
PRE_MONTHS = (-48, -24)  # months relative to registry commissioning (F6)
POST_MONTHS = (0, 24)
S2_VARS = ("ndvi", "vnir", "b08", "b11", "ndpi", "r1108")
S1_VARS = ("vv", "vh", "vvvh")
BAND_RES = {"b11": 20.0, "ndpi": 20.0, "r1108": 20.0}  # native resolution of the coarsest band used
WINDOW_RADII_M = (8.0, 15.0, 23.0, 30.0, 40.0, 60.0, 80.0, 120.0)
FEATURE_RADIUS_M = 40.0  # = spatial.CENTRE_RADIUS_M (F1)
CREDIT = "Contains modified Copernicus Sentinel data 2015-2026; outlines (c) OpenStreetMap contributors"


# ------------------------------------------------------------------ inputs

def public_sites() -> pd.DataFrame:
    p1 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    p0 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v0.parquet")
    dates = pd.concat([
        p1[["pilot_id", "reg_commissioning_date"]],
        p0[["pilot_id", "commissioned"]].rename(columns={"commissioned": "reg_commissioning_date"})])
    out = public_outlines().merge(dates, on="pilot_id", how="left")
    basis = pd.read_csv(paths.FIGURES / "sanity" / "public_basis.csv")[["pilot_id", "osm_power"]]
    return out.merge(basis, on="pilot_id")


def load(site_id: str):
    return store.read_series(site_id, ROOTS[site_id[0]])


def pilot_coordinates() -> pd.DataFrame:
    p1 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    p0 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v0.parquet")
    cols = ["pilot_id", "site_key", "lat", "lon"]
    return pd.concat([p1[cols], p0[cols]]).drop_duplicates("pilot_id").reset_index(drop=True)


def queue_matches(pilot_ids) -> pd.DataFrame:
    """Signature site to round-1 queue item: registry key first, else nearest item within max(100 m, coordinate
    uncertainty of either item). Same rule as ``bo.labelling.exposure`` (read only, not modified)."""
    from bo.labelling.exposure import coordinate_uncertainty, match_to_queue

    pilot = pilot_coordinates()
    pilot = pilot[pilot.pilot_id.isin(set(pilot_ids))]
    q = pd.read_parquet(QUEUE_FILE)
    return match_to_queue(pilot, q, unc_m=coordinate_uncertainty(pilot, q))


def registry_overlay_allowed(pilot_id: str, hidden: set[str]) -> bool:
    """Registry fields (dates, status, capacity, technology) may be drawn only for sites outside the queue."""
    return pilot_id not in hidden


class Loader:
    """Chip access for one platform. ``sh_pc`` reads the pilot stores by pilot id; ``ee_r1`` reads the queue store by
    the matched queue id (sites without a queue match have no ee_r1 chip and are skipped)."""

    def __init__(self, platform: str, matches: pd.DataFrame):
        self.platform = platform
        self.qid = dict(zip(matches.pilot_id, matches.queue_id))

    def has(self, pilot_id: str) -> bool:
        if self.platform == "sh_pc":
            return True
        q = self.qid.get(pilot_id)
        return q is not None and store.site_path(q, paths.CHIPS / "ee_r1").exists()

    def __call__(self, pilot_id: str):
        if self.platform == "sh_pc":
            return load(pilot_id)
        return store.read_series(self.qid[pilot_id], [paths.CHIPS / "ee_r1"])

    def store_id(self, pilot_id: str) -> str:
        return pilot_id if self.platform == "sh_pc" else self.qid[pilot_id]

    def s1_negatives(self) -> list[tuple[str, object]]:
        """Target-free Sentinel-1 chips: sh_pc the random negatives of ``sh_v1_s1`` (pilot v1); ee_r1 the
        queue's ``random_negative`` items (no registered unit within 2 km, ``bo.data.queue.NEG_MIN_DIST_M``)
        outside the locked test fold 0."""
        if self.platform == "sh_pc":
            neg = pd.read_parquet(paths.PROCESSED / "pilot" / "negatives_v1.parquet")
            root = paths.CHIPS / "sh_v1_s1"
            ids = neg.loc[neg.kind == "random", "neg_id"]
        else:
            q = pd.read_parquet(QUEUE_FILE)
            sp = pd.read_parquet(SPLIT_FILE)[["queue_id", "fold"]]
            q = q.merge(sp, on="queue_id", how="left")
            root = paths.CHIPS / "ee_r1"
            ids = q.loc[(q.stratum == "random_negative") & (q.fold != 0), "queue_id"]
        return [(i, root) for i in ids if store.site_path(i, root).exists()]


def chip_affine(ds) -> tuple[Affine, int]:
    a, b, c, d, e, f = ds.attrs["transform"]
    return Affine(a, b, c, d, e, f), int(ds.sizes["y"])


def fine_mask(ds, geom_wgs84) -> np.ndarray:
    """Outline rasterised on a 1 m grid aligned with the chip (n*FINE x n*FINE, float 0/1)."""
    aff, n = chip_affine(ds)
    tr = Transformer.from_crs(4326, int(ds.attrs["crs_epsg"]), always_xy=True)
    g = shp_transform(tr.transform, geom_wgs84)
    fa = aff * Affine.scale(1.0 / FINE)
    return rfeatures.rasterize([(g, 1)], out_shape=(n * FINE, n * FINE), transform=fa,
                               fill=0, dtype="uint8").astype(float)


def block(x: np.ndarray, k: int) -> np.ndarray:
    h, w = x.shape
    return x.reshape(h // k, k, w // k, k).mean(axis=(1, 3))


def fill_fraction(fine: np.ndarray, sigma_m: float, res_m: float = 10.0) -> np.ndarray:
    """Fraction of each 10 m pixel's response that comes from the target, for a Gaussian PSF of sigma_m
    (metres) and, for 20 m bands, a 20 m pixel footprint replicated to 10 m."""
    f = ndimage.gaussian_filter(fine, sigma_m, mode="constant") if sigma_m > 0 else fine
    f10 = block(f, FINE)
    if res_m > 10:
        f10 = ndimage.uniform_filter(f10, size=int(res_m // 10), mode="nearest")
    return f10


def per_pixel_cubes(ds) -> dict[str, np.ndarray]:
    cubes = {}
    if "s2_refl" in ds:
        bands = [str(b) for b in ds.band.values]
        refl = ds.s2_refl.values.astype("float64")
        bad = s2_quality_mask(ds)
        for v in S2_VARS:
            c = compute_index(v, refl, bands)
            c[bad] = np.nan
            if np.isfinite(c).any():
                cubes[v] = c
    if "s1_vv_db" in ds:
        vv = ds.s1_vv_db.values.astype("float64")
        cubes["vv"] = vv
        if "s1_vh_db" in ds and np.isfinite(ds.s1_vh_db.values).any():
            vh = ds.s1_vh_db.values.astype("float64")
            cubes["vh"] = vh
            cubes["vvvh"] = vv - vh
    return cubes


def month_offsets(months, ref) -> np.ndarray:
    m = pd.DatetimeIndex(months).to_period("M")
    r = pd.Timestamp(ref).to_period("M")
    return np.array([(x - r).n for x in m])


# ------------------------------------------------------------------ contrast and PSF

def pre_post_delta(cube: np.ndarray, months, ref, season: tuple[int, ...]) -> tuple[np.ndarray, int]:
    """Per-pixel (post minus pre), matched by calendar month inside ``season``; mean over months that
    have both. Returns (H, W) map and the number of calendar months used."""
    off = month_offsets(months, ref)
    cal = pd.DatetimeIndex(months).month.values
    pre = (off >= PRE_MONTHS[0]) & (off <= PRE_MONTHS[1])
    post = (off >= POST_MONTHS[0]) & (off <= POST_MONTHS[1])
    diffs = []
    for m in season:
        a, b = pre & (cal == m), post & (cal == m)
        if not a.any() or not b.any():
            continue
        with np.errstate(all="ignore"):
            d = np.nanmedian(cube[b], axis=0) - np.nanmedian(cube[a], axis=0)
        if np.isfinite(d).mean() > 0.5:
            diffs.append(d)
    if not diffs:
        return np.full(cube.shape[1:], np.nan), 0
    with np.errstate(all="ignore"):
        return np.nanmean(np.stack(diffs), axis=0), len(diffs)


def fit_contrast(delta: np.ndarray, fill: np.ndarray) -> dict:
    ok = np.isfinite(delta)
    x, y = fill[ok], delta[ok]
    if ok.sum() < 50 or x.max() < 0.3:
        return {"b": np.nan, "a": np.nan, "r2": np.nan, "b_se": np.nan, "n_px": int(ok.sum())}
    X = np.c_[np.ones_like(x), x]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    s2 = res.var(ddof=2)
    cov = s2 * np.linalg.inv(X.T @ X)
    r2 = 1 - res.var() / y.var() if y.var() > 0 else np.nan
    return {"a": coef[0], "b": coef[1], "b_se": float(np.sqrt(cov[1, 1])), "r2": r2, "n_px": int(ok.sum())}


def contrast_table(sites: pd.DataFrame, loader=None) -> pd.DataFrame:
    loader = loader or load
    rows = []
    for s in sites.itertuples():
        if s.geometry is None or pd.isna(s.reg_commissioning_date):
            continue
        if hasattr(loader, "has") and not loader.has(s.pilot_id):
            continue
        ds = loader(s.pilot_id)
        fine = fine_mask(ds, s.geometry)
        months = ds.month.values
        cubes = per_pixel_cubes(ds)
        for var, cube in cubes.items():
            res_m = BAND_RES.get(var, 10.0)
            for season, mm in SEASONS.items():
                delta, n_m = pre_post_delta(cube, months, s.reg_commissioning_date, mm)
                if n_m == 0:
                    continue
                if var in S1_VARS:
                    # power mixes linearly inside a resolution cell, decibels do not
                    delta = 10.0 ** (delta / 10.0) - 1.0
                for sg in PSF_SIGMAS_M:
                    f = fill_fraction(fine, sg, res_m)
                    r = fit_contrast(delta, f)
                    rows.append({"pilot_id": s.pilot_id, "subtype": s.subtype, "osm_power": s.osm_power,
                                 "outline_m2": float(fine.sum()), "var": var, "season": season,
                                 "n_months": n_m, "psf_sigma_m": sg, **r})
    return pd.DataFrame(rows)


def best_psf(ct: pd.DataFrame) -> pd.DataFrame:
    """Effective PSF sigma per variable: maximise the mean R2 over sites with an outline of at least
    1,000 m2 (smaller outlines constrain the width poorly) and a plant outline (not a single generator)."""
    use = ct[(ct.outline_m2 >= 1000) & (ct.osm_power == "plant") & ct.r2.notna()]
    g = use.groupby(["var", "psf_sigma_m"]).r2.mean().reset_index()
    best = g.loc[g.groupby("var").r2.idxmax()].rename(columns={"r2": "mean_r2"})
    n = use.groupby("var").pilot_id.nunique().rename("n_sites")
    best = best.merge(n, on="var")
    best["fwhm_m"] = 2.0 * np.sqrt(2.0 * np.log(2.0)) * best.psf_sigma_m  # Gaussian full width at half maximum
    return best


# ------------------------------------------------------------------ noise

def window_masks(n: int, res: float = 10.0) -> dict[float, np.ndarray]:
    return {r: spatial.radius_map(n, res) <= r for r in WINDOW_RADII_M}


def noise_samples(cube: np.ndarray, months, keep: np.ndarray, radii, rng, n_pos: int = 40,
                  months_ok: np.ndarray | None = None) -> pd.DataFrame:
    """Year-over-year change of window means minus the chip-wide median (common mode) at random window
    positions whose pixels all lie in ``keep`` (no known target). ``d1`` is one month, ``d6`` the mean of
    the trailing six monthly values (at least three valid), i.e. a change that must persist.
    One row per (position, month, radius)."""
    _t, n, _ = cube.shape
    cube = cube.copy()
    if months_ok is not None:
        cube[~months_ok] = np.nan
    with np.errstate(all="ignore"):
        common = np.nanmedian(cube[:, keep], axis=1)
    cal = pd.DatetimeIndex(months).month.values
    rows = []
    for r in radii:
        half = int(np.ceil(r / 10.0))
        g = np.arange(-half - 1, half + 2)
        yy0, xx0 = np.meshgrid(g, g, indexing="ij")
        inside = np.hypot(yy0 * 10.0, xx0 * 10.0) <= r  # window centred on a pixel centre
        foot = np.c_[yy0[inside], xx0[inside]]
        lo, hi = half + 1, n - half - 2
        if hi <= lo:
            continue
        found = 0
        for _ in range(400):
            cy, cx = rng.integers(lo, hi, size=2)
            yy, xx = foot[:, 0] + cy, foot[:, 1] + cx
            if not keep[yy, xx].all():
                continue
            v = cube[:, yy, xx]
            ok = np.isfinite(v).mean(axis=1) >= 0.5
            with np.errstate(all="ignore"):
                w = np.where(ok, np.nanmean(v, axis=1), np.nan) - common
            x = pd.Series(w, index=pd.DatetimeIndex(months))
            d1 = yoy(x).values
            d6 = to_regular(pd.Series(d1, index=pd.DatetimeIndex(months))).rolling(6, min_periods=3).mean()
            d6 = d6.reindex(pd.DatetimeIndex(months).to_period("M").to_timestamp()).values
            for i in np.flatnonzero(np.isfinite(d1) | np.isfinite(d6)):
                rows.append((r, cal[i], d1[i], d6[i]))
            found += 1
            if found >= n_pos:
                break
    return pd.DataFrame(rows, columns=["radius_m", "cal_month", "d1", "d6"])


def noise_tables(sites: pd.DataFrame, rng, loader=None) -> pd.DataFrame:
    loader = loader or Loader("sh_pc", pd.DataFrame(columns=["pilot_id", "queue_id"]))
    parts = []
    # Sentinel-2: off-site pixels of the public signature chips
    for s in sites.itertuples():
        if s.geometry is None or not loader.has(s.pilot_id):
            continue
        ds = loader(s.pilot_id)
        fine = fine_mask(ds, s.geometry)
        inside = block(fine, FINE) > 0
        dist = ndimage.distance_transform_edt(~inside) * 10.0
        keep = dist > 100.0
        ok = ~s2_quality_mask(ds) if "s2_refl" in ds else None
        for var, cube in per_pixel_cubes(ds).items():
            sensor = "s1" if var in S1_VARS else "s2"
            if sensor == "s1":
                continue  # Sentinel-1 noise is taken from the random negatives below
            df = noise_samples(cube, ds.month.values, keep, WINDOW_RADII_M, rng, 15,
                               ok if sensor == "s2" else None)
            parts.append(df.assign(var=var, source="sanity_offsite", site=s.pilot_id))
    # Sentinel-1: random negatives of the same platform (whole chip, no registered unit within 2 km)
    for nid, root in loader.s1_negatives():
        ds = store.read_series(nid, [root])
        keep = np.ones((ds.sizes["y"], ds.sizes["x"]), bool)
        for var, cube in per_pixel_cubes(ds).items():
            df = noise_samples(cube, ds.month.values, keep, WINDOW_RADII_M, rng, 8)
            parts.append(df.assign(var=var, source="random_negative", site=nid))
    return pd.concat(parts, ignore_index=True)


def noise_quantiles(noise: pd.DataFrame) -> pd.DataFrame:
    cal2season = {m: k for k, v in SEASONS.items() for m in v}
    noise = noise.assign(season=noise.cal_month.map(cal2season))
    rows = []
    for (var, season, r), g in noise.groupby(["var", "season", "radius_m"]):
        for k in ("d1", "d6"):
            d = g[k].dropna().values
            if len(d) < 200:
                continue
            mad = 1.4826 * np.median(np.abs(d - np.median(d)))
            rows.append({"var": var, "season": season, "radius_m": r, "persistence": k, "n": len(d),
                         "n_sites": g[g[k].notna()].site.nunique(), "sd": d.std(), "robust_sd": mad,
                         "q01": np.quantile(d, 0.01), "q05": np.quantile(d, 0.05),
                         "q95": np.quantile(d, 0.95), "q99": np.quantile(d, 0.99)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ minimum detectable size

AREAS_M2 = np.unique(np.round(np.geomspace(50, 160_000, 60)))
_FILL_CACHE: dict = {}


def fill_table(sigma_m: float, res_m: float, n: int = 64, phases: int = 4) -> pd.DataFrame:
    """Mean fill fraction inside centred windows (rows: AREAS_M2, columns: WINDOW_RADII_M) for a square
    target, averaged over sub-pixel phases (target offset 0, 2.5, 5, 7.5 m)."""
    key = (sigma_m, res_m, n, phases)
    if key in _FILL_CACHE:
        return _FILL_CACHE[key]
    rad = spatial.radius_map(n, 10.0)
    tab = np.zeros((len(AREAS_M2), len(WINDOW_RADII_M)))
    for i, a in enumerate(AREAS_M2):
        side = np.sqrt(a)
        acc = np.zeros(len(WINDOW_RADII_M))
        for k in range(phases):
            c = n * FINE / 2 + k * (10.0 / phases)
            lo, hi = max(round(c - side / 2), 0), min(round(c + side / 2), n * FINE)
            fine = np.zeros((n * FINE, n * FINE))
            fine[lo:hi, lo:hi] = 1.0
            f = fill_fraction(fine, sigma_m, res_m)
            acc += [f[rad <= r].mean() for r in WINDOW_RADII_M]
        tab[i] = acc / phases
    out = pd.DataFrame(tab, index=AREAS_M2, columns=WINDOW_RADII_M)
    _FILL_CACHE[key] = out
    return out


def window_signal(var: str, contrast: float, fill: np.ndarray) -> np.ndarray:
    """Expected change of the window statistic for a target of pure ``contrast`` filling ``fill`` of the
    window. Reflectance and indices: linear mixing (an approximation for ratio indices). SAR: contrast is
    the pure power ratio minus one; the window change in dB is 10 log10(1 + fill * contrast)."""
    if var in S1_VARS:
        return 10.0 * np.log10(np.maximum(1.0 + fill * contrast, 1e-6))
    return contrast * fill


def min_detectable(var: str, contrast: float, sigma_m: float, res_m: float, q: pd.DataFrame) -> dict:
    """Smallest square area whose expected window change passes the one-sided 99 % (and 95 %) quantile
    of the no-target noise in the direction of the contrast, with the best window radius."""
    tab = fill_table(sigma_m, res_m)
    out = {}
    for level, (lo, hi) in {"q99": ("q01", "q99"), "q95": ("q05", "q95")}.items():
        best, best_r = np.inf, np.nan
        for r in WINDOW_RADII_M:
            row = q[q.radius_m == r]
            if row.empty:
                continue
            row = row.iloc[0]
            sig = window_signal(var, contrast, tab[r].values)
            hit = sig > row[hi] if contrast > 0 else sig < row[lo]
            if hit.any():
                a = tab.index.values[np.argmax(hit)]
                if a < best:
                    best, best_r = a, r
        out[f"amin_{level}_m2"] = best if np.isfinite(best) else np.nan
        out[f"radius_{level}_m"] = best_r
        # the same with the fixed feature window (F1), which is what the allow-list columns use
        row = q[q.radius_m == FEATURE_RADIUS_M]
        a_fix = np.nan
        if not row.empty:
            sig = window_signal(var, contrast, tab[FEATURE_RADIUS_M].values)
            thr = row.iloc[0][hi] if contrast > 0 else row.iloc[0][lo]
            hit = sig > thr if contrast > 0 else sig < thr
            a_fix = tab.index.values[np.argmax(hit)] if hit.any() else np.nan
        out[f"amin_{level}_r40_m2"] = a_fix
    # 80 % detection probability at the 99 % threshold (definition of the minimum detectable size in
    # docs/analysis_plan.md 7.1): the expected change must exceed the threshold by the 20 % quantile of the
    # noise, approximated as 0.8416 robust SD (noise median near 0, see noise_yoy_window.csv).
    z80 = 0.8416
    for tag, radii in (("p80", WINDOW_RADII_M), ("p80_r40", (FEATURE_RADIUS_M,))):
        best = np.inf
        for r in radii:
            row = q[q.radius_m == r]
            if row.empty:
                continue
            row = row.iloc[0]
            sig = window_signal(var, contrast, tab[r].values)
            hit = (sig > row["q99"] + z80 * row["robust_sd"]) if contrast > 0 else \
                (sig < row["q01"] - z80 * row["robust_sd"])
            if hit.any():
                best = min(best, tab.index.values[np.argmax(hit)])
        out[f"amin_q99_{tag}_m2"] = best if np.isfinite(best) else np.nan
    return out


# Footprint ratios quoted from docs/research/site_footprints.md: BESS 94 to 150 m2 per MW (core of the
# eight German sites, section B), solar 0.88 ha per MWp (ZSW 2024, fact 14) with range 0.7 to 1.2 ha.
BESS_M2_PER_MW = (94.0, 150.0)
PV_M2_PER_MWP = (7_000.0, 8_800.0, 12_000.0)


def to_capacity(df: pd.DataFrame) -> pd.DataFrame:
    """Add capacity equivalents of the minimum areas (modelled; footprint ratios above)."""
    df = df.copy()
    for c in [c for c in df.columns if c.startswith("amin_")]:
        bess = df.subtype == "battery"
        df.loc[bess, c.replace("_m2", "_mw_lo")] = df.loc[bess, c] / BESS_M2_PER_MW[1]
        df.loc[bess, c.replace("_m2", "_mw_hi")] = df.loc[bess, c] / BESS_M2_PER_MW[0]
        pv = df.subtype == "ground-mounted"
        df.loc[pv, c.replace("_m2", "_mw_lo")] = df.loc[pv, c] / PV_M2_PER_MWP[2]
        df.loc[pv, c.replace("_m2", "_mw_hi")] = df.loc[pv, c] / PV_M2_PER_MWP[0]
    return df


def speckle_check(noise_q: pd.DataFrame, loader=None) -> pd.DataFrame:
    """Compare the measured single-pixel year-over-year spread of VV with the spread expected from speckle
    alone: intensity ~ Gamma(ENL) gives var(10 log10 I) = (10 / ln 10)^2 * trigamma(ENL). ENL 4.4 from
    docs/research/sentinel1.md fact 15; the monthly median of n scenes scales the spread by about
    1.2533 / sqrt(n) (large-sample efficiency of the median); a difference of two months adds sqrt(2)."""
    from scipy.special import polygamma

    loader = loader or Loader("sh_pc", pd.DataFrame(columns=["pilot_id", "queue_id"]))
    ns = []
    for nid, root in loader.s1_negatives():
        v = store.read_site(nid, root).s1_n_scenes.values
        ns.extend(v[v > 0].tolist())
    n_med = float(np.median(ns))
    sd_scene = 10.0 / np.log(10.0) * np.sqrt(float(polygamma(1, 4.4)))
    pred = sd_scene * 1.2533 / np.sqrt(n_med) * np.sqrt(2.0)
    rows = []
    for var in ("vv", "vh"):
        m = noise_q[(noise_q["var"] == var) & (noise_q.radius_m == WINDOW_RADII_M[0])
                    & (noise_q.persistence == "d1")]
        for r in m.itertuples():
            rows.append({"var": var, "season": r.season, "window_radius_m": r.radius_m,
                         "measured_robust_sd_db": r.robust_sd, "speckle_only_sd_db": pred,
                         "sd_single_scene_db": sd_scene, "median_scenes_per_month": n_med})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ figures

def series_figure(s, ds, fine, platform: str = "sh_pc", hidden: set[str] | None = None) -> None:
    hidden = set() if hidden is None else hidden
    allowed = registry_overlay_allowed(s.pilot_id, hidden)
    conv = PLATFORMS[platform]["s1_convention"]
    feats = site_features(ds, site_id=s.pilot_id)
    m = pd.DatetimeIndex(feats.month)
    inside = block(fine, FINE) >= 0.5
    cubes = per_pixel_cubes(ds)
    panels = [("ndvi", "s2_ndvi_c", "NDVI (experimental formula)"),
              ("vnir", "s2_vnir_c", "mean VNIR reflectance"),
              ("b11", "s2_b11_c", "B11 reflectance (20 m)"),
              ("ndpi", "s2_ndpi_c", "NDPI (Feng et al. 2024)"),
              ("vv", "s1_vv_c", f"S1 VV {conv} (dB)"),
              ("vh", "s1_vh_c", f"S1 VH {conv} (dB)"),
              ("vvvh", "s1_vvvh_c", "S1 VV minus VH (dB)")]
    panels = [p for p in panels if feats[p[1]].notna().any()]
    fig, axes = plt.subplots(len(panels), 1, figsize=(9, 1.45 * len(panels)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, (var, col, title) in zip(axes, panels):
        ax.plot(m, feats[col], ".-", lw=0.7, ms=2.5, color="0.2", label="centre disk 40 m (feature)")
        ring = feats[col] - feats[col[:-2] + "_ctr"]  # ring median = centre minus contrast
        ax.plot(m, ring, lw=0.6, color="tab:green", label="ring 150-300 m")
        if var in cubes and inside.sum() >= 2:
            v = cubes[var][:, inside]
            ok = np.isfinite(v).mean(axis=1) >= 0.5
            with np.errstate(all="ignore"):
                ser = np.where(ok, np.nanmedian(v, axis=1), np.nan)
            ax.plot(m, ser, lw=0.8, color="tab:orange", label="inside OSM outline")
        if allowed and pd.notna(s.reg_commissioning_date):
            ax.axvline(pd.Timestamp(s.reg_commissioning_date), color="tab:red", lw=0.8, ls="--")
        ax.set_ylabel(title, fontsize=6)
        ax.tick_params(labelsize=6)
        if var == "ndpi":
            ax.set_ylim(-3, 3)
    axes[0].legend(fontsize=5, ncol=3, loc="upper left")
    if platform == "ee_r1":
        src = "Earth Engine (S1 sigma0)"
    else:
        src = ("Sentinel Hub" if s.pilot_id.startswith("Q") else "Planetary Computer") + " (S1 gamma0)"
    if allowed:
        title = (f"{s.pilot_id} ({s.subtype}, outline {fine.sum():,.0f} m2), {src} chips. "
                 "Red dashed: MaStR commissioning month (observed)")
    else:
        title = f"{s.pilot_id}, {src} chips. Registry fields not drawn (site is in the labelling queue)"
    axes[0].set_title(title, fontsize=7)
    axes[-1].text(0, -0.45, CREDIT, transform=axes[-1].transAxes, fontsize=5)
    fig.tight_layout()
    fdir = PLATFORMS[platform]["fig"]
    fdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fdir / f"{s.pilot_id}_series.png", dpi=130)
    plt.close(fig)


def aligned_figure(sites: pd.DataFrame, platform: str = "sh_pc", hidden: set[str] | None = None,
                   loader=None) -> bool:
    """Year-over-year change of centre features against months since commissioning, both technologies, for sites
    outside the labelling queue only (M4). Returns False (no figure written) if no such site has a chip."""
    hidden = set() if hidden is None else hidden
    loader = loader or load
    sites = sites[[registry_overlay_allowed(p, hidden) for p in sites.pilot_id]]
    if hasattr(loader, "has"):
        sites = sites[[loader.has(p) for p in sites.pilot_id]]
    out = PLATFORMS[platform]["fig"] / "aligned_yoy.png"
    if sites.empty:
        out.unlink(missing_ok=True)
        return False
    cols = [("s2_ndvi_c_yoy", "NDVI yoy (experimental)"), ("s2_vnir_c_yoy", "VNIR yoy"),
            ("s1_vv_c_yoy", "VV yoy (dB)"), ("s1_vh_c_yoy", "VH yoy (dB)")]
    fig, axes = plt.subplots(len(cols), 2, figsize=(10, 7), sharex=True)
    for j, tech in enumerate(["battery", "ground-mounted"]):
        for s in sites[sites.subtype == tech].itertuples():
            if pd.isna(s.reg_commissioning_date):
                continue
            f = site_features(loader(s.pilot_id), site_id=s.pilot_id)
            off = month_offsets(f.month, s.reg_commissioning_date)
            for i, (c, t) in enumerate(cols):
                axes[i, j].plot(off, f[c], lw=0.6, alpha=0.8, label=s.pilot_id)
                axes[i, j].set_ylabel(t, fontsize=7)
        axes[0, j].set_title(f"{tech}: months since MaStR commissioning (observed); non-queue sites only",
                             fontsize=8)
        for i in range(len(cols)):
            axes[i, j].axvline(0, color="k", lw=0.6)
            axes[i, j].axhline(0, color="0.6", lw=0.5)
            axes[i, j].set_xlim(-60, 36)
            axes[i, j].tick_params(labelsize=6)
        axes[0, j].legend(fontsize=5, ncol=4)
    fig.text(0.01, 0.005, CREDIT, fontsize=5)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return True


# ------------------------------------------------------------------ main

def tag(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Every result table states its platform and Sentinel-1 backscatter convention (review m1)."""
    return df.assign(platform=platform, s1_convention=PLATFORMS[platform]["s1_convention"])


def run(platform: str, sites: pd.DataFrame, matches: pd.DataFrame) -> None:
    cfg = PLATFORMS[platform]
    out = cfg["out"]
    out.mkdir(parents=True, exist_ok=True)
    cfg["fig"].mkdir(parents=True, exist_ok=True)
    hidden = set(matches.pilot_id)
    loader = Loader(platform, matches)
    rng = np.random.default_rng(paths.SEED)
    used = [s for s in sites.itertuples() if s.geometry is not None and loader.has(s.pilot_id)]
    for s in used:
        ds = loader(s.pilot_id)
        series_figure(s, ds, fine_mask(ds, s.geometry), platform, hidden)
    aligned = aligned_figure(sites, platform, hidden, loader)

    ct = contrast_table(sites, loader)
    ct.insert(1, "store_id", ct.pilot_id.map(loader.store_id))
    tag(ct, platform).to_csv(out / "contrast_fit_all.csv", index=False)
    psf = best_psf(ct)
    tag(psf, platform).to_csv(out / "psf_effective.csv", index=False)
    sel = ct.merge(psf[["var", "psf_sigma_m"]], on=["var", "psf_sigma_m"])
    tag(sel, platform).to_csv(out / "contrast_at_best_psf.csv", index=False)
    summ = (sel[(sel.osm_power == "plant") & (sel.outline_m2 >= 1000)].groupby(["subtype", "var", "season"])
            .agg(n_sites=("pilot_id", "nunique"), b_median=("b", "median"), b_min=("b", "min"),
                 b_max=("b", "max"), r2_median=("r2", "median")).reset_index())
    tag(summ, platform).to_csv(out / "contrast_summary.csv", index=False)

    noise = noise_tables(sites, rng, loader)
    q = noise_quantiles(noise)
    q = q.merge(noise.groupby("var").site.nunique().rename("n_chips_var").reset_index(), on="var", how="left")
    tag(q, platform).to_csv(out / "noise_yoy_window.csv", index=False)
    tag(speckle_check(q, loader), platform).to_csv(out / "s1_speckle_check.csv", index=False)
    tag(minsize(out), platform).to_csv(out / "min_detectable_size.csv", index=False)
    tag(stability_table(sites, loader), platform).to_csv(out / "stability_before_after.csv", index=False)
    tag(orbit_table(used, loader), platform).to_csv(out / "s1_orbits.csv", index=False)
    meta = {"platform": platform, "platform_name": cfg["name"], "s1_convention": cfg["s1_convention"],
            "s1_note": cfg["s1_note"], "sites": [loader.store_id(s.pilot_id) + "=" + s.pilot_id for s in used],
            "n_s1_noise_chips": len(loader.s1_negatives()),
            "aligned_figure_written": aligned, "figures_dir": str(cfg["fig"].relative_to(paths.REPO_ROOT)),
            "registry_overlay_hidden_for": sorted(hidden),
            "pre_months": PRE_MONTHS, "post_months": POST_MONTHS, "seasons": SEASONS,
            "psf_grid_m": PSF_SIGMAS_M, "window_radii_m": WINDOW_RADII_M, "seed": paths.SEED,
            "quantity_type": "modelled", "credit": CREDIT}
    (out / "signatures_meta.json").write_text(json.dumps(meta, indent=1, default=str))


def orbit_table(used, loader) -> pd.DataFrame:
    rows = []
    for s in used:
        a = loader(s.pilot_id).attrs
        rows.append({"pilot_id": s.pilot_id, "store_id": loader.store_id(s.pilot_id),
                     "s1_relative_orbit": a.get("s1_relative_orbit"), "s1_pass_direction": a.get("s1_pass_direction"),
                     "source": a.get("source")})
    return pd.DataFrame(rows)


def fold0_table(sites: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Signature sites and their queue item and fold (review m8), so fold-0 metrics can be reported with and
    without them. Sites without a queue match are listed with an empty queue_id."""
    sp = pd.read_parquet(SPLIT_FILE)[["queue_id", "fold", "role", "block_id"]]
    df = sites[["pilot_id"]].merge(matches, on="pilot_id", how="left").merge(sp, on="queue_id", how="left")
    df["in_fold0"] = df.fold.eq(0)
    df["used_in"] = "signature contrast, PSF fit, S2 noise; relevance list (signatures.md section 2)"
    return df.rename(columns={"how": "match_rule"})


def compare_platforms() -> pd.DataFrame:
    """Contrast and minimum size, sh_pc (gamma0) against ee_r1 (sigma0), on the sites both platforms measured
    (paired by pilot id) and on all sites of each platform. Modelled quantities."""
    a, b = (pd.read_csv(PLATFORMS[k]["out"] / "contrast_at_best_psf.csv") for k in ("sh_pc", "ee_r1"))
    keep = ["pilot_id", "subtype", "var", "season", "b", "r2"]
    ok = lambda d: d[(d.osm_power == "plant") & (d.outline_m2 >= 1000)][keep]
    pair = ok(a).merge(ok(b), on=["pilot_id", "subtype", "var", "season"], suffixes=("_sh_pc", "_ee_r1"))
    pair = pair.dropna(subset=["b_sh_pc", "b_ee_r1"])
    g = pair.groupby(["subtype", "var", "season"])
    rows = g.agg(n_paired=("pilot_id", "nunique"), b_median_sh_pc_paired=("b_sh_pc", "median"),
                 b_median_ee_r1_paired=("b_ee_r1", "median")).reset_index()
    rows["median_paired_diff_ee_minus_sh"] = g.apply(lambda x: (x.b_ee_r1 - x.b_sh_pc).median(),
                                                     include_groups=False).values
    sa, sb = (pd.read_csv(PLATFORMS[k]["out"] / "contrast_summary.csv") for k in ("sh_pc", "ee_r1"))
    f = pd.read_csv(OUT / "signatures_2026-11-18_frozen" / "contrast_summary.csv")
    cols = ["subtype", "var", "season", "n_sites", "b_median"]
    rows = (rows.merge(f[cols].rename(columns={"n_sites": "n_frozen", "b_median": "b_median_frozen"}),
                       on=["subtype", "var", "season"], how="outer")
            .merge(sa[cols].rename(columns={"n_sites": "n_sh_pc", "b_median": "b_median_sh_pc"}),
                   on=["subtype", "var", "season"], how="outer")
            .merge(sb[cols].rename(columns={"n_sites": "n_ee_r1", "b_median": "b_median_ee_r1"}),
                   on=["subtype", "var", "season"], how="outer"))
    return rows


def compare_psf_paired() -> pd.DataFrame:
    """Best PSF width per variable on the sites both platforms fit (same rule as ``best_psf``)."""
    d = {k: pd.read_csv(PLATFORMS[k]["out"] / "contrast_fit_all.csv") for k in ("sh_pc", "ee_r1")}
    d = {k: v[(v.outline_m2 >= 1000) & (v.osm_power == "plant") & v.r2.notna()] for k, v in d.items()}
    rows = []
    for var in sorted(set(d["sh_pc"]["var"]) & set(d["ee_r1"]["var"])):
        common = set(d["sh_pc"].loc[d["sh_pc"]["var"] == var, "pilot_id"]) & set(
            d["ee_r1"].loc[d["ee_r1"]["var"] == var, "pilot_id"])
        row = {"var": var, "n_paired_sites": len(common)}
        for k, v in d.items():
            g = v[(v["var"] == var) & v.pilot_id.isin(common)].groupby("psf_sigma_m").r2.mean()
            row[f"psf_sigma_m_{k}"] = g.idxmax() if len(g) else np.nan
            row[f"mean_r2_{k}"] = g.max() if len(g) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def compare_minsize() -> pd.DataFrame:
    key = ["subtype", "var", "season", "persistence", "contrast_case"]
    val = ["contrast", "amin_q99_p80_r40_m2", "amin_q99_p80_m2", "amin_q99_r40_m2", "amin_q99_m2"]
    f = pd.read_csv(OUT / "signatures_2026-11-18_frozen" / "min_detectable_size.csv")[key + val]
    a = pd.read_csv(PLATFORMS["sh_pc"]["out"] / "min_detectable_size.csv")[key + val]
    b = pd.read_csv(PLATFORMS["ee_r1"]["out"] / "min_detectable_size.csv")[key + val]
    m = (f.rename(columns={v: v + "_frozen" for v in val})
         .merge(a.rename(columns={v: v + "_sh_pc" for v in val}), on=key, how="outer")
         .merge(b.rename(columns={v: v + "_ee_r1" for v in val}), on=key, how="outer"))
    m["ratio_central_ee_over_frozen"] = m.amin_q99_p80_r40_m2_ee_r1 / m.amin_q99_p80_r40_m2_frozen
    m["ratio_central_ee_over_sh_pc"] = m.amin_q99_p80_r40_m2_ee_r1 / m.amin_q99_p80_r40_m2_sh_pc
    return m.sort_values(key)


def main(platforms=("sh_pc", "ee_r1")) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sites = public_sites()
    matches = queue_matches(sites.pilot_id)
    fold0_table(sites, matches).to_csv(OUT / "signature_sites_fold0.csv", index=False)
    for p in platforms:
        run(p, sites, matches)
    if all((PLATFORMS[k]["out"] / "contrast_at_best_psf.csv").exists() for k in PLATFORMS):
        compare_platforms().to_csv(OUT / "signatures_platform_comparison.csv", index=False)
        compare_minsize().to_csv(OUT / "signatures_platform_minsize_comparison.csv", index=False)
        compare_psf_paired().to_csv(OUT / "signatures_platform_psf_paired.csv", index=False)
    # platform-independent registry tables (observed), as before
    reg, chips = colocation_tables()
    reg.to_csv(OUT / "colocation_registry.csv", index=False)
    chips.to_csv(OUT / "colocation_pilot_chips.csv", index=False)


def stability_table(sites: pd.DataFrame, loader=None) -> pd.DataFrame:
    """Median trailing-12-month spread of centre features in a fully 'before' window (36 to 24 months before
    commissioning) and a fully 'after' window (12 to 36 months after). Public sites only."""
    loader = loader or load
    rows = []
    for s in sites.itertuples():
        if pd.isna(s.reg_commissioning_date):
            continue
        if hasattr(loader, "has") and not loader.has(s.pilot_id):
            continue
        f = site_features(loader(s.pilot_id), site_id=s.pilot_id)
        off = month_offsets(f.month, s.reg_commissioning_date)
        for period, (lo, hi) in (("before", (-36, -24)), ("after", (12, 36))):
            g = f[(off >= lo) & (off <= hi)]
            rows.append({"pilot_id": s.pilot_id, "subtype": s.subtype, "period": period, "n_months": len(g),
                         "s2_ndvi_c_sd12": g.s2_ndvi_c_sd12.median(), "s2_vnir_c_sd12": g.s2_vnir_c_sd12.median(),
                         "s1_vv_c_cv12": g.s1_vv_c_cv12.median(), "s1_vh_c_cv12": g.s1_vh_c_cv12.median()})
    return pd.DataFrame(rows)


def colocation_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Share of registry battery sites with a ground-mounted PV site within 300 m (observed, from
    results/registry/registry_colocation_breakdown.csv), and pilot battery chips whose chip contains a
    registered PV site (chip attribute ``other_registered_sites_in_chip``)."""
    b = pd.read_csv(paths.RESULTS / "registry" / "registry_colocation_breakdown.csv")
    near = ["0 m (same point)", ">0 to 10 m", ">10 to 50 m", ">50 to 100 m", ">100 to 300 m"]
    out = []
    for tech, g in b.groupby("technology"):
        out.append({"technology": tech, "sites": int(g.sites.sum()),
                    "sites_within_300m": int(g[g.distance_band.isin(near)].sites.sum())})
    reg = pd.DataFrame(out)
    reg["share_within_300m"] = reg.sites_within_300m / reg.sites
    p1 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    rows = []
    for r in p1.itertuples():
        for root in (paths.CHIPS / "sh_v1", paths.CHIPS / "sh_v1_s1"):
            if store.site_path(r.pilot_id, root).exists():
                other = json.loads(store.read_site(r.pilot_id, root).attrs.get("other_registered_sites_in_chip", "{}"))
                rows.append({"subtype": r.subtype, "pv_in_chip": other.get("ground_pv", 0) > 0,
                             "battery_in_chip": other.get("battery", 0) > 0})
                break
    chips = pd.DataFrame(rows).groupby("subtype").agg(
        n=("pv_in_chip", "size"), with_pv_in_chip=("pv_in_chip", "sum"),
        with_battery_in_chip=("battery_in_chip", "sum")).reset_index()
    return reg, chips


def minsize(out_dir=None) -> pd.DataFrame:
    """Minimum detectable size from the saved contrast, PSF and noise tables of ``out_dir``."""
    out_dir = out_dir or OUT
    psf = pd.read_csv(out_dir / "psf_effective.csv")
    summ = pd.read_csv(out_dir / "contrast_summary.csv")
    q = pd.read_csv(out_dir / "noise_yoy_window.csv")
    rows = []
    psf_map = dict(zip(psf["var"], psf.psf_sigma_m))
    for r in summ.itertuples():
        if not np.isfinite(r.b_median) or r.var not in psf_map:
            continue
        weakest = r.b_min if r.b_median > 0 else r.b_max  # smallest contrast in the median's direction
        for label, b in (("median", r.b_median), ("weakest", weakest)):
            if np.sign(b) != np.sign(r.b_median):
                continue  # one site shows the opposite sign: no size can be predicted for it
            for pers in ("d1", "d6"):
                qq = q[(q["var"] == r.var) & (q.season == r.season) & (q.persistence == pers)]
                if qq.empty:
                    continue
                res = min_detectable(r.var, b, psf_map[r.var], BAND_RES.get(r.var, 10.0), qq)
                rows.append({"subtype": r.subtype, "var": r.var, "season": r.season, "persistence": pers,
                             "contrast_case": label, "contrast": b,
                             "contrast_db": 10 * np.log10(1 + b) if r.var in S1_VARS and b > -1 else np.nan,
                             "n_sites": r.n_sites, "psf_sigma_m": psf_map[r.var],
                             "res_m": BAND_RES.get(r.var, 10.0), **res})
    return to_capacity(pd.DataFrame(rows))


if __name__ == "__main__":
    import sys

    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--platform=")), "all")
    if "--platform" in sys.argv:
        arg = sys.argv[sys.argv.index("--platform") + 1]
    main(tuple(PLATFORMS) if arg == "all" else (arg,))
