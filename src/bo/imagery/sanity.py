"""Visual sanity panels: true colour and Sentinel-1 VV strips for public illustration sites.

For the author's review only. Frames show the 640 m chip, the acquisition month and a scale bar.
Nothing is annotated: no fences, access points or equipment. Titles use the pilot id, not
coordinates. Contains modified Copernicus Sentinel data 2017-2026.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from bo import paths

from .store import read_site

FIG_DIR = paths.FIGURES / "sanity"
SRC_TAGS = {"battery": ("battery", "storage"), "ground-mounted": ("solar",)}


def find_osm_public(cands: pd.DataFrame, radius_m: int = 400, cache: Path | None = None) -> pd.DataFrame:
    """Match candidate sites to OSM power plants/generators of the right source within radius_m.

    ``cands`` needs pilot_id, subtype, lat, lon. One Overpass request for all candidates, cached.
    Returns pilot_id, subtype, osm_type, osm_id, power, source (no coordinates).
    """
    cache = cache or (paths.RAW / "osm" / "sanity_candidates.json")
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        parts = "".join(
            f'nwr(around:{radius_m},{r.lat:.6f},{r.lon:.6f})["power"~"^(plant|generator)$"];'
            for r in cands.itertuples())
        q = f"[out:json][timeout:120];({parts});out tags center;"
        resp = None
        for attempt in range(4):
            resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": q},
                                 timeout=180, headers={"User-Agent": "research-imagery-pipeline/0.1"})
            if resp.status_code == 200:
                break
            time.sleep(30 * (attempt + 1))
        resp.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(resp.content)
        data = resp.json()
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    rows = []
    for r in cands.itertuples():
        best = None
        for el in data["elements"]:
            c = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
            if c["lat"] is None:
                continue
            tags = el.get("tags", {})
            src = " ".join(tags.get(k, "") for k in
                           ("plant:source", "generator:source", "source")).lower()
            if not any(t in src for t in SRC_TAGS[r.subtype]):
                continue
            _, _, d = geod.inv(r.lon, r.lat, c["lon"], c["lat"])
            if d <= radius_m and (best is None or d < best[0]):
                best = (d, el)
        if best:
            el = best[1]
            rows.append({"pilot_id": r.pilot_id, "subtype": r.subtype, "osm_type": el["type"],
                         "osm_id": el["id"], "osm_power": el["tags"].get("power"),
                         "osm_source": el["tags"].get("plant:source")
                         or el["tags"].get("generator:source"),
                         "match_distance_m": round(best[0])})
    return pd.DataFrame(rows)


def pick_frames(ds, per_quarter: bool = True) -> list[int]:
    """Index of the best-covered month in each quarter (clear fraction of S2 pixels)."""
    months = pd.DatetimeIndex(ds.month.values)
    cov = (ds.s2_clear_count.values > 0).mean(axis=(1, 2))
    any_data = cov > 0
    if "s1_vv_db" in ds:
        any_data = any_data | np.isfinite(ds.s1_vv_db.values).any(axis=(1, 2))
    first = int(np.argmax(any_data)) if any_data.any() else 0
    idx = []
    for q, g in pd.Series(range(first, len(months))).groupby(months[first:].to_period("Q")):
        k = g.values[np.argmax(cov[g.values])]
        if cov[k] > 0 or True:
            idx.append(int(k))
    return idx


def make_panel(site_id: str, chips_root: Path, out: Path | None = None, min_cov: float = 0.5,
               ncols: int = 12) -> Path:
    ds = read_site(site_id, chips_root).load()
    bands = list(ds.band.values)
    rgb_i = [bands.index(b) for b in ("B04", "B03", "B02")]
    idx = pick_frames(ds)
    cov = (ds.s2_clear_count.values > 0).mean(axis=(1, 2))
    months = pd.DatetimeIndex(ds.month.values)
    nrows_s2 = int(np.ceil(len(idx) / ncols))
    has_s1 = "s1_vv_db" in ds
    fig, axes = plt.subplots(2 * nrows_s2 if has_s1 else nrows_s2, ncols,
                             figsize=(ncols * 1.5, (2 * nrows_s2 if has_s1 else nrows_s2) * 1.62),
                             squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    res = float(ds.attrs["resolution_m"])
    n = int(ds.attrs["chip_size_px"])
    for j, k in enumerate(idx):
        r, c = divmod(j, ncols)
        ax = axes[r, c]
        if cov[k] >= min_cov:
            img = np.moveaxis(ds.s2_refl.values[k][rgb_i], 0, -1)
            img = np.clip(img / 0.25, 0, 1) ** (1 / 1.4)
            img = np.where(np.isfinite(img), img, 0.5)
            ax.imshow(img, interpolation="nearest")
        else:
            ax.imshow(np.full((n, n), 0.85), cmap="gray", vmin=0, vmax=1)
            ax.text(n / 2, n / 2, "no clear\nobs", ha="center", va="center", fontsize=6)
        ax.set_title(f"{months[k]:%Y-%m}", fontsize=6, pad=1)
        bar = 100 / res
        ax.plot([4, 4 + bar], [n - 5, n - 5], color="white", lw=1.5)
        if j == 0:
            ax.text(4, n - 8, "100 m", color="white", fontsize=5, va="bottom")
        if has_s1:
            a2 = axes[nrows_s2 + r, c]
            vv = ds.s1_vv_db.values[k]
            if np.isfinite(vv).any():
                a2.imshow(vv, cmap="gray", vmin=-20, vmax=0, interpolation="nearest")
            else:
                a2.imshow(np.full((n, n), 0.85), cmap="gray", vmin=0, vmax=1)
                a2.text(n / 2, n / 2, "no S1", ha="center", va="center", fontsize=6)
            a2.set_title(f"S1 VV {months[k]:%Y-%m}", fontsize=5, pad=1)
    orbit = ds.attrs.get("s1_relative_orbit")
    fig.suptitle(
        f"{site_id}  true colour (B04, B03, B02) best month per quarter; lower rows S1 VV, "
        f"relative orbit {orbit} {ds.attrs.get('s1_pass_direction', '')}\n"
        "Contains modified Copernicus Sentinel data 2017-2026. Observed imagery (composite) for review, "
        "not an annotation.", fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = out or (FIG_DIR / f"{site_id}_panel.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out
