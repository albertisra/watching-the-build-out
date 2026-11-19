"""Feature values at confuser classes against operating pilot sites (descriptive only, no classifier).

Sentinel-2: Planetary Computer store ``demo150`` (July to September 2025, bands B03, B04, B08, B11) for pilot v0
sites and v0 negatives. Sentinel-1: Sentinel Hub store ``sh_v1_s1`` (2015 to 2026) for pilot v1 sites and v1
negatives, summarised over July to September 2025 so both sensors describe the same season. Platforms are never
mixed in one series. Pilot sites count as "operating" when the MaStR commissioning month (observed) is before
2025-04; this selects rows for the description only and is not stored as a feature.

Hard negatives are OSM objects whose representative point is the chip centre (``negatives_v*.parquet``,
assumption A34). Run: ``uv run python -m bo.features.confusers``.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from bo import paths
from bo.imagery import store

from .signatures import FIG, OUT
from .site import site_features

S2_COLS = ["s2_ndvi_c", "s2_ndbi_c", "s2_mndwi_c", "s2_b11_c", "s2_r1108_c", "s2_ndvi_ctr", "s2_b08_tex_c"]
S1_COLS = ["s1_vv_c", "s1_vh_c", "s1_vvvh_c", "s1_vv_p90_c", "s1_vv_ctr", "s1_vv_c_cv12"]
CUTOFF = pd.Timestamp("2025-04-01")
WINDOW = ("2025-07-01", "2025-09-01")


def groups(pilot: pd.DataFrame, neg: pd.DataFrame, date_col: str, id_col: str = "pilot_id") -> pd.DataFrame:
    p = pilot[pilot[date_col] < CUTOFF][[id_col, "subtype"]].rename(columns={id_col: "site", "subtype": "group"})
    n = neg[["neg_id", "category"]].rename(columns={"neg_id": "site", "category": "group"})
    return pd.concat([p, n], ignore_index=True)


def summarise(root, ids: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for r in ids.itertuples():
        if not store.site_path(r.site, root).exists():
            continue
        f = site_features(store.read_series(r.site, [root]), site_id=r.site)
        f = f[(f.month >= WINDOW[0]) & (f.month <= WINDOW[1])]
        rows.append({"site": r.site, "group": r.group, **f[cols].median().to_dict()})
    return pd.DataFrame(rows)


def main() -> None:
    pr = paths.PROCESSED / "pilot"
    p0, n0 = pd.read_parquet(pr / "pilot_sites_v0.parquet"), pd.read_parquet(pr / "negatives_v0.parquet")
    p1, n1 = pd.read_parquet(pr / "pilot_sites_v1.parquet"), pd.read_parquet(pr / "negatives_v1.parquet")
    s2 = summarise(paths.CHIPS / "demo150", groups(p0, n0, "commissioned"), S2_COLS)
    s1 = summarise(paths.CHIPS / "sh_v1_s1", groups(p1, n1, "reg_commissioning_date"), S1_COLS)
    s2.to_csv(OUT / "confuser_sites_s2.csv", index=False)
    s1.to_csv(OUT / "confuser_sites_s1.csv", index=False)
    out = []
    for name, df, cols in (("s2", s2, S2_COLS), ("s1", s1, S1_COLS)):
        for g, d in df.groupby("group"):
            for c in cols:
                v = d[c].dropna()
                if len(v):
                    out.append({"sensor": name, "group": g, "feature": c, "n": len(v), "median": v.median(),
                                "q25": v.quantile(0.25), "q75": v.quantile(0.75)})
    summ = pd.DataFrame(out)
    summ.to_csv(OUT / "confuser_summary.csv", index=False)
    order = ["battery", "ground-mounted", "greenhouse", "warehouse_roof", "car_park", "industrial_yard",
             "quarry", "random"]
    feats = [("s2", c) for c in ("s2_ndvi_c", "s2_ndbi_c", "s2_b11_c", "s2_mndwi_c")] + \
            [("s1", c) for c in ("s1_vv_c", "s1_vh_c", "s1_vvvh_c", "s1_vv_p90_c")]
    fig, axes = plt.subplots(2, 4, figsize=(13, 6))
    for ax, (sen, c) in zip(axes.ravel(), feats):
        df = s2 if sen == "s2" else s1
        data = [df.loc[df.group == g, c].dropna().values for g in order]
        ax.boxplot(data, showfliers=True, flierprops={"markersize": 2})
        ax.set_xticks(range(1, len(order) + 1))
        ax.set_xticklabels([f"{g}\n(n={len(d)})" for g, d in zip(order, data)], rotation=60, fontsize=6)
        ax.set_title(c, fontsize=8)
        ax.tick_params(labelsize=6)
    fig.suptitle("Centre-disk features, July to September 2025. S2: Planetary Computer, pilot v0 and negatives v0; "
                 "S1: Sentinel Hub, pilot v1 and negatives v1", fontsize=8)
    fig.text(0.01, 0.005, "Contains modified Copernicus Sentinel data 2024-2025; negatives from OSM "
             "(c) OpenStreetMap contributors", fontsize=5)
    fig.tight_layout()
    fig.savefig(FIG / "confusers_2025q3.png", dpi=130)
    plt.close(fig)
    print(summ.pivot_table(index=["sensor", "feature"], columns="group", values="median").round(3).to_string())


if __name__ == "__main__":
    main()
