"""Agreement between first labels and blind relabels (and between labellers)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import EVENT_COLUMNS, is_month, month_index


def cohens_kappa(a, b) -> float:
    """Cohen's kappa for two equal-length label sequences. NaN if undefined (no items, or chance
    agreement is 1 because both raters used one identical category)."""
    a, b = list(a), list(b)
    if len(a) != len(b):
        raise ValueError("sequences differ in length")
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    if pe >= 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def month_errors(a, b) -> dict:
    """Absolute month error for pairs where both are YYYY-MM; special values (before_series, not_yet,
    empty) are compared by exact match and reported separately."""
    errs, sp_n, sp_match = [], 0, 0
    for x, y in zip(a, b):
        if is_month(x) and is_month(y):
            errs.append(abs(month_index(x) - month_index(y)))
        elif x or y:
            sp_n += 1
            sp_match += int(x == y)
    e = np.array(errs, dtype=float)
    return {
        "n_dated_pairs": len(errs),
        "mean_abs_error_months": float(e.mean()) if len(e) else float("nan"),
        "median_abs_error_months": float(np.median(e)) if len(e) else float("nan"),
        "share_within_1_month": float((e <= 1).mean()) if len(e) else float("nan"),
        "n_special_pairs": sp_n,
        "special_exact_match": (sp_match / sp_n) if sp_n else float("nan"),
    }


_EVENT_MONTHS = [c for c in EVENT_COLUMNS if c.endswith("_month")]
_PAIR_COLUMNS = ["site_class", "start_month", "complete_month", "confidence", *_EVENT_MONTHS]


def consistency_pairs(rows: pd.DataFrame) -> pd.DataFrame:
    """Pairs (first label, first blind relabel) per site and labeller from effective label rows
    (see labels.effective_rows). Sites without a relabel are left out."""
    out = []
    for (site, who), g in rows.groupby(["queue_id", "labeller_id"], sort=False):
        first = g[~g["is_relabel"]]
        again = g[g["is_relabel"]]
        if len(first) and len(again):
            f, r = first.iloc[0], again.iloc[0]
            out.append({"queue_id": site, "labeller_id": who,
                        "relabel_after_dop_seen": bool(r.get("relabel_after_dop_seen", False)),
                        **{f"{c}_1": f[c] for c in _PAIR_COLUMNS},
                        **{f"{c}_2": r[c] for c in _PAIR_COLUMNS}})
    return pd.DataFrame(out)


def agreement(rows: pd.DataFrame, dop_seen: bool | None = None) -> dict:
    """Class kappa, raw class agreement and month errors over first-vs-relabel pairs.
    `dop_seen` None uses all pairs; False keeps pairs whose first pass never showed a DOP chip (Sentinel-only
    repeat); True keeps the pairs whose relabel followed a pass 2 (`relabel_after_dop_seen`)."""
    p = consistency_pairs(rows)
    if dop_seen is not None and not p.empty:
        p = p[p["relabel_after_dop_seen"] == dop_seen].reset_index(drop=True)
    if p.empty:
        return {"n_pairs": 0}
    return {
        "n_pairs": len(p),
        "class_kappa": cohens_kappa(p["site_class_1"], p["site_class_2"]),
        "class_agreement": float((p["site_class_1"] == p["site_class_2"]).mean()),
        "start": month_errors(p["start_month_1"], p["start_month_2"]),
        "complete": month_errors(p["complete_month_1"], p["complete_month_2"]),
        "events": {c: month_errors(p[f"{c}_1"], p[f"{c}_2"]) for c in _EVENT_MONTHS
                   if (p[f"{c}_1"] != "").any() or (p[f"{c}_2"] != "").any()},
        "quantity_type": "observed (author labels)",
    }


def agreement_by_dop_exposure(rows: pd.DataFrame) -> dict:
    """Agreement split by whether the relabelled item's DOP chip had been shown in the first pass."""
    return {"all": agreement(rows), "sentinel_only_repeat": agreement(rows, dop_seen=False),
            "after_dop_seen": agreement(rows, dop_seen=True)}
