"""Locations of the source data and the data lake; both live outside the repository."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def source_dir() -> Path:
    return Path(os.environ.get("VERA_DATA") or REPO.parent / "data")


def lake_dir() -> Path:
    return Path(os.environ.get("VERA_LAKE") or REPO.parent / "data_lake")


def ensure_outside_repo(path: Path) -> Path:
    """Refuse any data location inside the repository."""
    resolved = path.resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise ValueError("data and the data lake must live outside the repository")
    return resolved
