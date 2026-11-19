"""Build monthly feature tables for every site in a set of chip-store roots of one platform.

``uv run python -m bo.features.build --name sh_v1 --roots data/chips/sh_v1``
``uv run python -m bo.features.build --name sh_v1_dec --roots data/chips/sh_v1_s1 data/chips/sh_v1_s2``

Roots are combined per site with ``bo.imagery.store.read_series``, which refuses to mix Sentinel Hub and
Planetary Computer stores. Output: ``data/processed/features/features_<name>.parquet`` with columns
``ID_COLUMNS + FEATURE_COLUMNS`` only (no registry field can enter).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from bo import paths
from bo.imagery import store

from .allowlist import FEATURE_COLUMNS, ID_COLUMNS
from .site import site_features


def site_ids(roots: list[Path]) -> list[str]:
    ids = set()
    for r in roots:
        ids |= {p.stem for p in r.glob("*.zarr")}
    return sorted(ids)


def build(name: str, roots: list[Path]) -> Path:
    frames = [site_features(store.read_series(s, roots), site_id=s) for s in site_ids(roots)]
    df = pd.concat(frames, ignore_index=True)
    assert tuple(df.columns) == ID_COLUMNS + FEATURE_COLUMNS
    out = paths.PROCESSED / "features" / f"features_{name}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--roots", nargs="+", required=True, help="store roots relative to the repository")
    a = ap.parse_args()
    out = build(a.name, [paths.REPO_ROOT / r for r in a.roots])
    print(out)


if __name__ == "__main__":
    main()
