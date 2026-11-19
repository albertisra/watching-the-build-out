"""Command line: ``uv run python -m bo.imagery.cli chips --sites FILE --start ... --end ...``."""

from __future__ import annotations

import argparse
from pathlib import Path

from bo import paths

from .build import build_many
from .config import ChipConfig
from .sites import load_sites


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("chips")
    c.add_argument("--sites", type=Path, nargs="+", required=True)
    c.add_argument("--ids", nargs="*", default=None)
    c.add_argument("--start", required=True)
    c.add_argument("--end", required=True)
    c.add_argument("--s2-start", default=None)
    c.add_argument("--root", type=Path, default=paths.CHIPS / "v0")
    c.add_argument("--bands", nargs="+", default=None)
    c.add_argument("--size", type=int, default=64)
    c.add_argument("--no-s1", action="store_true")
    c.add_argument("--no-s2", action="store_true")
    c.add_argument("--pols", nargs="+", default=None)
    c.add_argument("--speckle", default=None, choices=[None, "boxcar3", "lee5"])
    c.add_argument("--limit-gb", type=float, default=20.0)
    c.add_argument("--stage", default="chips")
    a = ap.parse_args(argv)
    import pandas as pd

    sites = pd.concat([load_sites(p) for p in a.sites], ignore_index=True)
    if a.ids:
        sites = sites[sites.site_id.isin(a.ids)]
    kw = {}
    if a.bands:
        kw["bands"] = tuple(a.bands)
    if a.pols:
        kw["pols"] = tuple(a.pols)
    cfg = ChipConfig(size=a.size, speckle=a.speckle, **kw)
    done, failed = build_many(
        sites, a.start, a.end, cfg, stage=a.stage, root=a.root, byte_limit_gb=a.limit_gb,
        do_s1=not a.no_s1, do_s2=not a.no_s2, s2_start=a.s2_start,
    )
    print("done", len(done), "failed", failed)


if __name__ == "__main__":
    main()
