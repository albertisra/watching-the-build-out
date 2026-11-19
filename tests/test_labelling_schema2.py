"""Label schema v2: per-technology events, two passes, immutability, blindness, MV DOP hidden."""

from __future__ import annotations

import ast
import csv

import pandas as pd
import pytest

from bo import paths
from bo.imagery import dop as dopmod
from bo.labelling import blind, chipview, exposure, labels, review, schema
from bo.labelling.schema import phase_sequence

MONTHS = [f"2020-{m:02d}" for m in range(1, 13)]


def ev(tech, c, s, e, **extra):
    d = {f"{tech}_clear_month": c, f"{tech}_struct_month": s, f"{tech}_complete_month": e}
    d.update({f"{tech}_{k}": v for k, v in extra.items()})
    return d


def pass1(tmp, **o):
    k = {"queue_id": "L1-1", "labeller_id": "a", "site_class": "battery", "confidence": 2,
         "events": ev("bat", "2020-03", "2020-05", "2020-09"), "directory": tmp}
    k.update(o)
    return labels.append_label(**k)


def test_round_trip_all_fields(tmp_path):
    events = {**ev("bat", "2020-03", "2020-05", "2020-09", clear_earliest="2020-02", clear_latest="2020-04"),
              **ev("pv", "before_series", "not_visible", "after_series")}
    lid = pass1(tmp_path, site_class="battery+PV", colocated="none", events=events, note="a\nb",
                registry_date_exposed=True, stratum="positive_battery")
    r = labels.read_labels(tmp_path).iloc[0]
    assert r.label_id == lid and r.schema_version == schema.SCHEMA_VERSION and r.pass_id == "pre_dop"
    for k, v in events.items():
        assert r[k] == v
    assert r.bat_complete_latest == "" and r.registry_date_exposed
    assert r.start_month == "2020-03" and r.complete_month == "2020-09"
    assert r.note == "a b"
    with open(tmp_path / labels.LABELS_FILE, newline="") as fh:
        raw = list(csv.DictReader(fh))
    assert list(raw[0]) == schema.LABEL_COLUMNS


def test_validation_rules(tmp_path):
    with pytest.raises(ValueError):  # undetermined event in a positive class
        pass1(tmp_path, events=ev("bat", "2020-03", "", "2020-09"))
    with pytest.raises(ValueError):  # order
        pass1(tmp_path, events=ev("bat", "2020-06", "2020-05", "2020-09"))
    with pytest.raises(ValueError):  # range must bracket the month
        pass1(tmp_path, events=ev("bat", "2020-03", "2020-05", "2020-09", clear_earliest="2020-04"))
    with pytest.raises(ValueError):  # after_series then a dated event
        pass1(tmp_path, events=ev("bat", "after_series", "2020-05", "2020-09"))
    with pytest.raises(ValueError):
        pass1(tmp_path, colocated="x")
    pass1(tmp_path, site_class="none", events={})  # negatives need no dates
    # a technology that is not active is dropped, not stored
    pass1(tmp_path, queue_id="L1-2", events={**ev("bat", "2020-03", "2020-05", "2020-09"),
                                              **ev("pv", "2020-01", "2020-02", "2020-03")})
    r = labels.read_labels(tmp_path).set_index("queue_id").loc["L1-2"]
    assert r.pv_clear_month == ""


def test_colocated_technology_gets_its_own_dates(tmp_path):
    with pytest.raises(ValueError):
        pass1(tmp_path, colocated="pv")  # visible PV needs PV dates
    pass1(tmp_path, colocated="pv", events={**ev("bat", "2020-03", "2020-05", "2020-09"),
                                            **ev("pv", "2019-01", "2019-02", "2019-06")})
    r = labels.read_labels(tmp_path).iloc[0]
    assert r.pv_struct_month == "2019-02" and r.colocated == "pv"


def test_phase_sequence_four_states():
    row = ev("bat", "2020-03", "2020-05", "2020-09")
    seq = phase_sequence(row, "bat", MONTHS)
    assert seq == [0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]
    # no clearing phase visible: Cl is absent, U jumps to UC
    seq = phase_sequence(ev("bat", "not_visible", "2020-05", "2020-09"), "bat", MONTHS)
    assert 1 not in seq and seq[4] == 2
    # before series complete; after series nothing
    assert set(phase_sequence(ev("bat", "before_series", "before_series", "before_series"), "bat", MONTHS)) == {3}
    assert set(phase_sequence(ev("bat", "after_series", "after_series", "after_series"), "bat", MONTHS)) == {0}
    # undetermined event: months it controls are -1; a later event already passed decides the rest
    seq = phase_sequence({"bat_clear_month": "2020-03", "bat_struct_month": "", "bat_complete_month": "2020-09"},
                         "bat", MONTHS)
    assert seq[0] == 0 and seq[3] == -1 and seq[10] == 3
    # brackets: months inside the earliest..latest range are ambiguous
    row = ev("bat", "2020-03", "2020-05", "2020-09", struct_earliest="2020-04", struct_latest="2020-06")
    assert phase_sequence(row, "bat", MONTHS, use_brackets=True)[3:5] == [-1, -1]
    assert phase_sequence(row, "bat", MONTHS)[3] == 1


def test_phase_sequence_feeds_hmm_fit():
    import numpy as np

    from bo.timeline import hmm

    z = np.array(phase_sequence(ev("pv", "2020-03", "2020-05", "2020-09"), "pv", MONTHS))
    x = np.linspace(0, 1, 12)[:, None] + 0.0 * z[:, None]
    p = hmm.fit_supervised([x], [z])
    assert p.mu.shape[0] == 4 and (p.h > 0).all()


def test_pass1_immutable_and_pass2_separate(tmp_path):
    lid = pass1(tmp_path)
    before = (tmp_path / labels.LABELS_FILE).read_bytes()
    with pytest.raises(ValueError):
        labels.void_label(lid, queue_id="L1-1", labeller_id="a", directory=tmp_path)
    assert (tmp_path / labels.LABELS_FILE).read_bytes() == before
    with pytest.raises(ValueError):  # pass 2 needs pass 1 of the same item
        labels.append_dop_review(pass1_label_id="nope", queue_id="L1-1", labeller_id="a", site_class="battery",
                                 confidence=2, dop_identity="confirms", dop_footprint="matches",
                                 events=ev("bat", "2020-03", "2020-05", "2020-09"), directory=tmp_path)
    p2 = labels.append_dop_review(
        pass1_label_id=lid, queue_id="L1-1", labeller_id="a", site_class="battery+PV", confidence=3,
        dop_identity="confirms", dop_footprint="differs", directory=tmp_path,
        events={**ev("bat", "2020-04", "2020-05", "2020-09"), **ev("pv", "2020-01", "2020-02", "2020-03")})
    after = (tmp_path / labels.LABELS_FILE).read_bytes()
    assert after.startswith(before)  # nothing earlier rewritten
    both = labels.read_two_pass(tmp_path).iloc[0]
    assert both.pre_dop_site_class == "battery" and both.post_dop_site_class == "battery+PV"
    assert both.pre_dop_bat_clear_month == "2020-03" and both.post_dop_bat_clear_month == "2020-04"
    assert both.dop_identity == "confirms" and both.post_dop_label_id == p2
    # pass-1 reader is unaffected by pass 2
    assert labels.read_labels(tmp_path).iloc[0].site_class == "battery"
    # pass 2 can be undone; pass 1 still stands
    labels.void_label(p2, queue_id="L1-1", labeller_id="a", directory=tmp_path)
    assert labels.read_two_pass(tmp_path).iloc[0].post_dop_label_id == ""
    assert not labels.has_dop_review("L1-1", "a", tmp_path)


def test_reveal_locks_item(tmp_path):
    lid = pass1(tmp_path)
    with pytest.raises(ValueError):  # nothing committed for another item
        review.lock_and_reveal("L1-9", "a", {"stratum": "x"}, round_queue_ids=set(), directory=tmp_path)
    with pytest.raises(ValueError):  # DOP pass still pending
        review.lock_and_reveal("L1-1", "a", {"stratum": "x"}, round_queue_ids=set(), dop_pending=True, directory=tmp_path)
    facts = review.lock_and_reveal("L1-1", "a", {"stratum": "random_negative"}, round_queue_ids=set(), directory=tmp_path)
    assert facts["queue stratum"] == "random_negative"
    with pytest.raises(labels.LockedError):
        pass1(tmp_path)
    with pytest.raises(labels.LockedError):
        labels.append_dop_review(pass1_label_id=lid, queue_id="L1-1", labeller_id="a", site_class="battery",
                                 confidence=2, dop_identity="confirms", dop_footprint="matches",
                                 events=ev("bat", "2020-03", "2020-05", "2020-09"), directory=tmp_path)


def test_no_registry_field_reachable_in_session_view():
    q = pd.DataFrame({"queue_id": ["L1-1"], "site_id": ["BESS-X"], "stratum": ["positive_battery"],
                      "lat": [1.0], "lon": [2.0], "bundesland": ["Hessen"], "landkreis": ["K"],
                      "osm_category": ["c"], "worldcover_class": ["w"]})
    cols = set(blind.session_columns(q).columns)
    assert cols == {"queue_id", "bundesland"}
    assert not hasattr(blind, "reveal_facts") and not hasattr(blind, "paths")
    blind.assert_blind(blind.view_payload(0, 5))
    # the labelling app never imports the review module or the reveal log, and never reads registry tables
    src = (paths.REPO_ROOT / "app" / "label_app.py").read_text()
    imported = {n.module or "" for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import) for a in n.names}
    assert not any("review" in m or "registry" in m for m in imported)
    for forbidden in ("reveal_facts", "log_reveal", "revealed_before", "registry_sites", "power_kw", "capacity",
                      "commission", "reg_status", "st.json("):
        assert forbidden not in src, forbidden
    # stratum is only stored, never displayed: it must not appear inside any st.* display call
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and getattr(node.func.value, "id", "") in ("st",) and node.func.attr in (
                    "write", "caption", "markdown", "json", "text", "info", "success", "error", "warning",
                    "subheader", "title", "dataframe", "table"):
            assert "stratum" not in ast.unparse(node)


def test_mv_dop_hidden(tmp_path, monkeypatch):
    assert "Mecklenburg-Vorpommern" in dopmod.restricted_states()
    assert not blind.dop_allowed("Mecklenburg-Vorpommern") and blind.dop_allowed("Bayern")
    # restricted state: nothing is looked up, even for an id that has a chip in the index
    monkeypatch.setattr(chipview, "_dop_index", lambda: (_ for _ in ()).throw(AssertionError("index read")))
    assert chipview.dop_for_site("L1-0001", "Mecklenburg-Vorpommern") == (None, None)
    assert chipview.dop_status("L1-0001", "Mecklenburg-Vorpommern") == "restricted"


def test_dop_status_for_open_state(monkeypatch):
    idx = pd.DataFrame({"chip_ok": [True, False], "chip_path": ["README.md", "x.tif"]}, index=["A", "B"])
    monkeypatch.setattr(chipview, "_dop_index", lambda: idx)
    assert chipview.dop_status("A", "Bayern") == "chip"
    assert chipview.dop_status("B", "Bayern") == "none" and chipview.dop_status("Z", "Bayern") == "none"


def test_exposure_matching_and_file():
    pilot = pd.DataFrame({"pilot_id": ["P1", "P2", "P3"], "site_key": ["K1", "K2", "K3"],
                          "lat": [50.0, 51.0, 52.0], "lon": [10.0, 11.0, 12.0]})
    q = pd.DataFrame({"queue_id": ["L1-1", "L1-2", "L1-3"], "site_id": ["K1", None, None],
                      "lat": [0.0, 51.0002, 60.0], "lon": [0.0, 11.0, 12.0]})
    m = exposure.match_to_queue(pilot, q)
    assert dict(zip(m.pilot_id, m.queue_id)) == {"P1": "L1-1", "P2": "L1-2"}
    ids = exposure.load_exposed_ids()
    assert ids and all(i.startswith("L1-") for i in ids)


def test_blind_relabel_never_replaces_first_label(tmp_path):
    first = pass1(tmp_path)
    pass1(tmp_path, is_relabel=True, events=ev("bat", "2020-04", "2020-06", "2020-10"))
    r = labels.read_labels(tmp_path)
    assert len(r) == 1 and r.iloc[0].label_id == first
    assert labels.read_two_pass(tmp_path).iloc[0].pre_dop_label_id == first
    assert labels.effective_rows(labels.read_all_rows(tmp_path))["is_relabel"].sum() == 1


# ---------------------------------------------------------------------------------- schema 3 follow-ups
def test_event_confidence_defaults_to_item_confidence(tmp_path):
    events = {**ev("bat", "2020-03", "2020-05", "2020-09"), "bat_struct_conf": "3"}
    pass1(tmp_path, confidence=2, events=events)
    r = labels.read_labels(tmp_path).iloc[0]
    assert (r.bat_clear_conf, r.bat_struct_conf, r.bat_complete_conf) == ("2", "3", "2")
    assert r.pv_clear_conf == "" and r.confidence == "2" and r.schema_version == "3"
    with pytest.raises(ValueError):
        pass1(tmp_path, queue_id="L1-2", events={**events, "bat_clear_conf": "4"})


def test_second_pass1_row_rejected_but_blind_relabel_allowed(tmp_path):
    pass1(tmp_path)
    with pytest.raises(labels.DuplicatePass1Error, match="pass 1 is final"):
        pass1(tmp_path)
    pass1(tmp_path, labeller_id="b")  # another labeller is fine
    pass1(tmp_path, is_relabel=True)
    assert len(labels.read_labels(tmp_path)) == 2


def test_coord_coarse_flag_stored(tmp_path):
    pass1(tmp_path, coord_coarse=True)
    pass1(tmp_path, queue_id="L1-2")
    r = labels.read_labels(tmp_path).set_index("queue_id")
    assert bool(r.loc["L1-1", "coord_coarse"]) and not bool(r.loc["L1-2", "coord_coarse"])
    assert bool(labels.read_two_pass(tmp_path).set_index("queue_id").loc["L1-1", "pre_dop_coord_coarse" if False else "coord_coarse"])
    assert "coord_coarse" not in blind.session_columns(pd.DataFrame(
        {"queue_id": ["x"], "stratum": ["pilot"], "bundesland": ["Bayern"], "coord_coarse": [True]})).columns
    assert exposure.load_coarse_ids() and "L1-0138" in exposure.load_coarse_ids()
    assert "L1-0025" not in exposure.load_coarse_ids()  # dp3


def test_exposure_radius_uses_coordinate_uncertainty():
    pilot = pd.DataFrame({"pilot_id": ["P1", "P2"], "site_key": ["K1", "K2"], "lat": [50.0, 51.0], "lon": [10.0, 11.0]})
    # about 55 m and 400 m north of the pilot points
    q = pd.DataFrame({"queue_id": ["L1-1", "L1-2"], "site_id": [None, None],
                      "lat": [50.0 + 55 / 111195, 51.0 + 400 / 111195], "lon": [10.0, 11.0]})
    assert set(exposure.match_to_queue(pilot, q).queue_id) == {"L1-1"}
    m = exposure.match_to_queue(pilot, q, unc_m={"L1-2": 500.0})
    assert set(m.queue_id) == {"L1-1", "L1-2"}
    assert "L1-0159" in exposure.load_exposed_ids()


def test_review_locked_during_open_round(tmp_path):
    pass1(tmp_path)
    args = ("L1-1", "a", {"stratum": "x"})
    with pytest.raises(review.RoundOpenError):
        review.lock_and_reveal(*args, round_queue_ids={"L1-1", "L1-2"}, directory=tmp_path)
    assert not labels.read_reveals(tmp_path).shape[0]
    review.lock_and_reveal(*args, round_queue_ids={"L1-1", "L1-2"}, allow_open_round=True, directory=tmp_path)
    assert len(pd.read_csv(tmp_path / labels.UNLOCKS_FILE)) == 1 and len(labels.read_reveals(tmp_path)) == 1


def test_readers_work_on_an_empty_label_folder(tmp_path):
    r = labels.read_labels(tmp_path, "author")
    assert len(r) == 0 and "labeller_id" in r.columns and "queue_id" in r.columns
    assert len(labels.read_two_pass(tmp_path, "author")) == 0


def test_stratum_looked_up_at_write_time_and_dop_seen_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(labels, "_STRATA_MAP", {"L1-1": "hard_negative"})
    lid = pass1(tmp_path)
    assert labels.read_labels(tmp_path).iloc[0].stratum == "hard_negative"
    labels.append_dop_review(pass1_label_id=lid, queue_id="L1-1", labeller_id="a", site_class="battery",
                             confidence=2, events=ev("bat", "2020-03", "2020-05", "2020-09"),
                             dop_identity="confirms", dop_footprint="matches", directory=tmp_path)
    pass1(tmp_path, queue_id="L1-2")
    pass1(tmp_path, queue_id="L1-2", is_relabel=True)  # DOP never shown for L1-2
    pass1(tmp_path, queue_id="L1-1", is_relabel=True)  # DOP was shown in pass 2
    r = labels.effective_rows(labels.read_all_rows(tmp_path))
    r = r[r["is_relabel"]].set_index("queue_id")
    assert not r.loc["L1-2", "relabel_after_dop_seen"] and r.loc["L1-1", "relabel_after_dop_seen"]
    from bo.labelling import agreement
    split = agreement.agreement_by_dop_exposure(labels.effective_rows(labels.read_all_rows(tmp_path)))
    assert split["all"]["n_pairs"] == 2 and split["sentinel_only_repeat"]["n_pairs"] == 1
    assert split["after_dop_seen"]["n_pairs"] == 1


def test_view_file_is_blind(tmp_path):
    from bo.data import queue as dq

    q = pd.DataFrame({"queue_id": ["L1-1", "L1-2"], "site_id": ["BESS-X", None], "stratum": ["pilot", "hard_negative"],
                      "lat": [1.0, 2.0], "lon": [3.0, 4.0], "bundesland": ["Hessen", "Bayern"],
                      "landkreis": ["K", None], "osm_category": [None, "c"], "worldcover_class": [None, "w"]})
    q.to_parquet(tmp_path / "q.parquet")
    pd.DataFrame({"site_id": ["BESS-X", "L1-2"], "chip_path": ["a", "b"], "chip_ok": [True, True]}).to_parquet(tmp_path / "d.parquet")
    dq.write_view(tmp_path / "q.parquet", tmp_path / "v.parquet", tmp_path / "d.parquet", tmp_path / "dv.parquet")
    v = pd.read_parquet(tmp_path / "v.parquet")
    assert list(v.columns) == ["queue_id", "lat", "lon", "bundesland"] and v["queue_id"].tolist() == ["L1-1", "L1-2"]
    dv = pd.read_parquet(tmp_path / "dv.parquet")
    assert "site_id" not in dv and set(dv["queue_id"]) == {"L1-1", "L1-2"}
