"""Phase 4 detectors (ml-engineer). Machinery only until labels exist.

Modules: `design` (plan constants), `guards` (allow-list, deny-list, fold and month guards), `freeze` (model freeze
file and fold-0 lock), `splits` (fold file reader), `assemble` (feature matrix and trailing windows), `targets`
(labels to monthly targets), `detector` (gradient boosting, calibration, tuning), `threshold` (site rule and
theta), `bootstrap`, `metrics`, `recall_curve`, `trackb` (DOP slot and paired comparison), `pipeline`,
`synthetic` (fake data for tests).
"""
