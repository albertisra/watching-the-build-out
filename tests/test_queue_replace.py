"""Replacement of queue item L1-0012 by L1-0411 (author decision 2026-11-19)."""

import pandas as pd

from bo import paths
from bo.data import queue as Q
from bo.timeline import splits as S


def test_queue_consistent_after_replacement():
    q, s = pd.read_parquet(Q.QUEUE), pd.read_parquet(Q.STRATA)
    sp = pd.read_parquet(S.SPLIT_FILE)
    assert len(q) == 410 and q.queue_id.is_unique
    assert "L1-0012" not in set(q.queue_id) and "L1-0411" in set(q.queue_id)
    assert set(q.queue_id) == set(s.queue_id) == set(sp.queue_id)
    assert sp.groupby("cluster_id")["fold"].nunique().max() == 1


def test_replacement_logged_and_precision_ok():
    log = pd.read_csv(paths.RESULTS / "labels" / "queue_round1_replacements.csv")
    assert {"L1-0012"} <= set(log.old_queue_id) and (log.seed == paths.SEED).all()
    sid = pd.read_parquet(Q.QUEUE).set_index("queue_id").loc["L1-0411", "site_id"]
    reg = pd.read_parquet(Q.SITES).set_index("site_id")
    assert reg.loc[sid, "coord_precision_class"] in ("dp4plus", "dp3")
