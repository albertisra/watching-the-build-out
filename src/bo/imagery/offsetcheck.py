"""Is the +0.1 offset step at the January 2022 baseline change handled on both platforms? (review finding I2)

Dark pixels are the sensitive test: a missing offset would add 0.1 to the darkest reflectances after 2022-01-25 and a
double application would clip them at 0. For each chip store the 1st percentile of the clear-pixel median B08 and B04 per
month is computed (B08 is near zero over water and shadow); medians over chips are compared across the change. For the
Planetary Computer route the raw digital numbers of one scene before and one after the change are read as well.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .store import read_site


def dark_series(root: Path, ids: list[str], bands=("B04", "B08")) -> pd.DataFrame:
    rows = []
    for sid in ids:
        ds = read_site(sid, root).load()
        months = pd.DatetimeIndex(ds.month.values)
        sel = np.nonzero((months >= "2021-07-01") & (months <= "2022-06-30"))[0]
        if not len(sel) or "s2_refl" not in ds:
            continue
        base = json.loads(ds.attrs.get("s2_processing_baseline_by_item", "{}"))
        items = json.loads(ds.attrs.get("s2_items_by_month", "{}"))
        for i in sel:
            r = {"site_id": sid, "month": str(months[i])[:7]}
            for b in bands:
                if b in ds.band.values:
                    v = ds.s2_refl.values[i, list(ds.band.values).index(b)]
                    v = v[np.isfinite(v)]
                    r[f"{b}_p1"] = float(np.percentile(v, 1)) if len(v) else np.nan
            c = Counter(base.get(x) for x in items.get(r["month"], []) if base.get(x))
            r["baselines"] = json.dumps(dict(c))
            rows.append(r)
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    g = df.groupby("month")[[c for c in df.columns if c.endswith("_p1")]].median()
    g["n_chips"] = df.groupby("month").site_id.nunique()
    g.insert(0, "platform", platform)
    return g.reset_index()
