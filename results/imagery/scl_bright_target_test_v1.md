# R3 test on pilot v1 (50 sites, ids Q000 to Q049)

Same method, period (2023-01-01 to 2025-12-31), footprint (40 m disk) and ring (150 to 300 m) as
`scl_bright_target_test.md` (pilot v0). Files: `scl_bright_target_test_v1.csv`, `..._v1_by_group.csv`,
`..._v1_table.csv`. Negatives are the 100 of `negatives_v1` (99 reused from the v0 statistics, one new random point).
The "operating" rows use days from 180 days after commissioning; most v1 batteries were commissioned in 2025 or
2026, so only 6 battery sites have operating days in the window. Mean ratio and 95 percent interval over sites;
last column is the share of days with a mostly cloud-flagged footprint under a clear ring.

| group | period | n_sites | ratio_clear_scl456 | ratio_clear_alt | ratio_clear_cld10 | ratio_clear_cld30 | ratio_clear_cld50 | cloud_fp_given_ring_clear |
|---|---|---|---|---|---|---|---|---|
| battery | all | 20 | 1.001 [0.982, 1.019] | 1.001 [0.989, 1.011] | 0.989 [0.976, 1.002] | 0.993 [0.980, 1.003] | 0.996 [0.988, 1.004] | 0.014 [0.008, 0.023] |
| battery | operating | 6 | 0.998 [0.953, 1.041] | 0.998 [0.984, 1.012] | 0.997 [0.974, 1.016] | 1.001 [0.987, 1.015] | 1.001 [0.991, 1.013] | 0.010 [0.001, 0.023] |
| ground-mounted | all | 30 | 0.998 [0.990, 1.005] | 0.994 [0.987, 1.002] | 0.993 [0.981, 1.002] | 0.997 [0.984, 1.005] | 0.997 [0.985, 1.006] | 0.015 [0.011, 0.019] |
| ground-mounted | operating | 18 | 0.999 [0.984, 1.016] | 0.997 [0.984, 1.010] | 1.000 [0.977, 1.014] | 1.003 [0.976, 1.020] | 0.999 [0.972, 1.017] | 0.014 [0.007, 0.023] |
| hard_negative_all | all | 50 | 0.986 [0.972, 1.003] | 0.987 [0.976, 0.999] | 0.944 [0.927, 0.962] | 0.959 [0.942, 0.975] | 0.972 [0.957, 0.985] | 0.022 [0.016, 0.030] |
| hard_negative_warehouse_roof | all | 9 | 0.974 [0.948, 1.001] | 0.966 [0.937, 0.992] | 0.891 [0.846, 0.936] | 0.895 [0.839, 0.947] | 0.916 [0.861, 0.967] | 0.044 [0.018, 0.074] |
| random_negative | all | 50 | 1.003 [0.993, 1.012] | 1.000 [0.992, 1.007] | 0.997 [0.993, 1.002] | 0.999 [0.995, 1.004] | 0.999 [0.995, 1.003] | 0.009 [0.007, 0.012] |

## Reading

- Ground-mounted PV: ratio near 1 under SCL 4/5/6 and under every alternative, as for v0. No evidence of cloud masking.
- Batteries: the small deficit seen in v0 (14 operating sites) does not appear in v1 (6 operating sites, interval
  spanning 1). With both samples small the battery question stays open, not settled; decision unchanged: SCL 4/5/6
  primary, alternative counts stored.
- Controls behave as in v0 (warehouse roofs lose clear observations under cloud probability, random points do not).
- Limits as in v0: fixed disk around a registry coordinate, 20 m SCL and CLD layers, small samples.
  Contains modified Copernicus Sentinel data 2023 to 2025.
