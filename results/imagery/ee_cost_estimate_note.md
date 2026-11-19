# Earth Engine cost estimate (probe of 3 pilot v1 sites by 2 years)

Method: the same yearly images the chip backend fetches (S2: 12 monthly medians plus 3 counts each, 108 bands; S1: 12 months of VV, VH and
count on one fixed orbit, 36 bands) were exported once as small batch tasks to an Earth Engine asset (free asset storage, no Drive or
Cloud Storage) and `batch_eecu_usage_seconds` was read from the task status; the assets were deleted afterwards. Interactive
`computePixels` does not report EECU, and the Cloud Monitoring route is not usable because the Monitoring API is not enabled for the
project. Whether interactive requests cost the same as the batch equivalent is therefore **unmeasured**; a x3 safety row is given.
Sites Q010, Q014 (batteries) and Q046 (PV park), years 2023 and 2024. Probe total 115.7 EECU-seconds (0.03 EECU-hours; the limit was
5 EECU-hours). The twelve measurements are in `quota_log.csv` (platform earthengine, column eecu_seconds).

Per site-year: S2 mean 16.3 EECU-s (13.4 to 21.5), S1 mean 3.0 EECU-s (1.6 to 5.3).
Extrapolation assumes 10 S2 years (2017 to 2026) and 12 S1 years (2015 to 2026) per site and linear scaling; sites with more
overlapping tiles cost more (the PV park was the dearest). Both the pilot set (150 chips) and a 400-site queue fit the 150 EECU-hour
monthly Community tier: 5.5 % (pilot) and 14.7 % (queue) at batch cost, 16.6 % and 44.2 % with the x3 margin (`ee_cost_estimate.csv`). Concurrent-request and rate limits were not
tested at scale. Earth Engine S1 is sigma0 with an ellipsoid-based terrain correction, not gamma0 terrain-flattened (about 0.6 to 1.0 dB
lower than the Sentinel Hub stores for the two compared sites, `ee_vs_sh_check.csv`).
