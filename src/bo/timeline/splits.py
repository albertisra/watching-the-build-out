"""Spatial block folds for the labelling queue (analysis plan v1.0, Section 4.1; A71).

* Blocks: 50 km cells in EPSG:3035, aligned to the CRS origin.
* Clusters: all queue sites linked by single linkage at 2 km; each cluster is atomic and goes to the
  block of its medoid (the member with the smallest summed distance to the other members).
* Folds: 5, balanced greedily over blocks on queue counts of battery positives, PV positives, negatives
  and open-DOP-state sites. Balancing never reads dates, labels, status or capacity. Fold 0 is the locked
  test fold.

"Battery positive" and "PV positive" here are queue composition (registry technology of the queued site,
from ``queue_round1_strata.parquet``, column ``technology`` only), not author labels. "Open-DOP state" is
a state with an open DOP source in ``bo.imagery.dop.SOURCES`` minus use-restricted states (Mecklenburg-
Vorpommern, STATUS decision of 2026-11-18).

The assignment is written once. ``--force`` overwrites and appends a row to the force log.

Run: ``uv run python -m bo.timeline.splits [--force --reason "..."]``
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist, squareform

from bo.paths import PROCESSED, RESULTS, SEED

BLOCK_M = 50_000.0
LINK_M = 2_000.0
N_FOLDS = 5
TEST_FOLD = 0
COUNT_COLS = ("n_battery", "n_pv", "n_negative", "n_open_dop")

QUEUE = PROCESSED / "labels" / "queue_round1.parquet"
STRATA = PROCESSED / "labels" / "queue_round1_strata.parquet"
SPLIT_FILE = PROCESSED / "splits" / "blocks_v1.parquet"
SUMMARY_FILE = RESULTS / "timeline" / "split_v1_summary.csv"
FORCE_LOG = RESULTS / "timeline" / "split_v1_force_log.csv"


def open_dop_states() -> set[str]:
    from bo.imagery import dop

    return set(dop.SOURCES) - dop.restricted_states()


def project_3035(lat, lon) -> tuple[np.ndarray, np.ndarray]:
    t = Transformer.from_crs(4326, 3035, always_xy=True)
    x, y = t.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.asarray(x), np.asarray(y)


def cluster_sites(x: np.ndarray, y: np.ndarray, link_m: float = LINK_M) -> np.ndarray:
    """Single-linkage cluster ids (0-based, ordered by first appearance) at ``link_m`` metres."""
    xy = np.column_stack([x, y])
    if len(xy) == 1:
        return np.zeros(1, int)
    lab = fcluster(linkage(xy, method="single"), t=link_m, criterion="distance")
    _, first = np.unique(lab, return_index=True)
    order = {lab[i]: k for k, i in enumerate(sorted(first))}
    return np.array([order[v] for v in lab])


def medoid_index(xy: np.ndarray) -> int:
    if len(xy) == 1:
        return 0
    d = squareform(pdist(xy))
    return int(np.argmin(d.sum(axis=1)))


def block_of(x: float, y: float, size: float = BLOCK_M) -> tuple[int, int]:
    return int(np.floor(x / size)), int(np.floor(y / size))


def balance_folds(counts: pd.DataFrame, n_folds: int = N_FOLDS, seed: int = SEED) -> pd.Series:
    """Greedy balancing of blocks (rows of ``counts``) over folds.

    Blocks are visited by decreasing total count, ties in a seeded random order. Each block goes to the
    fold that minimises the summed squared relative excess over the per-fold targets after adding it;
    ties go to the fold with fewer blocks, then the lower fold index. The score is the change in the
    summed imbalance of all folds, so an empty fold is preferred over one already near its target.
    """
    rng = np.random.default_rng(seed)
    c = counts[list(COUNT_COLS)].to_numpy(float)
    target = c.sum(axis=0) / n_folds
    scale = np.where(target > 0, target, 1.0)
    order = np.lexsort((rng.permutation(len(c)), -c.sum(axis=1)))
    totals = np.zeros((n_folds, c.shape[1]))
    nblocks = np.zeros(n_folds, int)
    fold = np.empty(len(c), int)
    for i in order:
        # Change in the total squared relative imbalance over all folds if block i joins fold f.
        after = (((totals + c[i]) - target) / scale) ** 2
        before = ((totals - target) / scale) ** 2
        score = (after - before).sum(axis=1)
        best = min(range(n_folds), key=lambda f: (round(score[f], 12), nblocks[f], f))
        fold[i] = best
        totals[best] += c[i]
        nblocks[best] += 1
    return pd.Series(fold, index=counts.index, name="fold")


def assign(queue: pd.DataFrame, technology: pd.Series, seed: int = SEED) -> pd.DataFrame:
    """Per-site table: queue_id, site_id, cluster_id, block_id, fold (no coordinates)."""
    q = queue.reset_index(drop=True)
    tech = technology.reindex(q["queue_id"]).to_numpy()
    x, y = project_3035(q["lat"], q["lon"])
    cl = cluster_sites(x, y)
    xy = np.column_stack([x, y])
    block = np.empty(len(q), object)
    for c in np.unique(cl):
        m = np.flatnonzero(cl == c)
        bx, by = block_of(*xy[m[medoid_index(xy[m])]])
        block[m] = f"E{bx}N{by}"
    open_states = open_dop_states()
    site = pd.DataFrame({
        "queue_id": q["queue_id"].to_numpy(),
        "site_id": q["site_id"].to_numpy(),
        "cluster_id": cl,
        "block_id": block,
        "n_battery": (tech == "battery").astype(int),
        "n_pv": (tech == "ground_pv").astype(int),
        "n_negative": pd.isna(tech).astype(int),
        "n_open_dop": q["bundesland"].isin(open_states).to_numpy().astype(int),
    })
    unknown = set(pd.Series(tech).dropna()) - {"battery", "ground_pv"}
    if unknown:
        raise ValueError(f"unexpected technology values {unknown}")
    blocks = site.groupby("block_id")[list(COUNT_COLS)].sum().sort_index()
    fold = balance_folds(blocks, seed=seed)
    site["fold"] = site["block_id"].map(fold).astype(int)
    site["role"] = np.where(site["fold"] == TEST_FOLD, "test", "development")
    # Atomic clusters never split across folds.
    assert site.groupby("cluster_id")["fold"].nunique().max() == 1
    return site


def summarise(site: pd.DataFrame, file_sha256: str, content_sha256: str, seed: int) -> pd.DataFrame:
    g = site.groupby("fold")
    out = pd.DataFrame({
        "n_sites": g.size(),
        "n_clusters": g["cluster_id"].nunique(),
        "n_blocks": g["block_id"].nunique(),
        **{c: g[c].sum() for c in COUNT_COLS},
    }).reset_index()
    out["role"] = np.where(out["fold"] == TEST_FOLD, "test (locked)", "development")
    tot = out[["n_sites", "n_clusters", "n_blocks", *COUNT_COLS]].sum()
    tot_row = {"fold": "all", "role": "all", **tot.to_dict()}
    out = pd.concat([out.astype({"fold": str}), pd.DataFrame([tot_row])], ignore_index=True)
    out["quantity_type"] = "observed (queue composition counts)"
    out["block_m"] = int(BLOCK_M)
    out["link_m"] = int(LINK_M)
    out["seed"] = seed
    out["split_file"] = "data/processed/splits/blocks_v1.parquet"
    out["file_sha256"] = file_sha256
    out["content_sha256"] = content_sha256
    return out


def content_hash(site: pd.DataFrame) -> str:
    cols = ["queue_id", "site_id", "cluster_id", "block_id", "fold"]
    text = site[cols].sort_values("queue_id").to_csv(index=False)
    return hashlib.sha256(text.encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(queue_path: Path = QUEUE, strata_path: Path = STRATA) -> tuple[pd.DataFrame, pd.Series]:
    q = pd.read_parquet(queue_path, columns=["queue_id", "site_id", "lat", "lon", "bundesland"])
    # Only the technology column is read from the strata file (plan 4.1 balancing counts).
    s = pd.read_parquet(strata_path, columns=["queue_id", "technology"])
    if not q["queue_id"].is_unique or set(q["queue_id"]) != set(s["queue_id"]):
        raise ValueError("queue and strata files do not match one to one")
    return q, s.set_index("queue_id")["technology"]


def build(force: bool = False, reason: str = "", out: Path = SPLIT_FILE, summary: Path = SUMMARY_FILE,
          force_log: Path = FORCE_LOG, queue_path: Path = QUEUE, strata_path: Path = STRATA,
          seed: int = SEED) -> pd.DataFrame:
    out, summary, force_log = Path(out), Path(summary), Path(force_log)
    if out.exists() and not force:
        raise FileExistsError(f"{out.name} exists; the assignment is written once. Use --force with "
                              "--reason to overwrite (logged).")
    if out.exists() and force:
        if not reason:
            raise ValueError("--force needs --reason")
        old = file_hash(out)
        row = pd.DataFrame([{"timestamp_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                             "reason": reason, "previous_file_sha256": old}])
        force_log.parent.mkdir(parents=True, exist_ok=True)
        row.to_csv(force_log, mode="a", header=not force_log.exists(), index=False)
    q, tech = load_inputs(queue_path, strata_path)
    site = assign(q, tech, seed=seed)
    cols = ["queue_id", "site_id", "cluster_id", "block_id", "fold", "role"]
    out.parent.mkdir(parents=True, exist_ok=True)
    site[cols].to_parquet(out, index=False)
    summ = summarise(site, file_hash(out), content_hash(site), seed)
    summary.parent.mkdir(parents=True, exist_ok=True)
    summ.to_csv(summary, index=False)
    return summ


def fold_map(split: pd.DataFrame | None = None, split_file: Path = SPLIT_FILE) -> dict[str, int]:
    """Map every ``queue_id`` and every non-empty ``site_id`` of the assignment to its fold.

    Feature frames key sites by either id (negatives have no registry ``site_id``), so both are keys.
    Raises if one key would map to two folds.
    """
    s = pd.read_parquet(split_file) if split is None else split
    out: dict[str, int] = {}
    for col in ("queue_id", "site_id"):
        for key, f in zip(s[col], s["fold"], strict=True):
            if pd.isna(key):
                continue
            key, f = str(key), int(f)
            if out.get(key, f) != f:
                raise ValueError(f"id {key} maps to two folds")
            out[key] = f
    return out


def fold_of_block(split: pd.DataFrame, block_id: str) -> int | None:
    """Fold inherited by a later site in ``block_id`` (plan 4.1); None if the block holds no queue site."""
    m = split.loc[split["block_id"] == block_id, "fold"].unique()
    return int(m[0]) if len(m) else None


def replace_site(old_id: str, new_id: str, reason: str, split_file: Path = SPLIT_FILE, summary: Path = SUMMARY_FILE,
                 force_log: Path = FORCE_LOG, queue_path: Path = QUEUE, strata_path: Path = STRATA,
                 seed: int = SEED) -> int:
    """Swap one queue site in the written assignment without touching any other row (logged, plan 4.1).

    The new site must lie 2 km or more from every other queue site (own cluster). It inherits the fold of
    its 50 km block; the block must already hold queue sites (otherwise ValueError, balance by hand).
    Returns the fold. Writes the force log row and the summary.
    """
    split = pd.read_parquet(split_file)
    q, tech = load_inputs(queue_path, strata_path)
    others = q[(q["queue_id"] != new_id) & (q["queue_id"] != old_id)]
    n = q[q["queue_id"] == new_id].iloc[0]
    x, y = project_3035([n["lat"]], [n["lon"]])
    ox, oy = project_3035(others["lat"], others["lon"])
    if np.hypot(ox - x[0], oy - y[0]).min() < LINK_M:
        raise ValueError("new site within 2 km of another queue site; it would join a cluster")
    bx, by = block_of(x[0], y[0])
    block = f"E{bx}N{by}"
    rest = split[split["queue_id"] != old_id]
    fold = fold_of_block(rest, block)
    if fold is None:
        raise ValueError("block holds no queue site; run the balancing by hand")
    row = {"queue_id": new_id, "site_id": n["site_id"], "cluster_id": int(split["cluster_id"].max()) + 1,
           "block_id": block, "fold": fold, "role": "test" if fold == TEST_FOLD else "development"}
    out = pd.concat([rest, pd.DataFrame([row])], ignore_index=True)[list(split.columns)]
    assert out.groupby("cluster_id")["fold"].nunique().max() == 1
    prev = file_hash(split_file)
    log = pd.DataFrame([{"timestamp_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                         "reason": reason, "previous_file_sha256": prev}])
    log.to_csv(force_log, mode="a", header=not Path(force_log).exists(), index=False)
    out.to_parquet(split_file, index=False)
    full = out.merge(pd.DataFrame({"queue_id": q["queue_id"], "bundesland": q["bundesland"]}), on="queue_id")
    t = tech.reindex(out["queue_id"]).to_numpy()
    full["n_battery"] = (t == "battery").astype(int)
    full["n_pv"] = (t == "ground_pv").astype(int)
    full["n_negative"] = pd.isna(t).astype(int)
    full["n_open_dop"] = full["bundesland"].isin(open_dop_states()).astype(int)
    summarise(full, file_hash(split_file), content_hash(full), seed).to_csv(summary, index=False)
    return fold


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--force", action="store_true", help="overwrite an existing assignment (logged)")
    ap.add_argument("--reason", default="", help="required with --force")
    a = ap.parse_args(argv)
    try:
        summ = build(force=a.force, reason=a.reason)
    except FileExistsError as e:
        print(e, file=sys.stderr)
        return 2
    print(summ.drop(columns=["file_sha256", "content_sha256", "split_file"]).to_string(index=False))
    print("file_sha256", summ["file_sha256"].iloc[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
