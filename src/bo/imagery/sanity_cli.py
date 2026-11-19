"""Make the sanity panels for the public illustration sites and record why each site is public.

``uv run python -m bo.imagery.sanity_cli --root data/chips/v0 --ids P007 ...``
Writes ``figures/sanity/<id>_panel.png`` and ``figures/sanity/public_basis.csv``. The basis is an OSM
element (type and id) tagged as a power plant or generator with the matching source within the
stated distance of the registry coordinate; the table carries no coordinates.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from bo import paths

from .sanity import FIG_DIR, find_osm_public, make_panel


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=paths.CHIPS / "v0")
    ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--version", default="v0")
    ap.add_argument("--out", type=Path, default=FIG_DIR)
    a = ap.parse_args(argv)
    pil = pd.read_parquet(paths.PROCESSED / "pilot" / f"pilot_sites_{a.version}.parquet")
    cands = pil[pil.pilot_id.isin(a.ids)][["pilot_id", "subtype", "lat", "lon"]]
    basis = find_osm_public(cands, radius_m=250, cache=paths.RAW / "osm" / f"sanity_candidates_{a.version}.json")
    basis = basis[basis.pilot_id.isin(a.ids)].copy()
    basis["why_public"] = basis.apply(
        lambda r: f"OpenStreetMap {r.osm_type} {r.osm_id} tagged power={r.osm_power}, source={r.osm_source}; "
                  f"{r.match_distance_m} m from the registry coordinate", axis=1)
    a.out.mkdir(parents=True, exist_ok=True)
    f = a.out / "public_basis.csv"
    if f.exists():  # keep the rows of other pilot versions (ids are disjoint: P for v0, Q for v1)
        old = pd.read_csv(f)
        basis = pd.concat([old[~old.pilot_id.isin(basis.pilot_id)], basis], ignore_index=True)
    basis.to_csv(f, index=False)
    basis = basis[basis.pilot_id.isin(a.ids)]
    for pid in basis.pilot_id:
        print(make_panel(pid, a.root, a.out / f"{pid}_panel.png"))


if __name__ == "__main__":
    main()
