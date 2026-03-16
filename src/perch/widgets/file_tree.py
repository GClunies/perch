from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable

from rich.style import Style
from rich.text import Text
from textual import work
from textual.widgets import DirectoryTree
from textual.widgets._tree import TreeNode

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

# Maps git status labels to (short code, color) for tree indicators.
# Colors match _STATUS_STYLES in git_status.py.
_GIT_INDICATORS: dict[str, tuple[str, str]] = {
    "modified": ("M", "yellow"),
    "added": ("A", "green"),
    "deleted": ("D", "red"),
    "renamed": ("R", "cyan"),
    "copied": ("C", "cyan"),
    "unmerged": ("U", "bold red"),
    "type-changed": ("T", "magenta"),
    "untracked": ("?", "dim"),
}


class WorktreeFileTree(DirectoryTree):
    """A directory tree that filters out noise directories."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._git_status: dict[str, str] = {}
        self._stop_watching = threading.Event()

    def on_mount(self) -> None:
        self._watch_filesystem()

    def on_unmount(self) -> None:
        self._stop_watching.set()

    @work(thread=True)
    def _watch_filesystem(self) -> None:
        """Watch the worktree for filesystem changes and refresh git status."""
        from perch.services.git import get_status_dict

        # Initial status refresh
        try:
            status = get_status_dict(Path(self.path))
            self.app.call_from_thread(self._apply_git_status, status)
        except RuntimeError:
            return

        # Watch for changes and re-fetch status on each change set
        try:
            import watchfiles

            for _changes in watchfiles.watch(
                self.path,
                stop_event=self._stop_watching,
            ):
                try:
                    status = get_status_dict(Path(self.path))
                    self.app.call_from_thread(self._apply_git_status, status)
                except RuntimeError:
                    pass
        except Exception:
            pass

    def _apply_git_status(self, status: dict[str, str]) -> None:
        """Apply fetched git status and re-render the tree."""
        self._git_status = status
        self.root.refresh()

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.name not in EXCLUDED_NAMES
            and not path.name.endswith(".egg-info")
        ]

    def render_label(
        self, node: TreeNode, base_style: Style, style: Style
    ) -> Text:
        label = super().render_label(node, base_style, style)

        if node._allow_expand or node.data is None:
            return label

        path = node.data.path if hasattr(node.data, "path") else node.data
        if not isinstance(path, Path):
            return label

        try:
            rel = path.relative_to(self.path)
        except ValueError:
            return label

        rel_str = str(rel)
        status = self._git_status.get(rel_str)
        if status is None:
            return label

        indicator = _GIT_INDICATORS.get(status)
        if indicator is None:
            return label

        code, color = indicator
        label.append(f" {code}", style=color)
        return label
