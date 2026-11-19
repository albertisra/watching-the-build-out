"""Add quality flags and other-site context to chip stores that were written before these existed."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bo import paths

from .geo import ChipGrid
from .qc import add_flags
from .regcontext import attr_value
from .store import read_site, write_site


def backfill_store(site_id: str, root: Path, own_keys: dict[str, str] | None = None) -> None:
    from affine import Affine

    ds = read_site(site_id, root).load()
    add_flags(ds)
    grid = ChipGrid(int(ds.attrs["crs_epsg"]), Affine(*ds.attrs["transform"]), int(ds.attrs["chip_size_px"]),
                    float(ds.attrs["resolution_m"]))
    ds.attrs["other_registered_sites_in_chip"] = attr_value(grid, (own_keys or {}).get(site_id))
    write_site(ds, site_id, root)


def own_keys_v1() -> dict[str, str]:
    p = pd.read_parquet(paths.PROCESSED / "pilot" / "pilot_sites_v1.parquet")
    return dict(zip(p.pilot_id, p.site_key, strict=True))
