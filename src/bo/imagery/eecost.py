"""EECU measurement by batch export to an Earth Engine asset (free asset storage), then clean-up.

Interactive ``computePixels`` calls do not report EECU. The same image is therefore exported once as a small batch task to an
asset under a probe folder and ``batch_eecu_usage_seconds`` is read from the task status. Assets are deleted afterwards.
The project id never appears in logs or results (``eechips.scrub``).
"""

from __future__ import annotations

import time
import uuid

import ee

from .eechips import chip_geometry, project_id, scrub
from .geo import ChipGrid
from .quota import append_ee_row

FOLDER = "bo_probe"


def asset_id(name: str) -> str:
    return f"projects/{project_id()}/assets/{FOLDER}/{name}"


def export_task(image, grid: ChipGrid, name: str):
    l, _, _, t = grid.bounds
    task = ee.batch.Export.image.toAsset(
        image=image, description=name, assetId=asset_id(name), region=chip_geometry(grid),
        crs=f"EPSG:{grid.epsg}", crsTransform=[grid.res, 0, l, 0, -grid.res, t], maxPixels=10**8)
    task.start()
    return task


def wait_eecu(task, timeout_s: int = 900, poll_s: int = 8) -> dict:
    """Poll until the task ends; return state and ``batch_eecu_usage_seconds``."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = ee.data.getTaskStatus(task.id)[0]
        if st["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return {"state": st["state"], "eecu": float(st.get("batch_eecu_usage_seconds", float("nan"))),
                    "error": scrub(str(st.get("error_message", "")))}
        time.sleep(poll_s)
    return {"state": "TIMEOUT", "eecu": float("nan"), "error": ""}


def cleanup_assets(prefix: str, delete=None, lister=None) -> list[str]:
    """Delete every asset in the probe folder whose name starts with ``prefix``; returns the deleted ids."""
    delete = delete or ee.data.deleteAsset
    lister = lister or ee.data.listAssets
    parent = f"projects/{project_id()}/assets/{FOLDER}"
    gone = []
    for a in lister({"parent": parent}).get("assets", []):
        if a["id"].split("/")[-1].startswith(prefix):
            delete(a["id"])
            gone.append(a["id"])
    return gone


def measure(name: str, image, grid: ChipGrid, stage: str, note: str) -> dict:
    res = wait_eecu(export_task(image, grid, name))
    if res["state"] == "COMPLETED":
        append_ee_row(stage, res["eecu"], note)
    return res


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
