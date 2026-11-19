"""Clean stale provenance attributes in chip stores and check one relative orbit per Sentinel-1 series."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from bo import paths

from .s1orbit import relative_orbit
from .store import read_site, site_path, write_site

_ITEM = re.compile(r"(S1[ABCD])_IW_GRDH_1S[DS][VH]_\d{8}T\d{6}_\d{8}T\d{6}_(\d{6})_")
S1_RULE = ("relative orbit chosen with select_orbit on Planetary Computer STAC metadata and enforced in the evalscript "
           "from the absolute orbit in the product name (s1orbit.py); S1A, S1B, S1C and S1D scenes included")
FORMULA = "s1orbit.py: offsets S1A 73, S1B 27, S1C 172 (99 from abs orbit 8260), S1D 42"


def clean_store(site_id: str, root: Path) -> None:
    """Drop item lists of months outside the store axis; update the orbit rule text; add ``source`` if missing."""
    ds = read_site(site_id, root).load()
    axis = {str(m)[:7] for m in ds.month.values.astype("datetime64[M]")}
    for key in ("s1_items_by_month", "s2_items_by_month"):
        if key in ds.attrs:
            d = json.loads(ds.attrs[key])
            ds.attrs[key] = json.dumps({k: v for k, v in d.items() if k in axis})
    if ds.attrs.get("source") == "sentinelhub":
        if "s1_orbit_rule" in ds.attrs:
            ds.attrs["s1_orbit_rule"] = S1_RULE
        if "s1_relative_orbit" in ds.attrs:
            ds.attrs["s1_orbit_formula"] = FORMULA
    ds.attrs.setdefault("source", "planetary_computer")
    write_site(ds, site_id, root)


def orbit_consistency(site_id: str, root: Path) -> dict | None:
    """Relative orbit of every listed Sentinel-1 item against the store's orbit, for every month."""
    ds = read_site(site_id, root)
    if "s1_items_by_month" not in ds.attrs:
        return None
    orbit = int(ds.attrs["s1_relative_orbit"])
    items = json.loads(ds.attrs["s1_items_by_month"])
    n = bad = unparsed = 0
    months_bad = []
    for month, lst in items.items():
        for name in lst:
            m = _ITEM.search(name)
            n += 1
            if not m:
                unparsed += 1
                continue
            if relative_orbit(m.group(1), int(m.group(2))) != orbit:
                bad += 1
                months_bad.append(month)
    return {"store": root.name, "site_id": site_id, "source": ds.attrs.get("source", "planetary_computer"),
            "relative_orbit": orbit, "months_with_items": len(items), "items": n, "items_on_other_orbit": bad,
            "unparsed_items": unparsed, "months_with_other_orbit": ",".join(sorted(set(months_bad))),
            "one_orbit_per_series": bad == 0 and unparsed == 0}


def run_all(roots: list[Path] | None = None) -> pd.DataFrame:
    roots = roots or [paths.CHIPS / r for r in ("sh_v1", "sh_v1_s1", "v0", "test", "demo150")]
    rows = []
    for root in roots:
        for p in sorted(root.glob("*.zarr")):
            r = orbit_consistency(p.stem, root)
            if r:
                rows.append(r)
    return pd.DataFrame(rows)


_ = (np, site_path)
