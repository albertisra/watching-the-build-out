"""Blindness guard. Only whitelisted fields ever reach the labelling view.

Registry fields (reg_*, capacity, technology, status, dates, unit IDs), the queue stratum, the
site ID (its prefix tells positives from negatives), coordinates, federal state and any model
output are all excluded. Registry facts live in `bo.labelling.review` (separate review mode, after the labels are locked);
nothing in the labelling session imports it.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

# Fields the view may receive. `alias` is the position label shown instead of the site ID.
VIEW_FIELDS = ("alias", "position", "n_total", "is_relabel_hidden")

FORBIDDEN_PREFIXES = ("reg_", "model_", "pred_", "prob_", "score_")
FORBIDDEN_NAMES = {
    "capacity", "power_kw", "capacity_kw", "technology", "subtype", "status", "commissioned",
    "commissioning_date", "unit_ids", "unit_id", "n_units", "stratum", "site_id", "queue_id",
    "site_key", "registry_key", "landkreis", "osm_category", "worldcover_class", "pilot_id", "neg_id", "lat", "lon", "bundesland", "state", "kind", "category", "group", "date",
    "planned", "quantity_type", "nearest_unit_m", "area_m2", "osm_id", "osm_type",
}
# Names are matched on the lower-cased key; any hit raises.


def is_forbidden(key: str) -> bool:
    k = key.lower()
    return k in FORBIDDEN_NAMES or k.startswith(FORBIDDEN_PREFIXES) or "capacity" in k or "unit_id" in k


def assert_blind(payload: Mapping) -> None:
    bad = [k for k in payload if is_forbidden(str(k))]
    if bad:
        raise ValueError(f"fields not allowed in the labelling view: {bad}")


def view_payload(position: int, n_total: int) -> dict:
    """Everything the view gets about the current item: its position only. The relabel flag is not
    shown either, so a relabel is indistinguishable from a first label."""
    payload = {"alias": f"item {position + 1} of {n_total}", "position": position, "n_total": n_total}
    assert_blind(payload)
    return payload


# DOP chip metadata fields the view may show (index columns `group`, `state`, `source_url`, `reason`
# and the chip path are left out: they identify the class or the site).
DOP_VIEW_FIELDS = ("date_type", "flight_date", "flight_year", "licence", "attribution", "use_restriction")


def dop_view(meta: Mapping) -> dict:
    """Flight date only when the date type is day; a year edition shows the year; a production date
    or no date shows no date at all (never a production date as a flight date)."""
    dtype = str(meta.get("date_type", "none"))
    out = {"date_type": dtype, "date_text": "no acquisition date known"}
    if dtype == "day" and meta.get("flight_date"):
        out["date_text"] = f"flown {meta['flight_date']}"
    elif dtype == "year_edition" and meta.get("flight_year") not in (None, ""):
        try:
            out["date_text"] = f"edition year {int(float(meta['flight_year']))} (day unknown)"
        except (TypeError, ValueError):
            pass
    elif dtype == "production_only":
        out["date_text"] = "flight date unknown (only a production date exists; not shown as a flight date)"
    out["internal_only"] = bool(meta.get("use_restriction"))
    out["licence"] = str(meta.get("licence") or "")
    out["attribution"] = str(meta.get("attribution") or "")
    assert_blind({k: v for k, v in out.items() if k in FORBIDDEN_NAMES})
    return out


def dop_allowed(bundesland: str | None) -> bool:
    """False for states whose DOP terms restrict external use (`bo.imagery.dop.restricted_states`,
    Mecklenburg-Vorpommern). Their DOP is not shown in labelling until the author decides otherwise."""
    from bo.imagery.dop import restricted_states

    return str(bundesland or "") not in restricted_states()


def session_columns(queue: pd.DataFrame) -> pd.DataFrame:
    """The queue as the labelling session sees it: item key and the federal state (only to gate DOP).
    Stratum, registry key, district, OSM category, land cover and coordinates are dropped."""
    return queue[[c for c in ("queue_id", "bundesland") if c in queue.columns]].copy()
