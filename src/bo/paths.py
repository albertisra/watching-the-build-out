"""Repository paths, built with pathlib relative to the repository root (KICKOFF rule 8).

Large data folders under ``data/`` are symbolic links to ``~/Data/Power_Grid/``.
Never hard-code absolute paths elsewhere; import them from here.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA = REPO_ROOT / "data"
RAW = DATA / "raw"  # immutable downloads (symlink)
CHIPS = DATA / "chips"  # cached image chips (symlink)
PROCESSED = DATA / "processed"  # rebuildable derived data (symlink)
CHECKPOINTS = DATA / "checkpoints"  # model checkpoints (symlink)
LABELS = DATA / "labels"  # author labels, kept inside the repository

RESULTS = REPO_ROOT / "results"
FIGURES = REPO_ROOT / "figures"
DOCS = REPO_ROOT / "docs"

SYMLINKED = (RAW, CHIPS, PROCESSED, CHECKPOINTS)

# Fixed seed used by every stochastic step unless a config overrides it.
SEED = 20261112
