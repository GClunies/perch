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


def _make_section_header(title: str) -> ListItem:
    """Create a non-selectable section header ListItem."""
    text = Text(f"\n{title}", style="bold")
    item = ListItem(Label(text), classes="section-header")
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

    class CommitSelected(Message):
        """Posted when a commit is selected in the git status panel."""

        def __init__(self, commit_hash: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash

    class SelectionRestored(Message):
        """Posted after each data refresh once the selection has been set.

        The app uses this to sync the viewer when the Git tab is active and the
        initial async load completes after the user switched to the tab.
        """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        Binding("c", "copy", "Copy Path"),
        Binding("f", "app.toggle_focus_mode", "Focus"),
        Binding("j", "cursor_down", "Down", show=False),
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

    def _on_list_item__child_clicked(self, event: ListItem._ChildClicked) -> None:
        """Guard against stale item references after an auto-refresh."""
        try:
            super()._on_list_item__child_clicked(event)
        except ValueError:
            pass  # Item was replaced by a concurrent refresh

    def on_mount(self) -> None:
        self.append(_make_section_header("Loading git status..."))
        self._do_refresh()
        self.set_interval(5, self._do_refresh)

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

    def _update_display(self, status: GitStatusData, commits: list) -> None:
        # Save current selection
        saved_name = self._get_selected_name()

        self.clear()

        # Unstaged
        self.append(_make_section_header("Unstaged Changes"))
        if status.unstaged:
            for f in status.unstaged:
                self.append(_make_file_item(f, staged=False))
        else:
            item = ListItem(Label(Text("  No unstaged changes", style="dim")))
            item.disabled = True
            self.append(item)

        # Staged
        self.append(_make_section_header("Staged Changes"))
        if status.staged:
            for f in status.staged:
                self.append(_make_file_item(f, staged=True))
        else:
            item = ListItem(Label(Text("  No staged changes", style="dim")))
            item.disabled = True
            self.append(item)

        # Untracked
        self.append(_make_section_header("Untracked Files"))
        if status.untracked:
            for f in status.untracked:
                self.append(_make_file_item(f, staged=False))
        else:
            item = ListItem(Label(Text("  No untracked files", style="dim")))
            item.disabled = True
            self.append(item)

        # Recent commits
        self.append(_make_section_header("Recent Commits"))
        for c in commits:
            text = Text()
            text.append(c.hash, style="cyan")
            text.append(f" {c.message}  ")
            text.append(c.author, style="dim")
            text.append(f"  {c.relative_time}", style="dim")
            item = ListItem(Label(text), name=f"commit:{c.hash}")
            self.append(item)

        # Restore selection and notify the app so it can sync the viewer
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
        if item.name.startswith("commit:"):
            commit_hash = item.name.removeprefix("commit:")
            self.post_message(self.CommitSelected(commit_hash=commit_hash))
        else:
            staged = getattr(item, "_staged", False)
            self.post_message(self.FileSelected(path=item.name, staged=staged))
        return True

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle file or commit selection."""
        item = event.item
        if item.name is None:
            return
        if item.name.startswith("commit:"):
            commit_hash = item.name.removeprefix("commit:")
            self.post_message(self.CommitSelected(commit_hash=commit_hash))
        else:
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

    def action_copy(self) -> None:
        """Copy the highlighted item's path or commit hash to clipboard."""
        item = self.highlighted_child
        if not isinstance(item, ListItem) or item.name is None:
            return
        if item.name.startswith("commit:"):
            value = item.name.removeprefix("commit:")
            self.app.copy_to_clipboard(value)
            self.app.notify(f"Copied: {value}")
        else:
            abs_path = str(self._worktree_root / item.name)
            self.app.copy_to_clipboard(abs_path)
            self.app.notify(f"Copied: {abs_path}")

    def _update_copy_binding(self) -> None:
        """Update the copy binding description based on the highlighted item."""
        item = self.highlighted_child
        is_commit = (
            isinstance(item, ListItem)
            and item.name is not None
            and item.name.startswith("commit:")
        )
        desc = "Copy Hash" if is_commit else "Copy Path"
        self._bindings.bind("c", "copy", desc)
        try:
            self.screen.refresh_bindings()
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self._update_copy_binding()

    def action_refresh(self) -> None:
        self._do_refresh()
