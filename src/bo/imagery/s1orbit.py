"""Relative orbit from the absolute orbit number, per Sentinel-1 satellite.

relative = (absolute - offset) % 175 + 1. Offsets fitted on Planetary Computer ``sentinel-1-rtc`` items
(``sat:absolute_orbit`` against ``sat:relative_orbit``, 2016 to 2026, every item of each satellite agreed):
S1A 73, S1B 27, S1C 172, S1D 42. S1C changed to 99 after its June 2026 orbit manoeuvre
(docs/research/sentinel1.md fact 9). Scan of every Planetary Computer S1C item over Europe from 2026-06-01 to 2026-06-28
(sat:absolute_orbit against sat:relative_orbit): absolute orbits up to 8258 (2026-06-25 05:55 UTC) follow 172 (this includes
8010 and 8017 on 2026-06-08), from 8264 (2026-06-25 15:31 UTC) they follow 99; no item exists for 8259 to 8263, so 8260
is the boundary. The first version used 8000, which put the 2026-06-08 and 2026-06-25 early passes on the wrong orbit
(review B3). Tracks keep their numbers across the change.
"""

from __future__ import annotations

OFFSETS = {"S1A": 73, "S1B": 27, "S1C": 172, "S1D": 42}
S1C_NEW_OFFSET = 99
S1C_BOUNDARY = 8260


def relative_orbit(satellite: str, absolute_orbit: int) -> int:
    if satellite not in OFFSETS:
        return -1
    off = OFFSETS[satellite]
    if satellite == "S1C" and absolute_orbit >= S1C_BOUNDARY:
        off = S1C_NEW_OFFSET
    return (absolute_orbit - off) % 175 + 1
