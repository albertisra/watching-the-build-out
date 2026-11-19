"""Does the Sentinel-2 clear-pixel rule lose observations over battery yards? Before/after test.

Follow-up to ``results/imagery/scl_bright_target_test_v1.md`` (R3). That test compared a 40 m disk around the
registry coordinate with a ring on the same days, which mixes masking with land-cover differences between disk
and ring. Here each site is its own control: the ratio of clear observations inside the true OSM outline to
those in a ring (100 to 300 m from the outline) is computed before construction and after it, and the
quantity of interest is the ratio of the two (difference in differences on the log scale). A value below 1
means the finished structure loses clear observations that the same ground did not lose before.

Inputs: per-pixel monthly clear counts in the chip stores (``s2_clear_count`` = SCL 4/5/6,
``s2_clear_count_alt`` = SCL 2/4/5/6/7, ``s2_clear_count_cld30`` = CLD <= 30 %, Sentinel Hub only).
The MaStR commissioning month (observed) only selects the before and after months.
Run: ``uv run python -m bo.features.scl_did``. Output: ``results/features/scl_did_*.csv``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import ndimage

from bo import paths

from .signatures import FINE, OUT, block, fine_mask, load, month_offsets, public_sites

RULES = {"scl456": "s2_clear_count", "alt": "s2_clear_count_alt", "cld30": "s2_clear_count_cld30"}
PRE = (-1000, -24)  # every month up to 24 months before commissioning (F6, wider window for counts)
POST = (0, 1000)


def site_ratios(ds, fine) -> list[dict]:
    inside = block(fine, FINE) >= 0.5
    dist = ndimage.distance_transform_edt(~(block(fine, FINE) > 0)) * 10.0
    ring = (dist >= 100) & (dist <= 300)
    rows = []
    if inside.sum() < 2:
        return rows
    off = month_offsets(ds.month.values, ds.attrs["_ref"])
    passes = ds.s2_n_passes.values if "s2_n_passes" in ds else np.ones(len(off))
    for rule, var in RULES.items():
        if var not in ds:
            continue
        c = ds[var].values.astype(float)
        for period, (lo, hi) in (("pre", PRE), ("post", POST)):
            sel = (off >= lo) & (off <= hi) & (passes > 0)
            if sel.sum() < 6:
                continue
            if not ring.any():
                continue  # outline fills the chip: no ring inside the 640 m chip
            mi = c[sel][:, inside].mean(axis=1)
            mr = c[sel][:, ring].mean(axis=1)
            ci, cr = mi.sum(), mr.sum()
            ring_clear = mr >= 1.0
            lost = (np.median(c[sel][:, inside], axis=1) == 0) & ring_clear
            rows.append({"rule": rule, "period": period, "n_months": int(sel.sum()),
                         "clear_inside": ci, "clear_ring": cr, "ratio": ci / cr if cr > 0 else np.nan,
                         "months_ring_clear": int(ring_clear.sum()),
                         "lost_month_share": lost.sum() / ring_clear.sum() if ring_clear.any() else np.nan,
                         "n_px_inside": int(inside.sum())})
    return rows


def main() -> None:
    rng = np.random.default_rng(paths.SEED)
    sites = public_sites()
    rows = []
    for s in sites.itertuples():
        if s.geometry is None or pd.isna(s.reg_commissioning_date) or s.osm_power != "plant":
            continue
        ds = load(s.pilot_id)
        if "s2_clear_count" not in ds:
            continue
        ds.attrs["_ref"] = s.reg_commissioning_date
        for r in site_ratios(ds, fine_mask(ds, s.geometry)):
            rows.append({"pilot_id": s.pilot_id, "subtype": s.subtype,
                         "platform": "sentinelhub" if s.pilot_id.startswith("Q") else "planetary_computer", **r})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "scl_did_site_period.csv", index=False)
    w = df.pivot_table(index=["pilot_id", "subtype", "rule"], columns="period", values="ratio").dropna()
    w["did"] = w["post"] / w["pre"]
    lm = df.pivot_table(index=["pilot_id", "subtype", "rule"], columns="period", values="lost_month_share")
    w = w.join(lm.add_prefix("lost_")).reset_index()
    w.to_csv(OUT / "scl_did_sites.csv", index=False)
    summ = []
    for (sub, rule), g in w.groupby(["subtype", "rule"]):
        x = np.log(g.did.values)
        boots = [np.exp(rng.choice(x, len(x)).mean()) for _ in range(5000)]
        summ.append({"subtype": sub, "rule": rule, "n_sites": len(x), "did_geomean": float(np.exp(x.mean())),
                     "ci_lo": float(np.quantile(boots, 0.025)), "ci_hi": float(np.quantile(boots, 0.975)),
                     "did_min": float(g.did.min()), "did_max": float(g.did.max()),
                     "lost_month_share_pre": float(g.lost_pre.mean()),
                     "lost_month_share_post": float(g.lost_post.mean())})
    pd.DataFrame(summ).to_csv(OUT / "scl_did_summary.csv", index=False)
    print(w.to_string())
    print(pd.DataFrame(summ).to_string())


if __name__ == "__main__":
    main()
