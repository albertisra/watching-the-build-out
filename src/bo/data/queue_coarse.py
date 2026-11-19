"""Which round-1 queue items sit on rounded registry coordinates (review M2).

Reads the queue and the registry site table (matched by ``site_id``) and writes
``results/labels/queue_coarse_coordinates.csv``. The queue itself is not modified.
Items without a ``site_id`` (OSM or random negatives) are not registry positions and are skipped.
The precision class is a registry data-quality attribute (observed), not a feature.
"""
from __future__ import annotations

import pandas as pd

from bo import paths

QUEUE = paths.PROCESSED / "labels" / "queue_round1.parquet"
SITES = paths.PROCESSED / "registry" / "registry_sites.parquet"
OUT = paths.RESULTS / "labels" / "queue_coarse_coordinates.csv"
COARSE = ("dp1", "dp2", "dp3")  # at most 3 real decimals (about 100 m or coarser)


def coarse_queue_items(queue: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    s = sites[["site_id", "coord_precision_class", "coord_unc_m"]]
    m = queue[["queue_id", "site_id"]].dropna(subset=["site_id"]).merge(s, on="site_id", how="left")
    m = m[m["coord_precision_class"].isin(COARSE)]
    return (m.rename(columns={"coord_precision_class": "precision_class",
                              "coord_unc_m": "implied_position_uncertainty_m"})
            [["queue_id", "precision_class", "implied_position_uncertainty_m"]]
            .sort_values("queue_id").reset_index(drop=True))


def main() -> None:
    out = coarse_queue_items(pd.read_parquet(QUEUE), pd.read_parquet(SITES))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(out["precision_class"].value_counts().to_string())


if __name__ == "__main__":
    main()
