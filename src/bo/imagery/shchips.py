"""Chip stores built server-side on CDSE Sentinel Hub (same Zarr layout as the Planetary Computer stores).

Per site and calendar year one Process API request per sensor returns twelve monthly composites:
Sentinel-2 L2A median reflectance of clear pixels (SCL 4, 5, 6) plus three per-pixel counts, and
Sentinel-1 GRD gamma0 (terrain flattened, orthorectified, Copernicus 30 m DEM) VV/VH median in dB with a
single relative orbit enforced inside the evalscript. Harmonisation: Sentinel Hub is asked for
``harmonizeValues = true``, so reflectance is already on the pre-04.00 convention and no offset is applied
here; this equals the Planetary Computer rule (DN - 1000 for baseline >= 04.00, floor 0). Months without
a valid observation stay NaN with count 0.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from .composite import month_index
from .config import S2_BANDS, ChipConfig
from .geo import chip_grid
from .quota import GLOBAL, Stage
from .sentinelhub import post_process, s1_body, s2_body, split_s1_year, split_s2_year
from .store import build_dataset, write_site

_BASELINE = re.compile(r"_N(\d{2})(\d{2})_")


def item_baseline(path: str) -> str | None:
    m = _BASELINE.search(path)
    return f"{m.group(1)}.{m.group(2)}" if m else None


def _month_items(ud: dict, year: int) -> tuple[dict, dict, np.ndarray]:
    by_m: dict[str, list[str]] = {}
    bl: dict[str, str] = {}
    n = np.zeros(12, np.int16)
    for o in ud.get("orbits", []):
        m = int(o["date"][5:7])
        n[m - 1] += 1
        for t in o["tiles"]:
            name = t.rstrip("/").split("/")[-1] if "S2" in t else t.split("/")[-1]
            sid = re.search(r"(S2[ABC]_MSIL2A_[^/]*?\.SAFE)", t)
            sid = sid.group(1) if sid else name
            by_m.setdefault(f"{year}-{m:02d}", []).append(sid)
            b = item_baseline(t)
            if b:
                bl[sid] = b
    return by_m, bl, n


def _year_window(y: int, start: str, end: str) -> tuple[str, str]:
    """Time range of a yearly request, capped at the store axis (no data after ``end``)."""
    return max(f"{y}-01-01", start[:10]), min(f"{y}-12-31", end[:10])


def build_site_sh(site_id, lon, lat, years_s2, years_s1, orbit, start, end, cfg=None, root=None,
                  counters=GLOBAL, sensors=("s1", "s2"), log_stage: str | None = None,
                  own_site_key: str | None = None):
    """years_s2 / years_s1: years to request (the caller skips years without data).
    orbit: (relative_orbit, direction) chosen from Planetary Computer STAC metadata, or None."""
    cfg = cfg or ChipConfig()
    grid = chip_grid(lon, lat, cfg.size, cfg.res)
    months = month_index(start, end)
    T = len(months)
    H, W = grid.shape
    nb = len(S2_BANDS)
    refl = np.full((T, nb, H, W), np.nan, np.float32)
    cnt = np.zeros((T, H, W), np.uint16)
    cnt_alt = np.zeros((T, H, W), np.uint16)
    cnt_cld = np.zeros((T, H, W), np.uint16)
    npass = np.zeros(T, np.int16)
    items: dict = {}
    base: dict = {}
    idx = {m: i for i, m in enumerate(months)}

    def put_year(y, fn):
        for mo in range(12):
            m = np.datetime64(f"{y}-{mo + 1:02d}", "M")
            if m in idx:
                fn(idx[m], mo)

    for y in (years_s2 if "s2" in sensors else []):
        tf, tt = _year_window(y, start, end)
        b = s2_body(grid, y)
        d0 = b["input"]["data"][0]["dataFilter"]["timeRange"]
        d0["from"], d0["to"] = f"{tf}T00:00:00Z", f"{tt}T23:59:59Z"
        arr, ud, _ = post_process(b, counters, log_stage=log_stage, log_note=f"{site_id} S2 {y}")
        r = split_s2_year(arr)
        by_m, bl, n = _month_items(ud, y)
        items.update(by_m)
        base.update(bl)

        def f(i, mo, r=r, n=n):
            refl[i], cnt[i], cnt_alt[i], cnt_cld[i], npass[i] = (
                r["refl"][mo], r["count"][mo], r["count_alt"][mo], r["count_cld30"][mo], n[mo])
        put_year(y, f)
    vv = np.full((T, H, W), np.nan, np.float32)
    vh = np.full((T, H, W), np.nan, np.float32)
    c1 = np.zeros((T, H, W), np.uint16)
    n1 = np.zeros(T, np.int16)
    items1: dict = {}
    if orbit is not None and orbit[0] >= 0:
        for y in (years_s1 if "s1" in sensors else []):
            tf, tt = _year_window(y, start, end)
            arr, ud, _ = post_process(s1_body(grid, y, orbit[1], orbit[0], time_from=tf, time_to=tt), counters,
                                      log_stage=log_stage, log_note=f"{site_id} S1 {y}")
            r = split_s1_year(arr)
            by_m, _, n = _month_items(ud, y)
            items1.update(by_m)

            def g(i, mo, r=r, n=n):
                vv[i], vh[i], c1[i], n1[i] = r["db"][mo, 0], r["db"][mo, 1], r["count"][mo], n[mo]
            put_year(y, g)
    in_axis = {str(m) for m in months}
    items = {k: v for k, v in items.items() if k in in_axis}
    items1 = {k: v for k, v in items1.items() if k in in_axis}
    s2 = {"months": months, "refl": refl, "count": cnt, "count_alt": cnt_alt,
          "n_passes": npass, "n_used": cnt.reshape(T, -1).max(axis=1).astype(np.int16),
          "items_by_month": json.dumps(items), "baselines": json.dumps(base)}
    s1 = None
    if "s1" in sensors and orbit is not None and orbit[0] >= 0:
        s1 = {"months": months, "vv_db": vv, "vh_db": vh, "count": c1, "n_scenes": n1,
              "relative_orbit": int(orbit[0]), "direction": orbit[1],
              "orbit_candidates": "from Planetary Computer STAC metadata, see s1_orbit_rule",
              "items_by_month": json.dumps(items1), "speckle": "none", "pols": "vv,vh"}
    if "s2" not in sensors:
        s2 = None
    ds = build_dataset(site_id, grid, cfg, s2, s1, start, end)
    if s2 is not None:
        ds["s2_clear_count_cld30"] = (("month", "y", "x"), cnt_cld)
        from .qc import add_flags

        add_flags(ds)  # again, now that the CLD count exists
    from .regcontext import attr_value

    ds.attrs["other_registered_sites_in_chip"] = attr_value(grid, own_site_key)
    ds.attrs.update({
        "source": "sentinelhub",
        "s2_harmonised": "true: harmonizeValues=true, pre-04.00 convention, floor 0; no client-side offset",
        "s2_offset_policy": "applied server-side by Sentinel Hub harmonisation (equals PC rule)",
        "s2_clear_count_cld30": "Sen2Cor CLD <= 30 percent, valid pixels",
        "s2_n_passes_used_note": "per-month maximum of the per-pixel clear count (lower bound)",
        "s2_collection": "sentinel-2-l2a (CDSE Sentinel Hub Process API, mosaicking ORBIT)",
        "s1_collection": "sentinel-1-grd IW GRDH 1SDV (CDSE Sentinel Hub), gamma0 terrain, "
                         "Copernicus 30 m DEM, no speckle filter, dB",
        "s1_orbit_rule": "relative orbit chosen with select_orbit on Planetary Computer STAC metadata "
                         "and enforced in the evalscript from the product name; S1D scenes excluded",
        "s1_relative_orbit_enforced_server_side": "true",
    })
    write_site(ds, site_id, root)
    return ds


def build_many_sh(sites: pd.DataFrame, plan: pd.DataFrame, start: str, end: str, root, stage="sh_chips",
                  workers=4, skip_existing=True, sensors=("s1", "s2"), skip_roots=(),
                  pu_cap: float | None = None, req_cap: float | None = None, margin_pu: float = 150.0):
    """plan: columns site_id, year, s2_samples, s1_dates, s1_rel_orbit, s1_direction."""
    from .store import site_path

    done, failed = [], []

    pu0, rq0 = GLOBAL.sentinel_hub_pu, GLOBAL.sentinel_hub_requests

    def one(r):
        if skip_existing and any(site_path(r.site_id, x).exists() for x in (root, *skip_roots)):
            return r.site_id, None
        # hard budget: stop starting sites when this run's PU or requests approach the cap
        if pu_cap is not None and (GLOBAL.sentinel_hub_pu - pu0 + margin_pu > pu_cap
                                   or GLOBAL.sentinel_hub_requests - rq0 + 100 > (req_cap or 1e12)):
            return r.site_id, "BUDGET_STOP"
        p = plan[plan.site_id == r.site_id]
        y2 = [int(y) for y in p[p.s2_samples > 0].year]
        y1 = [int(y) for y in p[p.s1_dates > 0].year]
        o = (int(p.s1_rel_orbit.iloc[0]), str(p.s1_direction.iloc[0])) if len(p) else None
        try:
            build_site_sh(r.site_id, r.lon, r.lat, y2, y1, o, start, end, root=root, sensors=sensors,
                          log_stage=f"{stage}_req", own_site_key=getattr(r, "site_key", None))
            return r.site_id, None
        except Exception as e:  # noqa: BLE001 - one failing site must not stop the batch
            return r.site_id, repr(e)[:300]

    with (Stage(stage, "cdse_sentinelhub", note=f"{len(sites)} sites {start}..{end}", log_sh=False),
          ThreadPoolExecutor(workers) as ex):
        for sid, err in ex.map(one, list(sites.itertuples())):
            (failed if err else done).append((sid, err) if err else sid)
            print(sid, "FAIL " + err if err else "ok", flush=True)
    return done, failed
