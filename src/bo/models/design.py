"""Fixed design constants of the Phase 4 detector, copied from `docs/analysis_plan.md` v1.0.

Every value here is a pre-registered design choice [D] or threshold [P] of the plan; the section is named next
to it. Changing one needs a deviation entry in plan Section 13. Nothing here is a result.
"""

from __future__ import annotations

import pandas as pd

# Plan Section 1 (A70): last imagery month, temporal hold-out H, development period.
D_END = pd.Timestamp("2026-10-01")
H_START = pd.Timestamp("2025-11-01")
DEV_END = pd.Timestamp("2025-10-01")  # last month any fitted quantity may use

# Plan 4.1: five folds, fold 0 locked test fold, folds 1 to 4 development.
N_FOLDS = 5
TEST_FOLD = 0
DEV_FOLDS: tuple[int, ...] = (1, 2, 3, 4)

# Plan 2.4 (A81): detected if p >= theta in at least 2 usable months of the evaluation window.
MIN_DETECTED_MONTHS = 2

# Plan 7.1 (A82): minimum detectable size at fitted recall 0.8.
RECALL_TARGET = 0.8

# Plan 10 (A84): block bootstrap replicates, no interval below n = 10, Bonferroni for the 4 H1 cells.
N_BOOT = 2000
MIN_N_INTERVAL = 10
H1_PRIMARY_CELLS = 4

TECHNOLOGIES: tuple[str, ...] = ("battery", "pv")

# Plan 2.2 and A80: size classes in MW(p), left-closed.
SIZE_CLASS_EDGES: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0, float("inf"))
SIZE_CLASS_LABELS: tuple[str, ...] = ("1-5", "5-20", "20-100", ">=100")
LARGEST_CLASS_MIN_MW = {"battery": 100.0, "pv": 20.0}  # plan 7.1 primary cell

# A80 regions by federal state (full German names as in the queue's `bundesland`).
REGION_OF_STATE = {
    "Schleswig-Holstein": "north", "Hamburg": "north", "Niedersachsen": "north", "Bremen": "north",
    "Mecklenburg-Vorpommern": "north",
    "Brandenburg": "east", "Berlin": "east", "Sachsen": "east", "Sachsen-Anhalt": "east",
    "Thüringen": "east",
    "Bayern": "south", "Baden-Württemberg": "south",
    "Nordrhein-Westfalen": "west", "Hessen": "west", "Rheinland-Pfalz": "west", "Saarland": "west",
}

SEASON_OF_MONTH = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
                   6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}


def bonferroni_level(cells: int, family_level: float = 0.95) -> float:
    """Two-sided interval level after Bonferroni over `cells` primary cells (plan Section 10)."""
    return 1.0 - (1.0 - family_level) / cells


def dev_window(n_months: int = 12) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The development-period analogue of H: the `n_months` months ending at DEV_END (assumption M3)."""
    return DEV_END - pd.DateOffset(months=n_months - 1), DEV_END


def holdout_window() -> tuple[pd.Timestamp, pd.Timestamp]:
    return H_START, D_END
