"""Compare the stored S1 relative orbit and direction of each ee_r1 store with any SH or PC store at the same coordinates.

Reads attributes only; no network, no quota. Output: results/imagery/ee_vs_sh_orbit_check.csv
"""

from __future__ import annotations

import pandas as pd

from bo import paths

from .store import read_site, site_path

REFS = ("sh_v1", "sh_v1_s1", "v0")


def run() -> pd.DataFrame:
    q = pd.read_parquet(paths.PROCESSED / "labels" / "queue_round1.parquet")
    ref = pd.concat([pd.read_parquet(paths.PROCESSED / "pilot" / f)[[c, "lat", "lon"]].rename(columns={c: "ref_id"})
                     for f, c in (("pilot_sites_v0.parquet", "pilot_id"), ("negatives_v0.parquet", "neg_id"),
                                 ("pilot_sites_v1.parquet", "pilot_id"), ("negatives_v1.parquet", "neg_id"))],
                    ignore_index=True)
    rows = []
    for r in q.itertuples():
        p = site_path(r.queue_id, paths.CHIPS / "ee_r1")
        if not p.exists():
            continue
        m = ref[(abs(ref.lat - r.lat) < 1e-3) & (abs(ref.lon - r.lon) < 1e-3)]
        if m.empty:
            continue
        a = read_site(r.queue_id, paths.CHIPS / "ee_r1").attrs
        for rid in m.ref_id.unique():
            for root in REFS:
                if not site_path(rid, paths.CHIPS / root).exists():
                    continue
                b = read_site(rid, paths.CHIPS / root).attrs
                if "s1_relative_orbit" not in b:
                    continue
                ee = (a.get("s1_relative_orbit"), a.get("s1_pass_direction"))
                rf = (int(b["s1_relative_orbit"]), b["s1_pass_direction"])
                rows.append({"queue_id": r.queue_id, "ref_id": rid, "ref_root": root,
                             "ee_orbit": ee[0], "ee_direction": ee[1], "ref_orbit": rf[0], "ref_direction": rf[1],
                             "ee_orbit_rule": a.get("s1_orbit_rule", ""), "match": ee == rf})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    d = run()
    d.to_csv(paths.RESULTS / "imagery" / "ee_vs_sh_orbit_check.csv", index=False)
    print(len(d), "pairs;", int((~d.match).sum()), "mismatch")
    print(d.groupby("ref_root").match.agg(["size", "sum"]))
    print(d[~d.match].drop(columns="ee_orbit_rule").to_string())
