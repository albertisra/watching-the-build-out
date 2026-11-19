# National scan benchmark: Bremen, 2024-01-01 to 2024-12-31

Written by `src/bo/imagery/scan_cli.py`. Quantities labelled **measured** come from this run
(counters in `results/imagery/quota_log.csv`, stage `scan_benchmark`); **modelled** quantities are
plain area scaling of the measured ones and carry no uncertainty estimate.

## Setup (measured)

- State outline: Natural Earth admin-1, area 385 km2 (low accuracy, benchmark only).
- Platform: Planetary Computer `sentinel-2-l2a`, anonymous, COG windowed reads, 8 reader threads per
  month and strip. Nothing is stored except candidate polygons and their monthly series.
- Reduced band set: B04, B08, B11 and SCL at 20 m through the COG overviews (`ScanConfig.scale = 2`).
  Scene cloud cover below 60 percent from STAC metadata. Clear rule SCL 4, 5, 6 (A5);
  baseline offset per item (R5).
- Months: 12. Tiles processed: 3 (tile-part pairs). Items read: 137.

## Cost (measured)

| Quantity | Value |
|---|---|
| Wall-clock time | 5.3 min |
| Bytes received by GDAL (counting proxy, TLS included) | 1.91 GB |
| TLS tunnels opened | 452 |
| COG opens / window reads | 1071 / 1071 |
| STAC searches | 2 |
| Decoded bytes returned to Python | 0.86 GB |
| Candidate polygons kept | 324 |

HTTP requests inside GDAL are not visible to Python; the tunnel count is a lower bound because curl
reuses connections. No Sentinel Hub or openEO quota was used by the scan.

## Scaling to Germany (modelled, area factor 926)

Linear scaling of the measured cost by area and then by months to a 12-month window (12
months were run), same band set: about 1.8 TB read and about
82 hours of wall-clock time on this machine and
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
{"tiles": 3, "items_read": 137, "elapsed_s": 317.665, "net_bytes": 1905413476, "n_candidates": 324, "months": 12, "scale": 2}
```
