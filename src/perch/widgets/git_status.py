"""Git status panel showing unstaged, staged, untracked files and recent commits."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.message import Message
from textual.binding import Binding
from textual.widgets import Label, ListItem, ListView

from perch.models import GitFile, GitStatusData


_STATUS_STYLES: dict[str, str] = {
    "modified": "yellow",
    "added": "green",
    "deleted": "red",
    "renamed": "cyan",
    "copied": "cyan",
    "unmerged": "bold red",
    "type-changed": "magenta",
    "untracked": "dim",
}


def _make_file_item(f: GitFile, staged: bool = False) -> ListItem:
    """Create a ListItem for a GitFile entry with styled status + path."""
    style = _STATUS_STYLES.get(f.status, "")
    text = Text()
    text.append(f"{f.status:<12}", style=style)
    text.append(f" {f.path}")
    item = ListItem(Label(text), name=f.path)
    item._staged = staged  # type: ignore[attr-defined]
    return item


def _make_section_header(title: str, name: str | None = None) -> ListItem:
    """Create a non-selectable section header ListItem."""
    text = Text(f"\n{title}", style="bold")
    item = ListItem(Label(text), classes="section-header", name=name)
    item.disabled = True
    return item


class GitPanel(ListView):
    """Displays git status: unstaged/staged/untracked files and recent commits."""

    class FileSelected(Message):
        """Posted when a file is selected in the git status panel."""

        def __init__(self, path: str, staged: bool) -> None:
            super().__init__()
            self.path = path
            self.staged = staged

    class SelectionRestored(Message):
        """Posted after each data refresh once the selection has been set.

        The app uses this to sync the viewer when the Git tab is active and the
        initial async load completes after the user switched to the tab.
        """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        Binding("f", "app.toggle_focus_mode", "Focus"),
        Binding("j", "cursor_down", "Navigate", key_display="hjkl/\u2190\u2193\u2191\u2192"),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("l", "select_cursor", "Select", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    def __init__(
        self,
        worktree_root: Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._worktree_root = worktree_root
        self._is_git_repo = True
        self._expanded_commit: str | None = None

    def on_mount(self) -> None:
        self.append(_make_section_header("Loading git status..."))
        self._do_refresh()  # initial full refresh
        self.set_interval(5, self._refresh_file_status_worker)  # auto-refresh files only

    @work(thread=True)
    def _do_refresh(self) -> None:
        from perch.services.git import get_log, get_status

        try:
            status = get_status(self._worktree_root)
            commits = get_log(self._worktree_root)
        except RuntimeError:
            self.app.call_from_thread(self._show_not_git_repo)
            return

        self.app.call_from_thread(self._update_display, status, commits)

    def _show_not_git_repo(self) -> None:
        self._is_git_repo = False
        self.clear()
        text = Text("Not a git repository", style="bold red")
        self.append(ListItem(Label(text)))

    def _build_file_items(self, status: GitStatusData) -> list[ListItem]:
        """Build the file section ListItems (unstaged, staged, untracked)."""
        items: list[ListItem] = []
        items.append(_make_section_header("Unstaged Changes"))
        if status.unstaged:
            for f in status.unstaged:
                items.append(_make_file_item(f, staged=False))
        else:
            item = ListItem(Label(Text("  No unstaged changes", style="dim")))
            item.disabled = True
            items.append(item)
        items.append(_make_section_header("Staged Changes"))
        if status.staged:
            for f in status.staged:
                items.append(_make_file_item(f, staged=True))
        else:
            item = ListItem(Label(Text("  No staged changes", style="dim")))
            item.disabled = True
            items.append(item)
        items.append(_make_section_header("Untracked Files"))
        if status.untracked:
            for f in status.untracked:
                items.append(_make_file_item(f, staged=False))
        else:
            item = ListItem(Label(Text("  No untracked files", style="dim")))
            item.disabled = True
            items.append(item)
        return items

    @work(thread=True)
    def _refresh_file_status_worker(self) -> None:
        """Background worker to refresh file sections only."""
        from perch.services.git import get_status

        try:
            status = get_status(self._worktree_root)
        except RuntimeError:
            return
        self.app.call_from_thread(self._update_file_sections, status)

    def _update_file_sections(self, status: GitStatusData) -> None:
        """Replace file sections (above section-commits header), keep commits intact."""
        boundary = None
        for i, node in enumerate(self._nodes):
            if isinstance(node, ListItem) and node.name == "section-commits":
                boundary = i
                break
        if boundary is None:
            return  # Commits section not built yet

        saved_name = self._get_selected_name()

        # Collect and remove items before the boundary
        items_to_remove = [self._nodes[i] for i in range(boundary)]
        for item in items_to_remove:
            item.remove()

        # Build and insert new file sections
        new_items = self._build_file_items(status)
        for j, item in enumerate(new_items):
            self.insert(j, [item])

        self._restore_selection(saved_name)
        self.post_message(self.SelectionRestored())

    def _update_display(self, status: GitStatusData, commits: list) -> None:
        saved_name = self._get_selected_name()
        self.clear()
        for item in self._build_file_items(status):
            self.append(item)
        # Recent commits
        self.append(_make_section_header("Recent Commits", name="section-commits"))
        for c in commits:
            text = Text()
            text.append("\u25b8 ")
            text.append(c.hash, style="cyan")
            text.append(f" {c.message}  ")
            text.append(c.author, style="dim")
            text.append(f"  {c.relative_time}", style="dim")
            self.append(ListItem(Label(text), name=f"commit:{c.hash}"))
        self._restore_selection(saved_name)
        self.post_message(self.SelectionRestored())

    def _get_selected_name(self) -> str | None:
        """Get the file name of the currently selected item."""
        item = self.highlighted_child
        if isinstance(item, ListItem) and item.name is not None:
            return item.name
        return None

    def _restore_selection(self, saved_name: str | None) -> None:
        """Restore selection by file name, or select the first enabled item."""
        if saved_name is not None:
            for i, node in enumerate(self._nodes):
                if isinstance(node, ListItem) and node.name == saved_name:
                    self.index = i
                    return
        # Select first enabled item
        for i, node in enumerate(self._nodes):
            if isinstance(node, ListItem) and not node.disabled:
                self.index = i
                return

    def activate_current_selection(self) -> bool:
        """Post the appropriate message for the currently selected item.

        Returns True if an item was activated, False if nothing is selected.
        """
        item = self.highlighted_child
        if not isinstance(item, ListItem) or item.name is None:
            return False
        if item.name.startswith("commit:") or item.name.startswith("commit-file:"):
            return False  # Handled by app.py
        staged = getattr(item, "_staged", False)
        self.post_message(self.FileSelected(path=item.name, staged=staged))
        return True

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle file selection."""
        item = event.item
        if item.name is None:
            return
        if item.name.startswith("commit:") or item.name.startswith("commit-file:"):
            return  # Handled by app.py
        staged = getattr(item, "_staged", False)
        self.post_message(self.FileSelected(path=item.name, staged=staged))

    def _page_size(self) -> int:
        """Return the number of items visible in the viewport."""
        return max(1, self.scrollable_content_region.height)

    def action_page_up(self) -> None:
        """Move selection up by a page."""
        if self.index is not None:
            self.index = max(0, self.index - self._page_size())

    def action_page_down(self) -> None:
        """Move selection down by a page."""
        if self.index is not None:
            self.index = min(len(self) - 1, self.index + self._page_size())

    def action_refresh(self) -> None:
        self._do_refresh()

    def toggle_commit(self, commit_hash: str) -> None:
        """Expand or collapse a commit's file list (accordion pattern)."""
        if self._expanded_commit == commit_hash:
            self._collapse_commit(commit_hash)
            self._expanded_commit = None
        else:
            if self._expanded_commit is not None:
                self._collapse_commit(self._expanded_commit)
            self._expand_commit(commit_hash)
            self._expanded_commit = commit_hash

    def _expand_commit(self, commit_hash: str) -> None:
        """Insert child file items below the commit item."""
        from perch.services.git import get_commit_files

        commit_idx = None
        for i, node in enumerate(self._nodes):
            if isinstance(node, ListItem) and node.name == f"commit:{commit_hash}":
                commit_idx = i
                break
        if commit_idx is None:
            return

        self._set_commit_chevron(commit_idx, expanded=True)

        try:
            files = get_commit_files(self._worktree_root, commit_hash)
        except RuntimeError:
            return

        for j, f in enumerate(files):
            text = Text()
            text.append("  ")  # indent
            style = _STATUS_STYLES.get(f.status, "")
            text.append(f"{f.status:<10}", style=style)
            text.append(f" {f.path}")
            child = ListItem(
                Label(text),
                name=f"commit-file:{commit_hash}:{f.path}",
            )
            self.insert(commit_idx + 1 + j, [child])

    def _collapse_commit(self, commit_hash: str) -> None:
        """Remove child file items for a commit."""
        prefix = f"commit-file:{commit_hash}:"
        to_remove = [
            node for node in self._nodes
            if isinstance(node, ListItem) and node.name and node.name.startswith(prefix)
        ]
        for node in to_remove:
            node.remove()

        for i, node in enumerate(self._nodes):
            if isinstance(node, ListItem) and node.name == f"commit:{commit_hash}":
                self._set_commit_chevron(i, expanded=False)
                break

    def _set_commit_chevron(self, index: int, expanded: bool) -> None:
        """Update the chevron indicator on a commit item."""
        node = self._nodes[index]
        if not isinstance(node, ListItem) or not node.name:
            return
        label = node.query_one(Label)
        # Access the internal content stored by Static (name-mangled __content)
        text = getattr(label, "_Static__content", None)
        if not isinstance(text, Text):
            return
        plain = text.plain
        if not plain.startswith(("\u25b8 ", "\u25be ")):
            return
        chevron = "\u25be " if expanded else "\u25b8 "
        new_text = Text()
        new_text.append(chevron)
        new_text.append(plain[2:])
        label.update(new_text)
