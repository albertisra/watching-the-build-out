# R3 test: does the SCL 4/5/6 rule mask bright PV and battery sites as cloud?

Files: `scl_bright_target_test.csv` (one row per site and period), `scl_bright_target_test_by_group.csv`
(mean over sites with a 95 percent bootstrap interval over sites), `scl_bright_target_test_table.csv`
(the table below). Code: `src/bo/imagery/r3.py`, `r3_cli.py`. Raw daily statistics are cached in
`data/raw/sentinelhub/r3/` (not committed). Quantities are *detected* (model output of the Sen2Cor
scene classification and cloud probability), not observed ground truth.

## Method

- Data: Sentinel-2 L2A, 2023-01-01 to 2025-12-31, daily statistics from the CDSE Sentinel Hub Statistical
  API (server side, no pixels downloaded). Per day and polygon: fraction of pixels in each SCL class and
  the fraction with Sen2Cor cloud probability (`CLD`) at or below 10, 30 and 50 percent.
- Footprint: disk of 40 m radius around the site coordinate. Ring: 150 to 300 m. Neither depends on
  any registry attribute (A32).
- Ratio = clear observations in the footprint divided by clear observations in the ring, summed over the
  days on which both were observed. A ratio below 1 means the target is flagged as not clear more often
  than its surroundings. Rules: SCL 4, 5, 6 (A5 default); SCL 2, 4, 5, 6, 7 (alternative, A29); cloud
  probability at three thresholds (A33; the cloud-probability rule does not exclude shadow or snow).
- "operating" rows use only days from 180 days after the registry commissioning date; "all" rows use every
  day. The commissioning date selects days only and is not stored in any output.
- Controls: 50 hard negatives (OSM greenhouses, industrial land, car parks, quarries, warehouse roofs) with
  the footprint at the OSM polygon's representative point, and 50 random points.

## Result (mean ratio, 95 percent interval over sites; last column is the share of days the footprint is mostly cloud while the ring is mostly clear)

| group | period | n_sites | ratio_clear_scl456 | ratio_clear_alt | ratio_clear_cld10 | ratio_clear_cld30 | ratio_clear_cld50 | cloud_fp_given_ring_clear |
|---|---|---|---|---|---|---|---|---|
| battery | all | 20 | 0.986 [0.971, 1.000] | 0.992 [0.981, 1.001] | 0.983 [0.967, 0.997] | 0.995 [0.986, 1.004] | 0.997 [0.991, 1.003] | 0.010 [0.006, 0.015] |
| battery | operating | 14 | 0.959 [0.911, 0.991] | 0.971 [0.924, 0.999] | 0.968 [0.952, 0.984] | 0.991 [0.981, 1.000] | 0.995 [0.982, 1.006] | 0.008 [0.002, 0.016] |
| ground-mounted | all | 30 | 1.000 [0.990, 1.011] | 0.994 [0.987, 1.002] | 1.009 [1.001, 1.016] | 1.002 [0.995, 1.008] | 1.000 [0.994, 1.006] | 0.021 [0.014, 0.030] |
| ground-mounted | operating | 29 | 0.999 [0.989, 1.011] | 0.993 [0.985, 1.001] | 1.012 [1.004, 1.020] | 1.004 [0.997, 1.010] | 1.003 [0.997, 1.008] | 0.022 [0.014, 0.031] |
| hard_negative_all | all | 50 | 0.986 [0.972, 1.003] | 0.987 [0.976, 0.999] | 0.944 [0.927, 0.962] | 0.959 [0.942, 0.975] | 0.972 [0.957, 0.985] | 0.022 [0.016, 0.030] |
| hard_negative_car_park | all | 2 | 0.963 [0.947, 0.978] | 0.982 [0.969, 0.994] | 0.964 [0.958, 0.971] | 1.002 [1.001, 1.004] | 1.012 [1.006, 1.018] | 0.008 [0.007, 0.009] |
| hard_negative_greenhouse | all | 9 | 0.990 [0.970, 1.009] | 0.992 [0.969, 1.011] | 0.956 [0.912, 0.994] | 0.968 [0.931, 0.996] | 0.978 [0.950, 0.999] | 0.023 [0.009, 0.041] |
| hard_negative_industrial_yard | all | 15 | 0.977 [0.959, 0.997] | 0.981 [0.968, 0.997] | 0.950 [0.922, 0.975] | 0.972 [0.953, 0.991] | 0.982 [0.969, 0.996] | 0.018 [0.012, 0.025] |
| hard_negative_quarry | all | 15 | 1.004 [0.968, 1.050] | 1.003 [0.981, 1.034] | 0.962 [0.933, 0.989] | 0.974 [0.956, 0.992] | 0.986 [0.976, 0.998] | 0.016 [0.010, 0.023] |
| hard_negative_warehouse_roof | all | 9 | 0.974 [0.948, 1.001] | 0.966 [0.937, 0.992] | 0.891 [0.846, 0.936] | 0.895 [0.839, 0.947] | 0.916 [0.861, 0.967] | 0.044 [0.018, 0.074] |
| random_negative | all | 50 | 1.003 [0.994, 1.012] | 1.001 [0.993, 1.008] | 0.998 [0.993, 1.003] | 0.999 [0.995, 1.003] | 0.999 [0.995, 1.003] | 0.010 [0.007, 0.012] |

## Reading

- Ground-mounted PV: no evidence that the SCL 4/5/6 rule removes PV footprints more often than the
  surrounding ring (ratio close to 1 with a narrow interval, in operating and all days). The share of
  days on which the footprint is mostly cloud while the ring is clear is about twice the share at random
  points (last column), but small in absolute terms; it is the same size as at the hard negatives.
- Battery sites: the interval for the operating days lies slightly below 1 under SCL 4/5/6 and under the
  alternative rule, with only 14 sites and an upper bound close to 1. Treat it as a possible small loss of
  clear observations at container yards, not as a result.
- Controls: warehouse roofs lose more clear observations under the cloud-probability rule than under SCL
  4/5/6, so the test has the power to see bright-roof masking and the SCL rule shows less of it. Random
  points sit at 1, as they should.
- Decision for the pipeline: keep SCL 4/5/6 as the primary rule, store the alternative count
  (`s2_clear_count_alt`) next to it in every chip store, and revisit when Track B footprints allow the
  footprint disk to be replaced by the true polygon.

## Limits

- The footprint is a fixed disk around a registry coordinate. MaStR coordinates can sit at the plant edge or
  be imprecise, so the disk may include less target than assumed; this biases the ratio toward 1.
- Ring land cover differs from the target land cover (fields, roads), so the ratio mixes masking with
  genuine differences in cloud edge geometry.
- Pilot set version 0 has 20 batteries and 30 PV sites from a partial registry, a small sample. Dilation of
  the SCL cloud mask (up to 80 m around clouds, `docs/research/sentinel2.md` fact 17) acts on both areas alike.
- The SCL and `CLD` layers are 20 m products; a 40 m disk contains only about 12 native pixels.
- Contains modified Copernicus Sentinel data 2023 to 2025.
