"""Chip loading and image rendering for the labelling view. Display only: stretches and the
centre/ring split are viewing conventions (docs/assumptions.md A55), not measurements.

Missing months are drawn as empty frames, never interpolated.
"""

from __future__ import annotations

import io
import json
from collections import OrderedDict
from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from bo import paths
from bo.imagery import store

from .blind import dop_view

EE_ROOT = "ee_r1"  # Earth Engine stores of the round-1 queue, keyed by queue_id
SH_ROOTS = ("sh_v1", "sh_v1_s1", "sh_v1_s2")
PC_ROOTS = ("v0", "demo150")
TC_BANDS = ("B04", "B03", "B02")
FC_BANDS = ("B08", "B04", "B03")  # near-infrared, red, green
TC_MAX = 0.30
FC_MAX = (0.50, 0.30, 0.30)
VV_RANGE = (-25.0, 0.0)
VH_RANGE = (-30.0, -5.0)
CENTRE_RADIUS_PX = 4  # 40 m around the chip centre
RING_PX = (16, 28)  # 160 to 280 m from the centre


def resolve_roots(site_id: str, chips_dir: Path | None = None) -> tuple[str, list[Path], list[str]]:
    """Pick one platform and its store roots for a site. An Earth Engine store (``ee_r1``) wins over everything else; Sentinel Hub with Sentinel-2 wins over
    Planetary Computer; a Sentinel Hub Sentinel-1-only store is used when nothing else has the site.
    Never mixes platforms. Returns (platform, roots, store names)."""
    base = chips_dir or paths.CHIPS
    if store.site_path(site_id, base / EE_ROOT).exists():  # one platform and one S1 processing for the whole queue
        return "earthengine", [base / EE_ROOT], [EE_ROOT]
    sh = [base / r for r in SH_ROOTS if store.site_path(site_id, base / r).exists()]
    pc = [base / r for r in PC_ROOTS if store.site_path(site_id, base / r).exists()]
    if sh:
        full = [r for r in sh if r.name == "sh_v1"]
        roots = full or sh  # sh_v1 already holds S1 and S2; separate roots are merged otherwise
        has_s2 = bool(full) or any(r.name == "sh_v1_s2" for r in sh)
        if has_s2 or not pc:
            return "sentinelhub", roots, [r.name for r in roots]
    if pc:
        return "planetary_computer", pc[:1], [pc[0].name]
    raise FileNotFoundError(f"no chip store holds {site_id}")


def _stretch(a: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((a - lo) / (hi - lo), 0, 1)


def _rgb(refl: np.ndarray, bands: list[str], names: tuple[str, str, str], maxes) -> np.ndarray:
    """refl (month, band, y, x) -> uint8 (month, y, x, 3); all-NaN pixels become 0 and are masked later."""
    out = []
    for n, mx in zip(names, maxes):
        ch = np.nan_to_num(_stretch(refl[:, bands.index(n)], 0.0, mx) ** (1 / 1.4))
        out.append(ch)
    return (np.stack(out, axis=-1) * 255).astype(np.uint8)


class Prepared:
    """Pre-rendered arrays for one site (observed composites; stretch only)."""

    def __init__(self, ds):
        self.platform = store.source_of(ds)
        self.code_version = str(ds.attrs.get("code_version", ""))
        self.months = [str(m)[:7] for m in ds.month.values.astype("datetime64[M]")]
        n = len(self.months)
        self.n = n
        self.size = int(ds.sizes["x"])
        self.res = float(ds.attrs.get("resolution_m", 10))
        self.has_s2 = "s2_refl" in ds
        self.has_s1 = "s1_vv_db" in ds
        bands = [str(b) for b in ds.band.values] if "band" in ds.coords else []
        self.tc = self.fc = None
        self.s2_ok = np.zeros(n, bool)
        self.s2_count = np.zeros(n, int)
        self.flag_bright = np.zeros(n, bool)
        self.flag_cld = np.zeros(n, bool)
        if self.has_s2:
            refl = ds["s2_refl"].values
            self.s2_ok = ~np.isnan(refl).all(axis=(1, 2, 3))
            if all(b in bands for b in TC_BANDS):
                self.tc = _rgb(refl, bands, TC_BANDS, (TC_MAX,) * 3)
            if all(b in bands for b in FC_BANDS):
                self.fc = _rgb(refl, bands, FC_BANDS, FC_MAX)
            self.s2_count = np.nan_to_num(np.median(ds["s2_clear_count"].values, axis=(1, 2))).astype(int)
            if "s2_flag_bright" in ds:
                self.flag_bright = ds["s2_flag_bright"].values.astype(bool)
            if "s2_flag_cld_disagree" in ds:
                self.flag_cld = ds["s2_flag_cld_disagree"].values.astype(bool)
        self.vv = self.vh = None
        self.s1_ok = np.zeros(n, bool)
        self.s1_series = {}
        if self.has_s1:
            for name, var, rng in (("vv", "s1_vv_db", VV_RANGE), ("vh", "s1_vh_db", VH_RANGE)):
                a = ds[var].values
                ok = ~np.isnan(a).all(axis=(1, 2))
                if name == "vv":
                    self.s1_ok = ok
                if ok.any():
                    setattr(self, name, (np.nan_to_num(_stretch(a, *rng)) * 255).astype(np.uint8))
                    self.s1_series[name] = _centre_ring(a)
                    self.s1_series[name + "_ok"] = ok
        self.s1_orbit = ds.attrs.get("s1_relative_orbit", "")


def _centre_ring(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    s = a.shape[-1]
    yy, xx = np.mgrid[:s, :s]
    r = np.hypot(yy - (s - 1) / 2, xx - (s - 1) / 2)
    cm, rm = r <= CENTRE_RADIUS_PX, (r >= RING_PX[0]) & (r <= RING_PX[1])
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmean(a[:, cm], axis=1), np.nanmean(a[:, rm], axis=1)


_CACHE: OrderedDict[str, tuple[Prepared, str, str]] = OrderedDict()
_LOCK = Lock()
_CACHE_SIZE = 12


def load_site(site_id: str, chips_dir: Path | None = None) -> tuple[Prepared, str, str]:
    """(prepared arrays, platform, 'store names') with an LRU cache. Reads through bo.imagery.store."""
    key = f"{chips_dir}:{site_id}"
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    platform, roots, names = resolve_roots(site_id, chips_dir)
    ds = store.read_series(site_id, roots)
    val = (Prepared(ds), platform, "+".join(names))
    with _LOCK:
        _CACHE[key] = val
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
    return val


def prefetch(site_ids: list[str], chips_dir: Path | None = None) -> None:
    from concurrent.futures import ThreadPoolExecutor

    def _go(s):
        try:
            load_site(s, chips_dir)
        except (OSError, ValueError, KeyError):  # prefetch is best effort
            return

    ThreadPoolExecutor(max_workers=2).submit(lambda: [_go(s) for s in site_ids])


# ---------------------------------------------------------------- drawing

def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # old Pillow
        return ImageFont.load_default()


def empty_frame(t: int, text: str = "no data") -> Image.Image:
    im = Image.new("RGB", (t, t), (38, 38, 42))
    d = ImageDraw.Draw(im)
    d.line([(0, 0), (t, t)], fill=(70, 70, 76))
    d.line([(0, t), (t, 0)], fill=(70, 70, 76))
    d.text((t // 2, t // 2), text, fill=(150, 150, 150), font=_font(max(9, t // 10)), anchor="mm")
    return im


def _tile(arr: np.ndarray | None, i: int, ok: bool, t: int, gray: bool = False, text="no data") -> Image.Image:
    if arr is None or not ok:
        return empty_frame(t, text)
    a = arr[i]
    im = Image.fromarray(a, "L" if gray else "RGB").convert("RGB")
    return im.resize((t, t), Image.NEAREST)


def add_scale_bar(im: Image.Image, chip_px: int, res_m: float, metres: float = 640.0) -> Image.Image:
    """Scale bar for `metres` (default: the chip width). Pixel length = metres / res * zoom."""
    zoom = im.width / chip_px
    length = round(metres / res_m * zoom)
    length = min(length, im.width - 8)
    d = ImageDraw.Draw(im)
    y = im.height - 10
    d.rectangle([4, y - 1, 4 + length, y + 2], fill=(255, 255, 255), outline=(0, 0, 0))
    d.text((6, y - 4), f"{int(metres)} m", fill=(255, 255, 255), font=_font(11), anchor="lb",
           stroke_width=1, stroke_fill=(0, 0, 0))
    return im


def window_start(cursor: int, n: int, width: int) -> int:
    return int(max(0, min(cursor - width // 2, n - width)))


ROWS = (("S2 true colour", "tc"), ("S2 false colour NIR-R-G", "fc"), ("S1 VV", "vv"), ("S1 VH", "vh"))


def render_strip(p: Prepared, cursor: int, width: int = 9, t: int = 104,
                 marks: dict[int, str] | None = None) -> Image.Image:
    """Filmstrip of `width` months around the cursor. Rows: S2 TC, S2 FC, S1 VV, S1 VH. Header per
    column: month, clear-observation count, B/D flags. `marks` maps month index -> short marker strings."""
    s = window_start(cursor, p.n, width)
    idx = range(s, min(s + width, p.n))
    left, head, gap = 150, 40, 4
    W = left + width * (t + gap)
    H = head + len(ROWS) * (t + gap) + 4
    im = Image.new("RGB", (W, H), (20, 20, 24))
    d = ImageDraw.Draw(im)
    f, fs = _font(13), _font(11)
    for r, (label, key) in enumerate(ROWS):
        d.text((6, head + r * (t + gap) + t // 2), label, fill=(210, 210, 210), font=fs, anchor="lm")
    for c, i in enumerate(idx):
        x = left + c * (t + gap)
        col = (255, 220, 60) if i == cursor else (200, 200, 200)
        d.text((x, 2), p.months[i], fill=col, font=f)
        if p.has_s2:
            flags = ("B" if p.flag_bright[i] else "") + ("D" if p.flag_cld[i] else "")
            d.text((x, 20), f"n={p.s2_count[i]} {flags}", fill=(160, 200, 255), font=fs)
        else:
            d.text((x, 20), "no S2 in store", fill=(130, 130, 130), font=fs)
        mk = (marks or {}).get(i)
        if mk:
            d.text((x + t, 2), mk, fill=(120, 255, 120), font=f, anchor="ra")
        for r, (_, key) in enumerate(ROWS):
            y = head + r * (t + gap)
            if key in ("tc", "fc"):
                tile = _tile(getattr(p, key), i, p.s2_ok[i], t,
                             text="no clear obs" if p.has_s2 else "no S2")
            else:
                tile = _tile(getattr(p, key), i, p.s1_ok[i], t, gray=True,
                             text="no S1" if p.has_s1 else "no S1 in store")
            im.paste(tile, (x, y))
            if i == cursor:
                d.rectangle([x - 1, y - 1, x + t, y + t], outline=(255, 220, 60), width=2)
    # one 640 m bar under the first column set: bar spans one chip width = one tile
    zoom = t / p.size
    ln = int(640.0 / p.res * zoom)
    y = H - 3
    d.rectangle([left, y - 2, left + ln, y], fill=(255, 255, 255))
    d.text((left + ln + 6, y + 1), "640 m (one tile = full chip width)", fill=(230, 230, 230),
           font=fs, anchor="lb")
    return im


def render_large(p: Prepared, key: str, i: int, size: int = 320) -> Image.Image:
    gray = key in ("vv", "vh")
    ok = p.s1_ok[i] if gray else p.s2_ok[i]
    im = _tile(getattr(p, key), i, ok, size, gray=gray)
    return add_scale_bar(im, p.size, p.res)


def s1_plot(p: Prepared, cursor: int):
    """Monthly centre and ring means (dB) for VV and VH with a cursor line. Gaps stay gaps."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.5, 2.6), dpi=90)
    ax = fig.subplots(1, 2, sharex=True)
    x = np.arange(p.n)
    for a, name, lab in zip(ax, ("vv", "vh"), ("VV", "VH")):
        if name in p.s1_series:
            c, r = p.s1_series[name]
            a.plot(x, c, ".-", ms=2, lw=0.7, color="tab:red", label="centre (40 m radius)")
            a.plot(x, r, ".-", ms=2, lw=0.7, color="tab:blue", label="ring (160-280 m)")
        a.axvline(cursor, color="k", lw=1)
        a.set_title(f"S1 {lab} (dB, observed)", fontsize=8)
        a.tick_params(labelsize=7)
        step = max(1, p.n // 6)
        a.set_xticks(x[::step])
        a.set_xticklabels([p.months[i] for i in x[::step]], rotation=30, fontsize=6)
    if p.s1_series:
        ax[0].legend(fontsize=6, loc="best")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


# ---------------------------------------------------------------- DOP

def dop_for_site(queue_id: str, bundesland: str | None, size: int = 420
                 ) -> tuple[Image.Image | None, dict | None]:
    """DOP chip (downsampled, RGB) and its display metadata, or (None, None). Aerial image only.
    Returns (None, None) without opening anything for use-restricted states (Mecklenburg-Vorpommern).
    The index is keyed by registry key (positives) or queue_id (negatives) and is joined through the
    queue file, so the view only ever deals in queue_id."""
    from .blind import dop_allowed

    if not dop_allowed(bundesland):
        return None, None
    idx = _dop_index()
    if queue_id not in idx.index:
        return None, None
    row = idx.loc[queue_id].to_dict()
    tif = paths.REPO_ROOT / str(row["chip_path"])
    if not row.get("chip_ok") or not tif.exists():
        return None, dop_view(row)
    side = tif.with_suffix(".json")
    if side.exists():
        sc = json.loads(side.read_text())
        row["use_restriction"] = sc.get("use_restriction", "")
        row["attribution"] = sc.get("attribution", "")
    import rasterio

    with rasterio.open(tif) as r:
        arr = r.read([1, 2, 3], out_shape=(3, size, size))
    im = Image.fromarray(np.moveaxis(arr, 0, -1).astype(np.uint8))
    return add_scale_bar(im, 640, 1.0), dop_view(row)  # DOP chips cover 640 m x 640 m (1 px = 1 m here)


def dop_status(queue_id: str, bundesland: str | None) -> str:
    """`restricted` (use-restricted state, DOP never shown), `chip` (a usable chip exists) or `none`.
    Reads the index only; no image is opened."""
    from .blind import dop_allowed

    if not dop_allowed(bundesland):
        return "restricted"
    idx = _dop_index()
    if queue_id not in idx.index:
        return "none"
    row = idx.loc[queue_id]
    return "chip" if row.get("chip_ok") and (paths.REPO_ROOT / str(row["chip_path"])).exists() else "none"


_DOP_INDEX: pd.DataFrame | None = None
DOP_QUEUE_INDEX = "dop_chips_queue_round1.parquet"
DOP_VIEW_INDEX = "dop_chips_queue_round1_view.parquet"


def build_dop_index(dop: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Re-key a DOP index by queue_id. DOP `site_id` holds the registry key for positives and the
    queue_id for negatives, so the join key is queue.site_id where present, else queue.queue_id."""
    key = queue["site_id"].fillna(queue["queue_id"]) if "site_id" in queue else queue["queue_id"]
    m = pd.DataFrame({"queue_id": queue["queue_id"].values, "dop_key": key.values})
    out = m.merge(dop.drop_duplicates("site_id"), left_on="dop_key", right_on="site_id", how="inner")
    return out.drop(columns=["site_id", "dop_key"]).set_index("queue_id")


def _dop_index() -> pd.DataFrame:
    global _DOP_INDEX
    if _DOP_INDEX is None:
        vf = paths.PROCESSED / "labels" / DOP_VIEW_INDEX  # keyed by queue_id, built by `make queue-view`
        if vf.exists():
            _DOP_INDEX = pd.read_parquet(vf).set_index("queue_id")
        else:  # development queue: pilot chips keyed by pilot or negative id = queue_id
            _DOP_INDEX = pd.read_parquet(paths.PROCESSED / "pilot" / "dop_chips_v1.parquet").set_index("site_id")
    return _DOP_INDEX
