"""Post-labelling review mode (`make review`). Separate from the labelling session.

Lists items that already carry a committed label. Revealing registry facts for an item first logs the reveal,
which locks that item's labels for this labeller (no further label rows are accepted) and removes the item
from the blind relabel set. Registry values are observed; they are not shown anywhere in `make label`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bo import paths
from bo.labelling import chipview, labels, queue, review

st.set_page_config(page_title="Registry review (after labelling)", layout="wide")
CFG = queue.load_config()
st.title("Registry review, after labelling")
ALLOW = bool(CFG.get("review", {}).get("allow_during_open_round", False))
st.warning("Revealing locks the labels of an item. Items revealed here cannot be relabelled blind and are "
           "flagged `revealed_before`. Do not use this while labelling.")
who = st.text_input("Labeller ID", "author")
q = queue.load_queue(paths.REPO_ROOT / CFG["queue"]["file"]).set_index("queue_id", drop=False)
n_open = len(review.open_items(q.index, who))
if n_open and not ALLOW:
    st.error(f"Review is locked: {n_open} items of this round are still unlabelled. Finish labelling first. "
             "(Override: [review] allow_during_open_round in app/config/labelling.toml; every use is logged.)")
    st.stop()
if n_open:
    st.warning(f"Override active, {n_open} items unlabelled. Every item revealed now becomes non-blind and is "
               "removed from the blind relabel set; each reveal is logged in review_unlocks.csv.")
mine = labels.read_two_pass(labeller_id=who)
done = set(labels.revealed_sites(labeller_id=who))
todo = sorted(set(mine["queue_id"]) - done)
st.write(f"labelled: {len(mine)}, already reviewed: {len(done)}")
item = st.selectbox("Labelled item", todo)
if item and st.button("Lock labels and reveal registry facts"):
    row = q.loc[item]
    pending = chipview.dop_status(item, row.get("bundesland")) == "chip"
    pending = pending and not bool(row.get("is_relabel", False))
    try:
        facts = review.lock_and_reveal(item, who, row.to_dict(), round_queue_ids=set(q.index),
                                       allow_open_round=ALLOW, dop_pending=pending)
        st.json(facts)
        l = mine[mine["queue_id"] == item].iloc[0]
        st.dataframe(pd.DataFrame({"your pass-1 class": [l["pre_dop_site_class"]]}))
    except ValueError as e:
        st.error(str(e))
