from pathlib import Path
from typing import Iterable

from textual.widgets import DirectoryTree

EXCLUDED_NAMES: set[str] = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "node_modules",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    ".tox",
    ".eggs",
    ".beads",
}


class WorktreeFileTree(DirectoryTree):
    """A directory tree that filters out noise directories."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.name not in EXCLUDED_NAMES
            and not path.name.endswith(".egg-info")
        ]
