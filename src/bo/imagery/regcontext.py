"""Other registered sites inside a chip, by technology (review finding I5).

Computed from ``data/processed/registry/registry_sites.parquet`` (coordinates and technology only). No dates,
status or capacity are read, so nothing here can leak registry timing into chip attributes. The site the chip is
centred on is excluded by its site key when given.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from bo import paths

from .geo import ChipGrid, transformer

REGISTRY_SITES = paths.PROCESSED / "registry" / "registry_sites.parquet"


@lru_cache(maxsize=1)
def _sites() -> pd.DataFrame:
    return pd.read_parquet(REGISTRY_SITES, columns=["site_id", "technology", "lat", "lon"]).dropna()


def other_sites_in_chip(grid: ChipGrid, own_site_key: str | None = None, sites: pd.DataFrame | None = None) -> dict:
    s = _sites() if sites is None else sites
    x, y = transformer(4326, grid.epsg).transform(s.lon.to_numpy(), s.lat.to_numpy())
    l, b, r, t = grid.bounds
    inside = (np.asarray(x) >= l) & (np.asarray(x) < r) & (np.asarray(y) >= b) & (np.asarray(y) < t)
    sel = s[inside]
    if own_site_key is not None:
        sel = sel[sel.site_id != own_site_key]
    return {k: int(v) for k, v in sel.technology.value_counts().items()}


def attr_value(grid: ChipGrid, own_site_key: str | None = None) -> str:
    return json.dumps(other_sites_in_chip(grid, own_site_key), sort_keys=True)
