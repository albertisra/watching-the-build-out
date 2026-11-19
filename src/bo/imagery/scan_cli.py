"""Run the scan benchmark on one federal state and write ``results/imagery/scan_benchmark.md``.

``uv run python -m bo.imagery.scan_cli --state Bremen --start 2024-01-01 --end 2024-12-31``
Candidate polygons are written to ``data/processed/scan/`` (not committed).
"""

from __future__ import annotations

import argparse
import json

import geopandas as gpd

from bo import paths

from .negatives import METRIC, german_states
from .scan import ScanConfig, run_scan

GERMANY_KM2 = 357_000.0  # approximate national area; used only to scale the benchmark (modelled)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="Bremen")
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2024-12-31")
    a = ap.parse_args(argv)
    states = german_states()
    st = states[states.bundesland == a.state]
    area_km2 = float(st.to_crs(METRIC).area.sum() / 1e6)
    parts = gpd.GeoDataFrame(geometry=list(st.explode(index_parts=False).geometry), crs=4326)
    cfg = ScanConfig()
    cands, summ = run_scan(parts, a.start, a.end, cfg)
    out = paths.PROCESSED / "scan"
    out.mkdir(parents=True, exist_ok=True)
    if len(cands):
        cands.to_parquet(out / f"candidates_{a.state}_{a.start[:4]}.parquet")
    d = summ["delta"]
    gb = summ["net_bytes"] / 1e9
    scale = GERMANY_KM2 / area_km2
    md = f"""# National scan benchmark: {a.state}, {a.start} to {a.end}

Written by `src/bo/imagery/scan_cli.py`. Quantities labelled **measured** come from this run
(counters in `results/imagery/quota_log.csv`, stage `scan_benchmark`); **modelled** quantities are
plain area scaling of the measured ones and carry no uncertainty estimate.

## Setup (measured)

- State outline: Natural Earth admin-1, area {area_km2:,.0f} km2 (low accuracy, benchmark only).
- Platform: Planetary Computer `sentinel-2-l2a`, anonymous, COG windowed reads, 8 reader threads per
  month and strip. Nothing is stored except candidate polygons and their monthly series.
- Reduced band set: B04, B08, B11 and SCL at 20 m through the COG overviews (`ScanConfig.scale = 2`).
  Scene cloud cover below {cfg.max_scene_cloud:.0f} percent from STAC metadata. Clear rule SCL 4, 5, 6 (A5);
  baseline offset per item (R5).
- Months: {summ["months"]}. Tiles processed: {summ["tiles"]} (tile-part pairs). Items read: {summ["items_read"]}.

## Cost (measured)

| Quantity | Value |
|---|---|
| Wall-clock time | {summ["elapsed_s"] / 60:.1f} min |
| Bytes received by GDAL (counting proxy, TLS included) | {gb:.2f} GB |
| TLS tunnels opened | {d["net_tunnels"]} |
| COG opens / window reads | {d["cog_opens"]} / {d["cog_window_reads"]} |
| STAC searches | {d["stac_searches"]} |
| Decoded bytes returned to Python | {d["decoded_bytes"] / 1e9:.2f} GB |
| Candidate polygons kept | {summ["n_candidates"]} |

HTTP requests inside GDAL are not visible to Python; the tunnel count is a lower bound because curl
reuses connections. No Sentinel Hub or openEO quota was used by the scan.

## Scaling to Germany (modelled, area factor {scale:,.0f})

Linear scaling of the measured cost by area and then by months to a 12-month window ({summ["months"]}
months were run), same band set: about {gb * scale * 12 / summ["months"] / 1000:,.1f} TB read and about
{summ["elapsed_s"] * scale * 12 / summ["months"] / 3600:,.0f} hours of wall-clock time on this machine and
connection, one year of Germany. Real figures will differ: the state outline excludes tile
margins that a national run shares, the cloud filter and overlap vary by region, and the
benchmark state is mostly urban and flat. The access note's range for all bands at 10 m is
7 to 34 TB per year (`docs/research/access_platforms.md`, derived); the reduced band set and 20 m
overview read are what bring the figure down.

## Limits

- 20 m pixels (400 m2) cannot resolve a 1 MW battery site (R2). The scan finds ground-mounted PV
  and large clearing events at best; it is a cost and design benchmark, not a detector.
- No seasonality removal (A8) and no land-cover mask: the candidate count is dominated by field
  operations and other seasonal vegetation change. It is a volume figure for the output size of the
  streaming design, not a detection rate.
- The candidate rule is a placeholder (A35) and is not validated here. Candidates are *detected*
  objects, not confirmed sites.
- Contains modified Copernicus Sentinel data 2024.

```json
{json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in summ.items() if k != "delta"})}
```
"""
    (paths.RESULTS / "imagery").mkdir(parents=True, exist_ok=True)
    (paths.RESULTS / "imagery" / "scan_benchmark.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
