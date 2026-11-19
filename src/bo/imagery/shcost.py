"""Cost estimate for server-side chip building on CDSE Sentinel Hub (processing units, requests).

Model, calibrated on probes (``results/imagery/quota_log.csv``, stage ``sh_probe``):
- Process API PU = (64 x 64 / 512 x 512) / 3 x input bands x number of orbit samples in the time
  range, 16-bit output (a 108-band output costs the same as a 27-band one: only inputs count).
  The measured 6.083 PU for 146 samples and 8 input bands equals 0.015625 / 3 x 8 x 146.
- Sentinel-1 (GRD, orthorectified gamma0 terrain, orbit filter inside the evalscript): 1.589 PU
  measured for one site-year with 31 acquisitions on the chosen orbit, so 0.0512 PU per
  acquisition (the other orbits of the same direction are loaded and dropped inside the
  evalscript, so this per-acquisition figure carries that overhead for a typical site).
- One request per site and calendar year and sensor.
The sample counts per site and year come from Planetary Computer STAC metadata (no pixels).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from bo import paths

from .geo import chip_grid
from .io import stac_client
from .s1 import select_orbit
from .s1pipe import item_records, search_s1
from .s2pipe import dedupe_items, group_passes, search_s2

PU_PER_SAMPLE_BAND = 64 * 64 / (512 * 512) / 3
S2_INPUT_BANDS = 8  # six reflectance bands, SCL, CLD (dataMask is not counted)
S1_PU_PER_DATE = 1.5885 / 31
MONTHLY_PU = 10_000
MONTHLY_REQ = 10_000
SAFE_SHARE = 0.60


def site_counts(site_id: str, lon: float, lat: float, s2_start="2017-01-01", s1_start="2015-01-01",
                end="2026-10-31") -> pd.DataFrame:
    g = chip_grid(lon, lat)
    cl = stac_client()
    p = group_passes(dedupe_items(search_s2(g.bounds_lonlat(), s2_start, end, cl)))
    s2 = pd.Series([x[0].datetime.year for x in p]).value_counts()
    recs = item_records(search_s1(g.bounds_lonlat(), s1_start, end, cl), g)
    ch = select_orbit(recs)
    dates = pd.Series([pd.Timestamp(r["date"]).year for r in recs if ch and r["covers"]
                       and r["relative_orbit"] == ch.relative_orbit and r["direction"] == ch.direction]
                      ).value_counts() if ch else pd.Series(dtype=int)
    years = range(int(s1_start[:4]), int(end[:4]) + 1)
    rows = []
    for y in years:
        rows.append({"site_id": site_id, "year": y, "s2_samples": int(s2.get(y, 0)) if y >= int(s2_start[:4]) else 0,
                     "s1_dates": int(dates.get(y, 0)),
                     "s1_rel_orbit": ch.relative_orbit if ch else -1,
                     "s1_direction": ch.direction if ch else ""})
    return pd.DataFrame(rows)


def estimate(counts: pd.DataFrame) -> pd.DataFrame:
    c = counts.copy()
    c["s2_requests"] = (c.s2_samples > 0).astype(int)
    c["s1_requests"] = (c.s1_dates > 0).astype(int)
    c["s2_pu"] = c.s2_samples * S2_INPUT_BANDS * PU_PER_SAMPLE_BAND
    c["s1_pu"] = c.s1_dates * S1_PU_PER_DATE
    return c


def used_this_month(log=None, month: str | None = None) -> tuple[float, int]:
    """Sentinel Hub PU and requests already logged in the calendar month (UTC)."""
    q = pd.read_csv(log or (paths.RESULTS / "imagery" / "quota_log.csv"))
    q = q[q.platform.str.contains("sentinelhub", na=False)]
    if month is None:
        month = pd.Timestamp.now("UTC").strftime("%Y-%m")
    q = q[q.timestamp_utc.str.startswith(month)]
    # stage rows only, so nested site rows are not counted twice
    q = q[~q.stage.str.endswith("_site")]
    return float(q.sentinel_hub_pu.sum()), int(q.sentinel_hub_requests.sum())


def decide(total_pu: float, total_req: int, used_pu: float, used_req: int) -> dict:
    limit_pu, limit_req = SAFE_SHARE * MONTHLY_PU, SAFE_SHARE * MONTHLY_REQ
    return {"limit_pu": limit_pu, "limit_requests": limit_req,
            "used_pu": used_pu, "used_requests": used_req,
            "total_pu_after": used_pu + total_pu, "total_requests_after": used_req + total_req,
            "proceed": bool(used_pu + total_pu <= limit_pu and used_req + total_req <= limit_req)}


def run_estimate(sites: pd.DataFrame, workers: int = 4, **kw) -> pd.DataFrame:
    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(lambda r: site_counts(r.site_id, r.lon, r.lat, **kw), sites.itertuples()))
    return estimate(pd.concat(parts, ignore_index=True))
