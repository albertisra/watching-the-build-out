"""Constants taken from the research notes and ``docs/assumptions.md``.

Nothing here is invented: each value names its source.
"""

from __future__ import annotations

from dataclasses import dataclass

# docs/assumptions.md A4: 64 x 64 pixels at 10 m, plausible range 32 to 128.
DEFAULT_CHIP_SIZE = 64
DEFAULT_RES_M = 10.0

# docs/research/sentinel2.md, SCL classes table.
SCL_NO_DATA = 0
SCL_SATURATED = 1
SCL_CAST_SHADOW = 2
SCL_CLOUD_SHADOW = 3
SCL_VEGETATION = 4
SCL_NOT_VEGETATED = 5
SCL_WATER = 6
SCL_UNCLASSIFIED = 7
SCL_CLOUD_MEDIUM = 8
SCL_CLOUD_HIGH = 9
SCL_CIRRUS = 10
SCL_SNOW = 11

# Clear-pixel rules. "scl_456" is the default of docs/assumptions.md A5.
# "scl_4567" and "scl_blacklist" are the alternatives named in A5 and in
# docs/research/sentinel2.md ("keep 2 and 7 candidate-valid", blacklist 0, 1, 3, 8, 9, 10; we also
# drop 11 because the brief excludes snow).
CLEAR_RULES: dict[str, tuple[int, ...]] = {
    "scl_456": (4, 5, 6),
    "scl_4567": (4, 5, 6, 7),
    "scl_blacklist": (2, 4, 5, 6, 7),
}
DEFAULT_CLEAR_RULE = "scl_456"
ALT_CLEAR_RULE = "scl_blacklist"

# docs/research/sentinel2.md fact 13 and 15: baseline 04.00 became operational 2022-01-25 and
# shifts DN by +1000 (BOA_ADD_OFFSET = -1000, quantification 10000).
OFFSET_BASELINE = (4, 0)
BOA_ADD_OFFSET = -1000.0
QUANTIFICATION = 10000.0

# Planetary Computer collection ids (docs/research/access_platforms.md facts 27 to 29).
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_S2 = "sentinel-2-l2a"
PC_S1_RTC = "sentinel-1-rtc"
PC_S1_GRD = "sentinel-1-grd"
S1_NODATA = -32768.0

# Default Sentinel-2 bands for chips: four 10 m bands and two 20 m SWIR bands.
S2_BANDS = ("B02", "B03", "B04", "B08", "B11", "B12")
S2_BANDS_10M = ("B02", "B03", "B04", "B08")


@dataclass(frozen=True)
class ChipConfig:
    size: int = DEFAULT_CHIP_SIZE
    res: float = DEFAULT_RES_M
    clear_rule: str = DEFAULT_CLEAR_RULE
    bands: tuple[str, ...] = S2_BANDS
    speckle: str | None = None  # None, "boxcar3", "lee5"
    pols: tuple[str, ...] = ("vv", "vh")
