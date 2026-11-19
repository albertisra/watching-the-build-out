"""Streamlit labelling app. Start with `make label`. Logic lives in src/bo/labelling/ (tested).

Blind: this file only receives `view_payload` (position text), the session columns (item key, stratum for
storage, federal state to gate DOP) and image arrays. It never imports `bo.labelling.review` (registry facts);
those exist only in the separate review mode (`make review`) after the labels are locked.

Two passes per item. Pass 1 shows Sentinel-1/2 only; Enter writes the answers immutably. Pass 2 (only where a
DOP chip exists and the state is not use-restricted) shows the DOP chip and records identity and footprint
confirmation plus revised answers as separate rows.
"""

from __future__ import annotations

import streamlit as st

from bo import paths
from bo.labelling import APP_VERSION, chipview, exposure, labels, queue
from bo.labelling.blind import session_columns, view_payload
from bo.labelling.schema import (
    AFTER_SERIES,
    BEFORE_SERIES,
    CLASS_KEYS,
    COLOCATED,
    CONF_COLUMNS,
    DOP_FOOTPRINT,
    EVENTS,
    NOT_VISIBLE,
    active_techs,
    empty_events,
    normalise_events,
)

st.set_page_config(page_title="Labelling", layout="wide")

CFG = queue.load_config()
WIDTH = CFG["display"]["window_months"]
TECH_NAME = {"bat": "battery", "pv": "PV"}
EVENT_NAME = {"clear": "clearing / ground works", "struct": "structures", "complete": "complete"}
EVENT_TAG = {"clear": "C", "struct": "U", "complete": "E"}

KEYS_JS = """
<script>
const P = window.parent;
if (P.__labelKeys) P.document.removeEventListener('keydown', P.__labelKeys, true);
P.__labelKeys = function(e) {
  const t = e.target; const tag = (t && t.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || e.ctrlKey || e.metaKey || e.altKey) return;
  const map = {'ArrowLeft':'[left]','ArrowRight':'[right]','ArrowUp':'[up]','ArrowDown':'[down]','Enter':'[Enter]'};
  const k = map[e.key] || '[' + e.key + ']';
  const btns = Array.from(P.document.querySelectorAll('button'));
  const b = btns.find(x => x.innerText.trim().startsWith(k + ' '));
  if (b) { e.preventDefault(); b.click(); }
};
P.document.addEventListener('keydown', P.__labelKeys, true);
</script>
"""

def months_label(i):
    return ss.prep.months[i]


ss = st.session_state


# ------------------------------------------------------------------ session setup
def init_session():
    ss.labeller = ss.get("labeller", "author")
    qpath = paths.REPO_ROOT / CFG["queue"]["view_file"]
    if qpath.exists():
        q = queue.load_view(qpath)
        ss.queue_source = "round 1 queue"
    else:
        tpath = paths.REPO_ROOT / CFG["queue"]["test_file"]
        if not tpath.exists():
            tpath.parent.mkdir(parents=True, exist_ok=True)
            queue.make_test_queue(CFG).to_parquet(tpath)
        q = queue.load_queue(tpath)
        ss.queue_source = "DEVELOPMENT queue from pilot tables (not the research queue)"

    def has_chips(s):
        try:
            chipview.resolve_roots(s)
            return True
        except FileNotFoundError:
            return False

    q = q[q["queue_id"].map(has_chips)]
    ss.full_queue = session_columns(q)  # only queue_id and bundesland are kept
    ss.exposed = exposure.load_exposed_ids(paths.REPO_ROOT / CFG["queue"]["exposed_ids_file"])
    ss.coarse = exposure.load_coarse_ids(paths.REPO_ROOT / CFG["queue"]["coarse_coords_file"])  # stored, never shown
    rebuild_queue()


def rebuild_queue():
    who = ss.labeller
    mine = labels.read_labels(labeller_id=who)
    rows = labels.effective_rows(labels.read_all_rows())
    rows = rows[rows["labeller_id"] == who]
    relabel_done = set(rows.loc[rows["is_relabel"], "queue_id"])
    ss.queue = queue.build_session_queue(
        ss.full_queue, set(mine["queue_id"]), relabel_done, labels.revealed_sites(labeller_id=who),
        CFG["queue"]["relabel_fraction"], CFG["queue"]["relabel_min_position"], paths.SEED)
    ss.pos = 0
    ss.stage = 1
    ss.p1 = None
    reset_form()


def reset_form():
    ss.cls, ss.coloc, ss.conf, ss.note = None, "none", 2, ""
    ss.ev = empty_events()
    ss.track, ss.focus = "bat", "clear"
    ss.dop_id, ss.dop_fp = None, "matches"
    ss.cursor = None


# ------------------------------------------------------------------ callbacks
def act():
    return active_techs(ss.cls or "", ss.coloc)


def cur_track():
    a = act()
    return ss.track if ss.track in a else (a[0] if a else None)


def set_cls(c):
    ss.cls = c
    a = act()
    ss.track = a[0] if a and ss.track not in a else ss.track


def cycle_coloc():
    ss.coloc = COLOCATED[(COLOCATED.index(ss.coloc) + 1) % len(COLOCATED)]


def toggle_track():
    a = act()
    if len(a) > 1:
        ss.track = a[(a.index(cur_track()) + 1) % len(a)]


def cycle_focus():
    ss.focus = EVENTS[(EVENTS.index(ss.focus) + 1) % len(EVENTS)]


def _set(field, value, event=None):
    t = cur_track()
    if t is None:
        ss.msg = ("error", "Choose a class (or a co-located technology) first.")
        return
    e = event or ss.focus
    ss.focus = e
    ss.ev[f"{t}_{e}_{field}"] = value
    if field == "month" and value not in (None, "") and not str(value)[:1].isdigit():
        ss.ev[f"{t}_{e}_earliest"] = ss.ev[f"{t}_{e}_latest"] = ""


def mark(event):
    _set("month", months_label(ss.cursor), event)


def mark_range(field):
    _set(field, months_label(ss.cursor))


def mark_special(value):
    _set("month", value)


def clear_focus():
    t = cur_track()
    if t:
        for f in ("month", "earliest", "latest"):
            ss.ev[f"{t}_{ss.focus}_{f}"] = ""


def clear_all():
    ss.ev = empty_events()


def fill_all(value):
    t = cur_track()
    if t is None:
        ss.msg = ("error", "Choose a class first.")
        return
    for e in EVENTS:
        ss.ev[f"{t}_{e}_month"] = value
        ss.ev[f"{t}_{e}_earliest"] = ss.ev[f"{t}_{e}_latest"] = ""


def move(d):
    ss.cursor = max(0, min(ss.prep.n - 1, ss.cursor + d))


def cycle_event_conf():
    """Focused event: item default (empty) -> 1 -> 2 -> 3 -> default."""
    t = cur_track()
    if t is None:
        ss.msg = ("error", "Choose a class first.")
        return
    k = f"{t}_{ss.focus}_conf"
    ss.ev[k] = {"": "1", "1": "2", "2": "3", "3": ""}[str(ss.ev.get(k, "") or "")]


def set_conf(c):
    ss.conf = c


def set_dop(identity, footprint=None):
    ss.dop_id = identity
    if footprint:
        ss.dop_fp = footprint


def cycle_fp():
    ss.dop_fp = DOP_FOOTPRINT[(DOP_FOOTPRINT.index(ss.dop_fp) + 1) % len(DOP_FOOTPRINT)]


def advance():
    ss.pos += 1
    ss.stage = 1
    ss.p1 = None
    reset_form()


def do_save():
    if ss.pos >= len(ss.queue):
        return
    if ss.cls is None:
        ss.msg = ("error", "Choose a class first (b p c o n u).")
        return
    row = ss.queue.iloc[ss.pos]
    q = row["queue_id"]
    ev = {**normalise_events(ss.ev, ss.cls, ss.coloc), **{c: ss.ev.get(c, "") for c in CONF_COLUMNS}}
    try:
        if ss.stage == 1:
            lid = labels.append_label(
                queue_id=q, labeller_id=ss.labeller, site_class=ss.cls, colocated=ss.coloc, events=ev,
                confidence=ss.conf, note=ss.note, is_relabel=bool(row["is_relabel"]),
                chip_stores=ss.chip_stores, registry_date_exposed=q in ss.exposed, coord_coarse=q in ss.coarse)
            status = chipview.dop_status(q, row.get("bundesland"))
            if status == "chip" and not row["is_relabel"]:
                ss.stage, ss.p1 = 2, {"label_id": lid}
                ss.dop_id, ss.dop_fp = None, "matches"
                ss.msg = ("ok", "Sentinel-only answers written (final). Now the DOP chip: confirm identity and footprint, "
                                "revise answers if needed.".strip())
            else:
                advance()
                ss.msg = ("ok", "Saved.")
        else:
            if ss.dop_id is None:
                ss.msg = ("error", "DOP identity: y confirms, k contradicts, q cannot tell.")
                return
            labels.append_dop_review(
                pass1_label_id=ss.p1["label_id"], queue_id=q, labeller_id=ss.labeller, site_class=ss.cls,
                colocated=ss.coloc, events=ev, confidence=ss.conf, note=ss.note, dop_identity=ss.dop_id,
                dop_footprint=ss.dop_fp, chip_stores=ss.dop_stores,
                registry_date_exposed=q in ss.exposed, coord_coarse=q in ss.coarse)
            advance()
            ss.msg = ("ok", "Saved.")
    except ValueError as e:
        ss.msg = ("error", str(e))


# ------------------------------------------------------------------ main
if "queue" not in ss:
    init_session()

with st.sidebar:
    st.text_input("Labeller ID", key="labeller", on_change=rebuild_queue)
    st.caption(f"app version {APP_VERSION}")
    st.caption(ss.queue_source)
    mine = labels.read_labels(labeller_id=ss.labeller)
    st.write(f"labelled by you: {len(mine)}")
    st.write(f"position: {min(ss.pos + 1, len(ss.queue))} of {len(ss.queue)}")
    st.markdown(
        "**Class** `b` battery `p` PV `c` battery+PV `o` other `n` none `u` unsure  \n"
        "**Co-located other technology visible** `w` cycles none, PV, battery, other  \n"
        "**Technology** `t` switches battery / PV (when both are active)  \n"
        "**Events** `s` clearing here, `d` structures here, `e` complete here  \n"
        "`f` cycles the focused event; `h` before series, `j` after series, `m` not visible (focused event)  \n"
        "`a` earliest, `l` latest here (optional range)  \n"
        "`0` all events before series, `9` all after series, `x` clear focused, `X` clear all  \n"
        "`1 2 3` item confidence, `v` cycles the focused event's own confidence (default: item confidence)  \n`left right` month, `up down` 12 months  \n"
        "`Enter` commit and next. **Pass 1 is final.** Pass 2 (DOP): `y` identity and footprint confirmed, "
        "`k` contradicts, `q` cannot tell, `i` footprint answer  \n"
        "Click out of the note box first; keys are off while typing.")
    st.caption("S2 flags: B = bright (snow, haze, thin cloud), D = cloud-probability disagreement. "
               "n = clear observations (median over the chip). All imagery is observed.")

st.iframe(KEYS_JS, height=1)  # our own static script, no user input

if ss.pos >= len(ss.queue):
    st.success("Queue finished.")
    st.stop()

row = ss.queue.iloc[ss.pos]
site = row["queue_id"]  # item key; never displayed
payload = view_payload(ss.pos, len(ss.queue))  # the only item data the view uses
try:
    prep, platform, store_names = chipview.load_site(site)
except (OSError, ValueError, KeyError) as e:  # missing or incompatible store
    st.error(f"Chips for this item cannot be loaded: {type(e).__name__}")
    st.stop()
ss.prep = prep
dop_state = chipview.dop_status(site, row.get("bundesland"))  # index lookup only; no image in pass 1
ss.chip_stores = f"{store_names};platform={platform};{prep.code_version};dop={dop_state}"
if ss.cursor is None:
    firsts = [i for i in range(prep.n) if prep.s2_count[i] > 0]  # first month with clear S2 observations
    ss.cursor = firsts[0] if firsts else 0  # the full series stays navigable
chipview.prefetch([ss.queue.iloc[j]["queue_id"] for j in range(ss.pos + 1, min(ss.pos + 3, len(ss.queue)))])

if "msg" in ss:
    kind, text = ss.pop("msg")
    (st.error if kind == "error" else st.success)(text)

# ---- header
h1, h2 = st.columns([2, 5])
h1.subheader(payload["alias"] + ("   |   pass 2: DOP" if ss.stage == 2 else "   |   pass 1: Sentinel only"))
h2.write(f"series: {prep.months[0]} to {prep.months[-1]}, platform **{platform}** "
         f"(S2 {'yes' if prep.has_s2 else 'not in store yet'}, S1 {'yes' if prep.has_s1 else 'no'}"
         + (f", S1 orbit {prep.s1_orbit}" if prep.s1_orbit != "" else "") + ")")
t_now = cur_track()
st.write(f"cursor: **{prep.months[ss.cursor]}**   class: **{ss.cls or '-'}**   co-located other: **{ss.coloc}**   "
         f"confidence: **{ss.conf}**   technology: **{TECH_NAME.get(t_now, '-')}**   focus: **{EVENT_NAME[ss.focus]}**"
         + (f"   DOP identity: **{ss.dop_id or '-'}**   footprint: **{ss.dop_fp}**" if ss.stage == 2 else ""))
lines = []
for t in act():
    cells = []
    for e in EVENTS:
        m = ss.ev[f"{t}_{e}_month"] or "-"
        lo, hi = ss.ev[f"{t}_{e}_earliest"], ss.ev[f"{t}_{e}_latest"]
        rng = f" [{lo or '?'} to {hi or '?'}]" if (lo or hi) else ""
        ec = ss.ev.get(f"{t}_{e}_conf", "")
        cells.append(f"{EVENT_NAME[e]}: **{m}**{rng}" + (f" (conf {ec})" if ec else ""))
    lines.append(f"{TECH_NAME[t]}{' (current)' if t == t_now else ''}: " + "   |   ".join(cells))
if lines:
    st.markdown("  \n".join(lines))

# ---- filmstrip
marks = {}
for t in act():
    for e in EVENTS:
        v = ss.ev[f"{t}_{e}_month"]
        if v in prep.months:
            i = prep.months.index(v)
            marks[i] = (marks.get(i, "") + f" {t[0]}{EVENT_TAG[e]}").strip()
st.image(chipview.render_strip(prep, ss.cursor, WIDTH, marks=marks))

# ---- large views, DOP (pass 2 only), S1 plot
cols = st.columns([1, 1, 1, 1, 1.3] if ss.stage == 2 else [1, 1, 1, 1])
i = ss.cursor
for col, (name, key) in zip(cols, (("S2 true colour", "tc"), ("S2 false colour", "fc"), ("S1 VV", "vv"), ("S1 VH", "vh"))):
    col.caption(f"{name}, {prep.months[i]}")
    col.image(chipview.render_large(prep, key, i))
if ss.stage == 2:
    dop_img, dop_meta = chipview.dop_for_site(site, row.get("bundesland"))
    ss.dop_stores = f"{ss.chip_stores};dop_date_type={'none' if dop_meta is None else dop_meta['date_type']}"
    with cols[4]:
        if dop_img is not None:
            st.caption(f"DOP aerial image: {dop_meta['date_text']} (date type {dop_meta['date_type']})")
            st.image(dop_img)
            st.caption(dop_meta["attribution"] or dop_meta["licence"])
        else:
            st.caption("DOP: no chip")
st.image(chipview.s1_plot(prep, ss.cursor))

# ---- controls (buttons double as key targets; label must start with "[key] ")
st.write("**Class**")
cc = st.columns(len(CLASS_KEYS))
for col, (k, c) in zip(cc, CLASS_KEYS.items()):
    col.button(f"[{k}] {c}", on_click=set_cls, args=(c,), type="primary" if ss.cls == c else "secondary")
m = st.columns(8)
m[0].button("[left] prev month", on_click=move, args=(-1,))
m[1].button("[right] next month", on_click=move, args=(1,))
m[2].button("[up] -12 months", on_click=move, args=(-12,))
m[3].button("[down] +12 months", on_click=move, args=(12,))
m[4].button("[w] co-located other", on_click=cycle_coloc)
m[5].button("[t] switch technology", on_click=toggle_track)
m[6].button("[f] next event focus", on_click=cycle_focus)
m[7].button("[x] clear focused", on_click=clear_focus)
m2 = st.columns(8)
m2[0].button("[s] clearing here", on_click=mark, args=("clear",))
m2[1].button("[d] structures here", on_click=mark, args=("struct",))
m2[2].button("[e] complete here", on_click=mark, args=("complete",))
m2[3].button("[a] earliest here", on_click=mark_range, args=("earliest",))
m2[4].button("[l] latest here", on_click=mark_range, args=("latest",))
m2[5].button("[h] before series", on_click=mark_special, args=(BEFORE_SERIES,))
m2[6].button("[j] after series", on_click=mark_special, args=(AFTER_SERIES,))
m2[7].button("[m] not visible", on_click=mark_special, args=(NOT_VISIBLE,))
m3 = st.columns(8)
m3[0].button("[0] all before series", on_click=fill_all, args=(BEFORE_SERIES,))
m3[1].button("[9] all after series", on_click=fill_all, args=(AFTER_SERIES,))
m3[2].button("[X] clear all", on_click=clear_all)
m3[6].button("[v] event confidence", on_click=cycle_event_conf)
for k, col in zip((1, 2, 3), m3[3:6]):
    col.button(f"[{k}] confidence {k}", on_click=set_conf, args=(k,), type="primary" if ss.conf == k else "secondary")
if ss.stage == 2:
    d = st.columns(4)
    d[0].button("[y] DOP confirms identity and footprint", on_click=set_dop, args=("confirms", "matches"))
    d[1].button("[k] DOP contradicts", on_click=set_dop, args=("contradicts",))
    d[2].button("[q] DOP cannot tell", on_click=set_dop, args=("cannot_tell",))
    d[3].button("[i] footprint answer", on_click=cycle_fp)
st.text_area("Note (free text; no fences, gates or equipment details)", key="note", height=70)
st.button("[Enter] commit Sentinel-only answers (final) and continue" if ss.stage == 1
          else "[Enter] save DOP review and next", on_click=do_save, type="primary")
