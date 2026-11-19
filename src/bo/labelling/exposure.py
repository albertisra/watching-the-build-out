"""Queue items whose registry commissioning date the author has already seen in a figure.

Until 2026-11-18 `bo.features.signatures.series_figure` drew the MaStR commissioning month (red dashed line) on
`figures/signatures/<pilot_id>_series.png` for every public pilot site with a date. Since 2026-11-19 (review M4) the
regenerated figures draw no registry date, status, capacity or technology for sites that match a queue item, and
`aligned_yoy.png` holds non-queue sites only. The list here records what may already have been seen in the old
figures, so it stays valid and is not shrunk by the regeneration. Pilot sites are matched to
queue items by registry key, else by coordinates within max(`MATCH_MIN_M`, coordinate uncertainty) metres, the
uncertainty (`coord_unc_m`, registry site table; coarse-coordinate table for queue items) being the larger of the
two items'. The ids are stored with each label as
`registry_date_exposed` (shown in no UI) so that primary H2 and H3 can exclude them or report a sensitivity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bo import paths

MATCH_MIN_M = 100.0  # floor: site-scale position difference between a pilot centroid and a queue centroid
COARSE_FILE = paths.RESULTS / "labels" / "queue_coarse_coordinates.csv"
OUT_FILE = paths.RESULTS / "labels" / "registry_date_exposed_queue_ids.csv"


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def match_to_queue(pilot: pd.DataFrame, queue: pd.DataFrame, min_m: float = MATCH_MIN_M,
                   unc_m: dict[str, float] | None = None) -> pd.DataFrame:
    """Pilot rows (pilot_id, lat, lon, optional site_key) to queue ids. Columns: pilot_id, queue_id, how.
    Registry key first. Else the nearest queue item within max(min_m, unc of pilot, unc of queue item), where
    `unc_m` maps pilot_id and queue_id to the coordinate uncertainty in metres (missing means 0)."""
    unc = unc_m or {}
    out = []
    keys = {} if "site_id" not in queue else dict(zip(queue["site_id"].dropna(), queue["queue_id"][queue["site_id"].notna()]))
    qunc = queue["queue_id"].map(lambda i: unc.get(i, 0.0)).to_numpy(dtype=float)
    for r in pilot.itertuples():
        qid, how = keys.get(getattr(r, "site_key", None)), "registry_key"
        if qid is None:
            d = _haversine_m(r.lat, r.lon, queue["lat"].to_numpy(), queue["lon"].to_numpy())
            lim = np.maximum(min_m, np.maximum(qunc, unc.get(r.pilot_id, 0.0)))
            ok = np.where(d <= lim)[0]
            if len(ok):
                i = int(ok[np.argmin(d[ok])])
                qid, how = queue["queue_id"].iloc[i], f"coordinates_{d[i]:.0f}m"
        if qid is not None:
            out.append({"pilot_id": r.pilot_id, "queue_id": qid, "how": how})
    return pd.DataFrame(out, columns=["pilot_id", "queue_id", "how"])


def coordinate_uncertainty(pilot: pd.DataFrame, queue: pd.DataFrame) -> dict[str, float]:
    """coord_unc_m per pilot_id (through site_key) and queue_id (through site_id), registry_sites table; the
    larger of that and the coarse-coordinate table for queue items."""
    reg = pd.read_parquet(paths.PROCESSED / "registry" / "registry_sites.parquet", columns=["site_id", "coord_unc_m"])
    u = dict(zip(reg["site_id"], reg["coord_unc_m"].fillna(0.0)))
    out = {r.pilot_id: float(u.get(r.site_key, 0.0)) for r in pilot.itertuples()}
    for r in queue.itertuples():
        out[r.queue_id] = float(u.get(getattr(r, "site_id", None), 0.0))
    if COARSE_FILE.exists():
        c = pd.read_csv(COARSE_FILE)
        for r in c.itertuples():
            out[r.queue_id] = max(out.get(r.queue_id, 0.0), float(r.implied_position_uncertainty_m))
    return out


def load_coarse_ids(path=None) -> set[str]:
    """Queue items whose registry coordinate is rounded to 1 or 2 decimals (dp1, dp2). Used only to set the
    non-displayed `coord_coarse` flag on a label."""
    p = path or COARSE_FILE
    if not p.exists():
        return set()
    c = pd.read_csv(p, dtype=str)
    return set(c.loc[c["precision_class"].isin(["dp1", "dp2"]), "queue_id"])


def exposed_signature_ids() -> pd.DataFrame:
    """Queue ids of items drawn with a registry date in the signature figures (read-only use of signatures)."""
    from bo.features import signatures

    drawn = signatures.public_sites()
    drawn = drawn[drawn["reg_commissioning_date"].notna()]["pilot_id"]
    p1 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    p0 = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v0.parquet")
    pilot = pd.concat([p1[["pilot_id", "site_key", "lat", "lon"]], p0[["pilot_id", "site_key", "lat", "lon"]]])
    pilot = pilot[pilot["pilot_id"].isin(set(drawn))].drop_duplicates("pilot_id")
    q = pd.read_parquet(paths.PROCESSED / "labels" / "queue_round1.parquet")
    m = match_to_queue(pilot, q, unc_m=coordinate_uncertainty(pilot, q))
    m["figure"] = "figures/signatures/" + m["pilot_id"] + "_series.png"
    m["n_figures_drawn"] = len(drawn)
    return m.sort_values("queue_id").reset_index(drop=True)


def load_exposed_ids(path=None) -> set[str]:
    p = path or OUT_FILE
    if not p.exists():
        return set()
    return set(pd.read_csv(p, dtype=str)["queue_id"])


def main() -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df = exposed_signature_ids()
    df.to_csv(OUT_FILE, index=False)
    print(f"{df['n_figures_drawn'].iloc[0] if len(df) else 0} signature figures with a registry date; "
          f"{df['queue_id'].nunique()} queue items matched -> {OUT_FILE}")


if __name__ == "__main__":
    main()
