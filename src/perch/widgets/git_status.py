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


class GitStatusPanel(ListView):
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

    BINDINGS = [
        ("r", "refresh", "Refresh"),
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

        # Restore selection
        self._restore_selection(saved_name)

    def _get_selected_name(self) -> str | None:
        """Get the file name of the currently selected item."""
        if self.index is not None and 0 <= self.index < len(self):
            item = self.children[self.index]
            if isinstance(item, ListItem) and item.name is not None:
                return item.name
        return None

    def _restore_selection(self, saved_name: str | None) -> None:
        """Restore selection by file name, or select the first enabled item."""
        if saved_name is not None:
            for i, child in enumerate(self.children):
                if isinstance(child, ListItem) and child.name == saved_name:
                    self.index = i
                    return
        # Select first enabled item
        for i, child in enumerate(self.children):
            if isinstance(child, ListItem) and not child.disabled:
                self.index = i
                return

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

    def action_refresh(self) -> None:
        self._do_refresh()
