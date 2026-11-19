"""Assemble the R3 test outputs from the cached daily statistics.

``uv run python -m bo.imagery.r3_cli`` writes ``results/imagery/scl_bright_target_test.csv`` (one row
per site and period, keyed by pilot or negative id) and ``..._by_group.csv`` (mean over sites with a
bootstrap interval). Registry commissioning dates are used only to select the "operating" days
(180 days after commissioning) and are not written to any output.
"""

from __future__ import annotations

import pandas as pd

from bo import paths

from .r3 import analyse

OPERATING_MARGIN_DAYS = 180


def main(version: str = "v0"):
    sfx = "" if version == "v0" else f"_{version}"
    pil = pd.read_parquet(paths.PROCESSED / "pilot" / f"pilot_sites_{version}.parquet")
    neg = pd.read_parquet(paths.PROCESSED / "pilot" / f"negatives_{version}.parquet")
    d1 = pd.read_parquet(paths.PROCESSED / "pilot" / f"r3_daily_pilot{sfx}.parquet")
    neg_path = paths.PROCESSED / "pilot" / f"r3_daily_negatives{sfx}.parquet"
    parts = [d1]
    groups = [pil[["pilot_id", "subtype"]].rename(columns={"pilot_id": "site_id", "subtype": "group"})]
    if neg_path.exists():
        parts.append(pd.read_parquet(neg_path))
        g = neg[["neg_id", "kind", "category"]].copy()
        g["group"] = g.apply(lambda r: "random_negative" if r.kind == "random"
                             else f"hard_negative_{r.category}", axis=1)
        groups.append(g[["neg_id", "group"]].rename(columns={"neg_id": "site_id"}))
        extra = g[g.kind == "hard"][["neg_id"]].assign(group="hard_negative_all")
        groups_all_hard = extra.rename(columns={"neg_id": "site_id"})
    daily = pd.concat(parts, ignore_index=True)
    grp = pd.concat(groups, ignore_index=True)
    op = pd.to_datetime(pil.set_index("pilot_id")["reg_commissioning_date"], errors="coerce") + pd.Timedelta(
        days=OPERATING_MARGIN_DAYS)
    op = op.dropna()
    per_site, agg = analyse(daily, grp, op)
    if neg_path.exists():
        ps_h, ag_h = analyse(daily, groups_all_hard.assign(group="hard_negative_all"), None)
        per_site = pd.concat([per_site, ps_h], ignore_index=True)
        agg = pd.concat([agg, ag_h], ignore_index=True)
    out = paths.RESULTS / "imagery"
    out.mkdir(parents=True, exist_ok=True)
    per_site.round(4).to_csv(out / f"scl_bright_target_test{sfx}.csv", index=False)
    agg.round(4).to_csv(out / f"scl_bright_target_test{sfx}_by_group.csv", index=False)
    piv = agg[agg.metric.isin(["ratio_clear_scl456", "ratio_clear_alt", "ratio_clear_cld10",
                               "ratio_clear_cld30", "ratio_clear_cld50",
                               "cloud_fp_given_ring_clear"])]
    piv = piv.assign(txt=piv.apply(lambda r: f"{r['mean']:.3f} [{r.ci95_low:.3f}, {r.ci95_high:.3f}]",
                                   axis=1))
    tab = piv.pivot_table(index=["group", "period"], columns="metric", values="txt",
                          aggfunc="first")
    tab["n_sites"] = piv.groupby(["group", "period"]).n_sites.max()
    tab = tab.reset_index()
    tab.to_csv(out / f"scl_bright_target_test{sfx}_table.csv", index=False)
    print(tab.to_string())


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "v0")
