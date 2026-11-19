"""Build and cache chips for a list of sites."""

from __future__ import annotations

import time
import traceback
from pathlib import Path

import pandas as pd

from .composite import month_index
from .config import ChipConfig
from .geo import chip_grid
from .quota import GLOBAL, Stage
from .s1pipe import build_s1
from .s2pipe import build_s2
from .store import build_dataset, site_path, write_scene_log, write_site


def build_site(site_id, lon, lat, start, end, cfg=None, do_s2=True, do_s1=True, root=None,
               s2_start=None, workers=None):
    """Common month axis start..end; Sentinel-2 is searched from ``s2_start`` (default start)."""
    cfg = cfg or ChipConfig()
    grid = chip_grid(lon, lat, cfg.size, cfg.res)
    months = month_index(start, end)
    s2 = (build_s2(grid, lon, lat, s2_start or start, end, cfg, workers=workers, months=months)
          if do_s2 else None)
    s1 = build_s1(grid, start, end, cfg, workers=workers, months=months) if do_s1 else None
    ds = build_dataset(site_id, grid, cfg, s2, s1, start, end)
    p = write_site(ds, site_id, root)
    if s2 is not None and len(s2["scene_log"]):
        write_scene_log(s2["scene_log"], site_id, root)
    return p, ds


class ByteBudgetExceeded(RuntimeError):
    pass


def build_many(sites: pd.DataFrame, start, end, cfg=None, stage="chips", root=None,
               skip_existing=True, byte_limit_gb: float = 20.0, log_each_site=True, **kw):
    """Build chips site by site. Stops (raises) when the network bytes of this call pass the limit.

    The limit is checked between sites against the bytes GDAL received through the counting proxy, so a single site
    can overshoot it by at most one site's volume.
    """
    from .netcount import ensure_proxy

    proxy = ensure_proxy()
    done, failed = [], []
    net0 = proxy.bytes_down
    with Stage(stage, "planetary_computer", note=f"{len(sites)} sites {start}..{end}"):
        for r in sites.itertuples():
            if skip_existing and site_path(r.site_id, root).exists():
                continue
            used = (proxy.bytes_down - net0) / 1e9
            if used > byte_limit_gb:
                raise ByteBudgetExceeded(f"{used:.1f} GB read, limit {byte_limit_gb} GB")
            t0 = time.time()
            try:
                if log_each_site:
                    with Stage(f"{stage}_site", "planetary_computer", note=str(r.site_id)):
                        build_site(r.site_id, r.lon, r.lat, start, end, cfg, root=root, **kw)
                else:
                    build_site(r.site_id, r.lon, r.lat, start, end, cfg, root=root, **kw)
                done.append(r.site_id)
                print(f"{r.site_id} ok {time.time()-t0:.0f}s total {used:.2f} GB", flush=True)
            except Exception:  # noqa: BLE001 - one failing site must not stop the batch
                traceback.print_exc()
                failed.append(r.site_id)
    return done, failed


_ = (GLOBAL, Path)
