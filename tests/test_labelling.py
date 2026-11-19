"""Non-UI logic of the labelling app: queue, blind subset, append-only labels, agreement, blindness."""

import numpy as np
import pandas as pd
import pytest

from bo import paths
from bo.labelling import agreement, blind, labels, queue, review
from bo.labelling.schema import validate_label


def make_queue(n=40):
    strata = ["positive_battery", "positive_pv", "hard_negative", "random_negative"]
    return pd.DataFrame({
        "queue_id": [f"S{i:03d}" for i in range(n)],
        "stratum": [strata[i % 4] for i in range(n)], "lat": 50.0, "lon": 10.0, "bundesland": "Hessen"})


# ---- queue
def test_order_reproducible_and_input_order_independent():
    q = make_queue()
    a = queue.order_queue(q, paths.SEED)
    b = queue.order_queue(q.sample(frac=1, random_state=1), paths.SEED)
    assert a["queue_id"].tolist() == b["queue_id"].tolist()
    assert a["queue_id"].tolist() != sorted(a["queue_id"])  # actually shuffled
    assert a["queue_id"].tolist() != queue.order_queue(q, paths.SEED + 1)["queue_id"].tolist()


def test_validate_queue_rejects_bad_input():
    q = make_queue()
    with pytest.raises(ValueError):
        queue.validate_queue(q.drop(columns=["lat"]))
    with pytest.raises(ValueError):
        queue.validate_queue(q.assign(stratum="registry_class"))
    with pytest.raises(ValueError):
        queue.validate_queue(pd.concat([q, q.iloc[:1]]))


def test_relabel_subset_size_seed_and_reveal_exclusion():
    labelled = {f"S{i:03d}" for i in range(30)}
    revealed = {"S001", "S002", "S003"}
    sel = queue.select_relabel(labelled, revealed, 0.10, paths.SEED)
    assert len(sel) == 3  # ceil(0.1 * 27)
    assert not set(sel) & revealed
    assert sel == queue.select_relabel(labelled, revealed, 0.10, paths.SEED)
    assert sel == queue.select_relabel(sorted(labelled, reverse=True), revealed, 0.10, paths.SEED)
    assert sel != queue.select_relabel(labelled, revealed, 0.10, paths.SEED + 1)
    assert queue.select_relabel(set(), set()) == []


def test_session_queue_inserts_relabels_late_without_duplicates():
    q = make_queue(60)
    labelled = {f"S{i:03d}" for i in range(20)}
    sq = queue.build_session_queue(q, labelled, set(), set(), 0.10, 10, paths.SEED)
    rl = sq[sq["is_relabel"]]
    assert len(rl) == 2 and set(rl["queue_id"]) <= labelled
    assert (rl.index >= 10).all()
    assert sq["queue_id"].is_unique
    assert len(sq) == 40 + 2
    done = set(rl["queue_id"])
    again = queue.build_session_queue(q, labelled, done, set(), 0.10, 10, paths.SEED)
    assert not again["is_relabel"].any()  # already relabelled sites are not asked again


def test_revealed_site_never_in_relabel_set():
    q = make_queue(60)
    labelled = {f"S{i:03d}" for i in range(20)}
    first = queue.build_session_queue(q, labelled, set(), set(), 0.10, 10, paths.SEED)
    hit = set(first.loc[first["is_relabel"], "queue_id"])
    again = queue.build_session_queue(q, labelled, set(), hit, 0.10, 10, paths.SEED)
    assert not set(again.loc[again["is_relabel"], "queue_id"]) & hit


def test_test_queue_schema():
    q = queue.make_test_queue()
    queue.validate_queue(q)
    assert "stratum" not in q.columns and len(q) > 0


# ---- labels: append-only, latest wins, void
def ev(clear, struct, complete, tech="pv"):
    return {f"{tech}_clear_month": clear, f"{tech}_struct_month": struct, f"{tech}_complete_month": complete}


def kw(**o):
    d = {"queue_id": "S1", "labeller_id": "a", "site_class": "PV", "confidence": 2,
         "events": ev("2024-03", "2024-05", "2024-09")}
    d.update(o)
    return d


def test_append_only_and_duplicate_pass1_rejected(tmp_path):
    labels.append_label(**kw(), directory=tmp_path)
    f = tmp_path / labels.LABELS_FILE
    before = f.read_bytes()
    with pytest.raises(labels.DuplicatePass1Error):
        labels.append_label(**kw(site_class="battery", note="multi\nline",
                                 events=ev("2024-03", "2024-05", "2024-09", "bat")), directory=tmp_path)
    assert f.read_bytes() == before  # nothing written
    labels.append_label(**kw(queue_id="S2"), directory=tmp_path)
    labels.append_label(**kw(labeller_id="b", site_class="none"), directory=tmp_path)
    assert len(labels.read_labels(tmp_path)) == 3
    assert f.read_bytes().startswith(before)
    assert len(labels.read_all_rows(tmp_path)) == 3


def test_metadata_columns_and_validation(tmp_path):
    labels.append_label(**kw(queue_id="Q1", stratum="hard_negative", chip_stores="sh_v1;x"), directory=tmp_path)
    r = labels.read_labels(tmp_path).iloc[0]
    assert r.app_version and r.timestamp_utc.endswith("+00:00") and r.stratum == "hard_negative"
    with pytest.raises(ValueError):
        validate_label("solar", "", "", 2)
    with pytest.raises(ValueError):
        validate_label("PV", "2024-5", "", 2)
    with pytest.raises(ValueError):
        validate_label("PV", "2024-06", "2024-03", 2)
    validate_label("PV", "before_series", "after_series", 3)
    with pytest.raises(ValueError):
        validate_label("PV", "", "", 4)


def test_reveals_logged(tmp_path):
    labels.log_reveal("S1", "a", tmp_path)
    labels.log_reveal("S2", "b", tmp_path)
    assert labels.revealed_sites(tmp_path) == {"S1", "S2"}
    assert labels.revealed_sites(tmp_path, "a") == {"S1"}
    assert labels.read_reveals(tmp_path).iloc[0].timestamp_utc


# ---- agreement
def test_kappa_known_values():
    assert agreement.cohens_kappa(list("aabb"), list("aabb")) == 1.0
    # po = 0.5, pe = 0.5 -> 0
    assert agreement.cohens_kappa(list("aabb"), list("abab")) == pytest.approx(0.0)
    # textbook: 20/50 yes-yes, 15 no-no, 5+10 off -> po 0.7, pe 0.5 -> 0.4
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert agreement.cohens_kappa(a, b) == pytest.approx(0.4)
    assert np.isnan(agreement.cohens_kappa(["a", "a"], ["a", "a"]))
    assert np.isnan(agreement.cohens_kappa([], []))


def test_month_errors():
    r = agreement.month_errors(["2024-01", "2023-12", "before_series", "", "2024-05"],
                               ["2024-03", "2024-01", "before_series", "2024-02", "after_series"])
    assert r["n_dated_pairs"] == 2 and r["mean_abs_error_months"] == 1.5
    assert r["n_special_pairs"] == 3 and r["special_exact_match"] == pytest.approx(1 / 3)


def test_agreement_uses_first_label_and_first_relabel(tmp_path):
    for s, c1, c2 in (("S1", "PV", "PV"), ("S2", "battery", "none"), ("S3", "none", "none"), ("S4", "PV", "PV")):
        labels.append_label(**kw(queue_id=s, site_class=c1, events=ev("2024-01", "2024-05", "2024-09", "bat" if c1 == "battery" else "pv") if c1 in ("PV", "battery") else {}),
                            directory=tmp_path)
    labels.append_label(**kw(queue_id="S1", site_class="PV", events=ev("2024-02", "2024-05", "2024-09"), is_relabel=True),
                        directory=tmp_path)
    labels.append_label(**kw(queue_id="S2", site_class="none", is_relabel=True), directory=tmp_path)
    labels.append_label(**kw(queue_id="S3", site_class="none", is_relabel=True), directory=tmp_path)
    res = agreement.agreement(labels.effective_rows(labels.read_all_rows(tmp_path)))
    assert res["n_pairs"] == 3 and res["class_agreement"] == pytest.approx(2 / 3)
    assert res["start"]["n_dated_pairs"] == 1 and res["start"]["mean_abs_error_months"] == pytest.approx(1.0)
    assert res["events"]["pv_struct_month"]["mean_abs_error_months"] == 0.0
    assert agreement.agreement(pd.DataFrame(columns=labels.LABEL_COLUMNS).assign(is_relabel=False))["n_pairs"] == 0


# ---- blindness
def test_view_payload_has_no_registry_fields():
    p = blind.view_payload(3, 40)
    blind.assert_blind(p)
    assert set(p) == {"alias", "position", "n_total"}
    assert "Q" not in p["alias"] and "S0" not in p["alias"]


@pytest.mark.parametrize("key", ["reg_power_kw", "reg_commissioning_date", "capacity_kw", "subtype", "status",
                                 "stratum", "queue_id", "site_id", "registry_key", "unit_ids", "model_prob", "lat", "bundesland"])
def test_forbidden_keys_raise(key):
    with pytest.raises(ValueError):
        blind.assert_blind({key: 1})


def test_registry_row_is_filtered_out_of_view():
    pilot = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet").iloc[0].to_dict()
    # a full registry row must never pass the whitelist
    with pytest.raises(ValueError):
        blind.assert_blind(pilot)
    clean = {k: v for k, v in pilot.items() if not blind.is_forbidden(k)}
    assert clean == {}


def test_dop_view_dates():
    d = blind.dop_view({"date_type": "day", "flight_date": "2025-04-16", "licence": "x"})
    assert "2025-04-16" in d["date_text"] and not d["internal_only"]
    p = blind.dop_view({"date_type": "production_only", "flight_date": None, "production_date": "2025-04-16"})
    assert "2025" not in p["date_text"]
    y = blind.dop_view({"date_type": "year_edition", "flight_year": 2023.0})
    assert "2023" in y["date_text"] and "unknown" in y["date_text"]
    assert blind.dop_view({"date_type": "none"})["date_text"].startswith("no acquisition")
    assert blind.dop_view({"date_type": "day", "flight_date": "2024-01-01", "use_restriction": "m-v"})["internal_only"]
    assert not any(blind.is_forbidden(k) for k in blind.dop_view({"date_type": "day"}))


def test_reveal_facts_only_via_reveal():
    import pandas as pd

    q = pd.read_parquet(paths.PROCESSED / "labels" / "queue_round1.parquet")
    row = q[q["site_id"].notna()].iloc[0].to_dict()
    f = review.reveal_facts(row["queue_id"], row)
    assert any("commissioning" in k for k in f)


# ---- round-1 queue wiring
def test_session_queue_keeps_file_order():
    q = make_queue(30).sample(frac=1, random_state=3).reset_index(drop=True)
    sq = queue.build_session_queue(q, set(), set(), set(), 0.10, 10, paths.SEED)
    assert sq["queue_id"].tolist() == q["queue_id"].tolist()


def test_queue_without_registry_key_validates():
    q = make_queue(8).assign(site_id=[None, "BESS-X"] * 4, stratum="pilot")
    queue.validate_queue(q)  # negatives have no registry key; queue_id is the key


def test_dop_index_joined_through_queue():
    from bo.labelling import chipview

    q = pd.DataFrame({"queue_id": ["L1-1", "L1-2"], "site_id": ["PV-9", None]})
    dop = pd.DataFrame({"site_id": ["PV-9", "L1-2"], "chip_path": ["a.tif", "b.tif"]})
    idx = chipview.build_dop_index(dop, q)
    assert idx.loc["L1-1", "chip_path"] == "a.tif" and idx.loc["L1-2", "chip_path"] == "b.tif"


def test_reveal_facts_from_queue_row_without_registry_key():
    f = review.reveal_facts("L1-2", {"stratum": "hard_negative", "site_id": None, "osm_category": "greenhouse",
                                    "bundesland": "Hessen"})
    assert f["queue stratum"] == "hard_negative" and f["OSM category"] == "greenhouse"
    assert "registry key" not in f


def test_app_never_reads_strata_file_or_shows_ids():
    import pathlib

    # only the label storage (stratum lookup at write time) touches the strata file; the app and the
    # other labelling modules never do, and the app never reads the full queue file
    mods = [p for p in (paths.REPO_ROOT / "src/bo/labelling").glob("*.py") if p.name not in ("labels.py", "queue.py")]
    src = "".join(p.read_text() for p in mods) + (paths.REPO_ROOT / "app/label_app.py").read_text()
    assert "queue_round1_strata" not in src
    assert "queue_round1.parquet" not in (paths.REPO_ROOT / "app/label_app.py").read_text()
    assert 'CFG["queue"]["file"]' not in (paths.REPO_ROOT / "app/label_app.py").read_text()
    assert pathlib.Path(paths.REPO_ROOT / "app/label_app.py").read_text().count('payload["alias"]') == 1
