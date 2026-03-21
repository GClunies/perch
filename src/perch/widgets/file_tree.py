from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable

from rich.style import Style
from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.widgets import DirectoryTree
from textual.widgets._tree import Tree, TreeNode

ALWAYS_EXCLUDED: set[str] = {
    ".git",
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


class FileTree(DirectoryTree):
    """A directory tree that filters out noise directories."""

    ICON_FILE = "󰈙 "
    ICON_NODE = "󰉋 "
    ICON_NODE_EXPANDED = "\U000f0770 "

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        Binding("ctrl+p", "app.file_search", "Search"),
        Binding("o", "app.open_editor", "Open"),
        Binding("f", "app.toggle_focus_mode", "Focus"),
        Binding("right", "expand_node", "Expand", show=False),
        Binding("left", "collapse_node", "Collapse", show=False),
        Binding("l", "expand_node", "Expand", show=False),
        Binding("h", "collapse_node", "Collapse", show=False),
        Binding(
            "j", "cursor_down", "Navigate", key_display="hjkl/\u2190\u2193\u2191\u2192"
        ),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    def action_expand_node(self) -> None:
        """Expand the currently highlighted folder node."""
        node = self.cursor_node
        if node is not None and node._allow_expand and not node.is_expanded:
            node.expand()

    def action_collapse_node(self) -> None:
        """Collapse the currently highlighted folder node."""
        node = self.cursor_node
        if node is not None and node._allow_expand and node.is_expanded:
            if node is self.root:
                return  # Root is the worktree anchor — never collapse it
            node.collapse()
        elif node is not None and node.parent is not None:
            parent = node.parent
            if parent is self.root:
                return  # Don't collapse the root by navigating up
            self.select_node(parent)
            parent.collapse()

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        """Re-expand the root immediately if it is ever collapsed (e.g. via click)."""
        if event.node is self.root:
            self.root.expand()

    def _page_size(self) -> int:
        """Return the number of visible lines in the tree viewport."""
        return max(1, self.scrollable_content_region.height)

    def action_page_up(self) -> None:
        """Move cursor up by a page."""
        self.cursor_line = max(0, self.cursor_line - self._page_size())

    def action_page_down(self) -> None:
        """Move cursor down by a page."""
        self.cursor_line = min(self.last_line, self.cursor_line + self._page_size())

    def action_refresh(self) -> None:
        """Re-scan the filesystem."""
        self.reload()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._git_status: dict[str, str] = {}
        self._ignored_paths: set[Path] = set()
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
        """Apply fetched git status and reload the tree structure."""
        self._git_status = status
        self.reload()

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        path_list = [p for p in paths if p.name not in ALWAYS_EXCLUDED]
        if not path_list:
            return path_list
        try:
            from perch.services.git import get_ignored_paths

            self._ignored_paths |= get_ignored_paths(Path(self.path), path_list)
        except Exception:
            pass
        return path_list

    def _is_dimmed(self, path: Path) -> bool:
        """Return True if the path is gitignored or a dotfile/dotdir."""
        if path.name.startswith("."):
            return True
        return path in self._ignored_paths

    def render_label(self, node: TreeNode, base_style: Style, style: Style) -> Text:
        label = super().render_label(node, base_style, style)

        path = node.data.path if hasattr(node.data, "path") else node.data
        if node.data is None or not isinstance(path, Path):
            return label

        # Dim gitignored and hidden entries
        if self._is_dimmed(path):
            label.stylize("dim")
            return label

        # Git status indicators (files only)
        if node._allow_expand:
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
