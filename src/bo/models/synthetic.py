"""Synthetic sites with a known signal, for software tests of the detector machinery (no real data, no labels).

Battery positives get a strong Sentinel-1 VV step from their start month on (amplitude grows with size); PV
positives get no signal at all (a pure noise class); negatives are noise. Every number written by `main` is a
property of this fake data and is named ``synthetic_*``: it says nothing about real detection performance.

``uv run python -m bo.models.synthetic`` writes `results/models/synthetic_*.csv`.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from bo import paths
from bo.features.allowlist import FEATURE_COLUMNS
from bo.labelling.schema import AFTER_SERIES, NOT_VISIBLE, empty_events

from . import design
from .detector import DetectorConfig
from .metrics import calibration_table
from .pipeline import develop, join_inputs
from .recall_curve import recall_curve
from .targets import monthly_targets

SYN_FEATURES = ("s1_vv_c", "s1_vh_c", "s2_r1108_c", "s2_vnir_c")


def make_synthetic(n_blocks: int = 40, sites_per_block: int = 5, seed: int = paths.SEED,
                   months: pd.DatetimeIndex | None = None, amplitude: float = 4.0
                   ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(features, labels, splits, sizes). Labels are in the `targets.primary_labels` format (schema v2)."""
    rng = np.random.default_rng(seed)
    months = months if months is not None else pd.date_range("2022-01-01", design.D_END, freq="MS")
    n = n_blocks * sites_per_block
    site_ids = [f"S{i:04d}" for i in range(n)]
    blocks = np.repeat(np.arange(n_blocks), sites_per_block)
    fold_of_block = rng.permutation(np.arange(n_blocks) % design.N_FOLDS)
    cls = rng.choice(["battery", "PV", "none"], size=n, p=[0.35, 0.35, 0.30])
    mw = 10 ** rng.uniform(0, 2.3, size=n)
    lo, hi = months.get_loc(pd.Timestamp("2023-01-01")), months.get_loc(pd.Timestamp("2025-06-01"))
    start_idx = rng.integers(lo, hi, size=n)
    frames, labels = [], []
    for i, sid in enumerate(site_ids):
        x = rng.normal(0, 1, size=(len(months), len(FEATURE_COLUMNS)))
        f = pd.DataFrame(x, columns=list(FEATURE_COLUMNS))
        f["s2_qc_flag"], f["s2_valid_c"], f["s1_valid_c"] = 0.0, 1.0, 1.0
        events = {}
        if cls[i] in ("battery", "PV"):
            # schema v2 events: no separate clearing phase, structures from the start month, not complete
            code = "bat" if cls[i] == "battery" else "pv"
            events = {f"{code}_clear_month": NOT_VISIBLE, f"{code}_struct_month": f"{months[start_idx[i]]:%Y-%m}",
                      f"{code}_complete_month": AFTER_SERIES}
        if cls[i] == "battery":
            gain = amplitude * np.clip(np.log10(mw[i]) / 1.0, 0.3, 1.0)
            f.loc[start_idx[i]:, "s1_vv_c"] += gain
        f.insert(0, "month", months)
        f.insert(0, "site_id", sid)
        frames.append(f)
        labels.append({"site_id": sid, "site_class": cls[i], "colocated": "none", **empty_events(), **events,
                       "confidence": 3, "labeller_id": "synthetic", "registry_date_exposed": False,
                       "label_pass_used": "pre_dop"})
    features = pd.concat(frames, ignore_index=True)
    splits = pd.DataFrame({"queue_id": site_ids, "site_id": site_ids, "block_id": [f"B{b:03d}" for b in blocks],
                           "fold": fold_of_block[blocks], "cluster_id": site_ids,
                           "open_dop": rng.random(n) < 0.5})
    sizes = pd.DataFrame({"site_id": site_ids, "mw": mw, "site_class": cls})
    return features, pd.DataFrame(labels), splits, sizes


def synthetic_targets(labels: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """Targets of the synthetic labels. Clearing is `not_visible` and completion `after_series`, so the onsets
    ``clear`` and ``struct`` give the same y; the argument here is not the author's mapping choice for real labels."""
    return monthly_targets(labels, features[["site_id", "month"]], onset="struct", brackets="point")


def run(n_boot: int = 200, max_iter: int = 60) -> dict[str, pd.DataFrame]:
    features, labels, splits, sizes = make_synthetic()
    targets = synthetic_targets(labels, features)
    data = join_inputs(features, targets, splits)
    cfgs = [DetectorConfig(t, SYN_FEATURES, windows=(3,), max_iter=max_iter) for t in design.TECHNOLOGIES]
    res = develop(data, cfgs, n_boot=n_boot)
    pos = res.sites[(res.sites["technology"] == "battery") & (res.sites["truth"] == 1)].merge(sizes, on="site_id")
    curve, summary = recall_curve(pos, "mw", n_boot=n_boot)
    o = res.oof.dropna(subset=["y"])
    cal = pd.concat([calibration_table(g["y"], g["p"]).assign(technology=t) for t, g in o.groupby("technology")])
    th = pd.DataFrame([{"technology": t, **vars(r)} for t, r in res.thresholds.items()])
    return {"metrics": res.metrics, "thresholds": th, "calibration": cal, "recall_curve": curve,
            "recall_curve_summary": pd.DataFrame([summary])}


def main() -> None:
    out = paths.RESULTS / "models"
    out.mkdir(parents=True, exist_ok=True)
    for name, df in run().items():
        df = df.assign(data="synthetic (software test, not a result)")
        df.to_csv(out / f"synthetic_{name}.csv", index=False)
    print(json.dumps(sorted(p.name for p in out.glob("synthetic_*.csv"))))


if __name__ == "__main__":
    main()
