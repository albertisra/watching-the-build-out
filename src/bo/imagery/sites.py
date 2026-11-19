"""Site lists are inputs: any parquet with an id column and lat/lon. Registry fields are dropped."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ID_COLUMNS = ("site_id", "pilot_id", "neg_id")


def load_sites(path: Path, id_col: str | None = None) -> pd.DataFrame:
    """Return a frame with columns site_id, lat, lon only (plus ``group`` if present).

    Registry fields such as status, commissioned and power_kw are never carried along.
    """
    df = pd.read_parquet(path)
    id_col = id_col or next((c for c in ID_COLUMNS if c in df.columns), None)
    if id_col is None:
        raise ValueError(f"no id column among {ID_COLUMNS} in {path}")
    out = df[[id_col, "lat", "lon"]].rename(columns={id_col: "site_id"})
    if out.site_id.duplicated().any():
        raise ValueError("duplicate site ids")
    if not out.lat.between(47, 56).all() or not out.lon.between(5, 16).all():
        raise ValueError("coordinates outside Germany's bounding box")
    return out.reset_index(drop=True)
