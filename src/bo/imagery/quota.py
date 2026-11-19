"""Usage accounting: requests, bytes read and processing units, appended to a CSV log.

GDAL hides its HTTP traffic from Python, so the pipeline routes GDAL through the counting proxy
of ``netcount`` (exact bytes received over the tunnels, TLS included). We also count STAC
searches, COG opens, COG window reads, decoded bytes and Sentinel Hub requests and processing
units. STAC and Sentinel Hub JSON traffic made with ``requests`` is not in the byte count (small).
"""

from __future__ import annotations

import csv
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from bo import paths

QUOTA_LOG = paths.RESULTS / "imagery" / "quota_log.csv"
FIELDS = [
    "timestamp_utc", "stage", "platform", "stac_searches", "cog_opens", "cog_window_reads",
    "decoded_bytes", "net_bytes_gdal", "net_tunnels", "sentinel_hub_requests", "sentinel_hub_pu",
    "elapsed_s", "note", "eecu_seconds",
]
_COUNTED = ["stac_searches", "cog_opens", "cog_window_reads", "decoded_bytes", "net_bytes_proxy",
            "net_tunnels", "sentinel_hub_requests", "sentinel_hub_pu"]


@dataclass
class Counters:
    stac_searches: int = 0
    cog_opens: int = 0
    cog_window_reads: int = 0
    decoded_bytes: int = 0
    net_bytes_proxy: int = 0
    net_tunnels: int = 0
    sentinel_hub_requests: int = 0
    sentinel_hub_pu: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, **kw) -> None:
        with self._lock:
            for k, v in kw.items():
                setattr(self, k, getattr(self, k) + v)


GLOBAL = Counters()


class Stage:
    """Context manager that records counter deltas for one stage in the quota log."""

    def __init__(self, stage: str, platform: str, note: str = "", log: Path | None = None,
                 counters: Counters | None = None, log_sh: bool = True):
        self.stage, self.platform, self.note = stage, platform, note
        self.log_sh = log_sh  # False when Sentinel Hub requests are logged one by one
        self.log = log or QUOTA_LOG
        self.c = counters or GLOBAL

    def __enter__(self):
        self._t0 = time.time()
        self._c0 = {k: getattr(self.c, k) for k in _COUNTED}
        return self

    def __exit__(self, *exc):
        d = {k: getattr(self.c, k) - v for k, v in self._c0.items()}
        self.elapsed = time.time() - self._t0
        self.net_bytes = d["net_bytes_proxy"]
        self.delta = d
        self.log.parent.mkdir(parents=True, exist_ok=True)
        new = not self.log.exists()
        with open(self.log, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            row = {k: v for k, v in d.items() if k != "net_bytes_proxy"}
            if not self.log_sh:
                row["sentinel_hub_requests"], row["sentinel_hub_pu"] = 0, 0.0
            w.writerow({
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "stage": self.stage, "platform": self.platform, **row,
                "net_bytes_gdal": d["net_bytes_proxy"], "elapsed_s": round(self.elapsed, 1),
                "note": self.note,
            })
        return False


_ROW_LOCK = threading.Lock()


def append_request_row(stage: str, pu: float, note: str = "", log: Path | None = None) -> None:
    """Append one Sentinel Hub request to the quota log immediately (survives a killed run)."""
    log = log or QUOTA_LOG
    with _ROW_LOCK:
        log.parent.mkdir(parents=True, exist_ok=True)
        new = not log.exists()
        with open(log, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerow({
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": stage,
                "platform": "cdse_sentinelhub", "stac_searches": 0, "cog_opens": 0, "cog_window_reads": 0,
                "decoded_bytes": 0, "net_bytes_gdal": 0, "net_tunnels": 0, "sentinel_hub_requests": 1,
                "sentinel_hub_pu": round(pu, 4), "elapsed_s": 0, "note": note})


def append_ee_row(stage: str, eecu_seconds: float, note: str = "", log: Path | None = None) -> None:
    """One Earth Engine measurement (EECU-seconds from a batch task or a monitoring read) in the quota log."""
    log = log or QUOTA_LOG
    with _ROW_LOCK, open(log, "a", newline="") as f:
        if True:
            csv.DictWriter(f, fieldnames=FIELDS).writerow({
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": stage,
                "platform": "earthengine", "stac_searches": 0, "cog_opens": 0, "cog_window_reads": 0,
                "decoded_bytes": 0, "net_bytes_gdal": 0, "net_tunnels": 0, "sentinel_hub_requests": 0,
                "sentinel_hub_pu": 0, "elapsed_s": 0, "note": note, "eecu_seconds": round(eecu_seconds, 2)})
