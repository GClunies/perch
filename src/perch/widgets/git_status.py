"""Git status panel showing unstaged, staged, untracked files and recent commits."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Collapsible, DataTable, Label, ListItem, ListView, Static

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


def _render_file_list(files: list[GitFile]) -> Text:
    """Render a list of GitFile entries as styled Rich text."""
    text = Text()
    for i, f in enumerate(files):
        if i > 0:
            text.append("\n")
        style = _STATUS_STYLES.get(f.status, "")
        text.append(f"  {f.status:<12}", style=style)
        text.append(f" {f.path}")
    return text


def _make_list_item(f: GitFile) -> ListItem:
    """Create a ListItem for a GitFile entry with styled status + path."""
    style = _STATUS_STYLES.get(f.status, "")
    text = Text()
    text.append(f"{f.status:<12}", style=style)
    text.append(f" {f.path}")
    return ListItem(Label(text), name=f.path)


class GitStatusPanel(VerticalScroll):
    """Displays git status: unstaged/staged/untracked files and recent commits."""

    class FileSelected(Message):
        """Posted when a file is selected in the git status panel."""

        def __init__(self, path: str, staged: bool) -> None:
            super().__init__()
            self.path = path
            self.staged = staged

    BINDINGS = [
        ("r", "refresh", "Refresh"),
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

    def compose(self):
        yield Static("Loading git status...", id="git-header")
        yield Static("Unstaged Changes", classes="section-header")
        yield ListView(id="git-unstaged")
        yield Static("Staged Changes", classes="section-header")
        yield ListView(id="git-staged")
        yield Static("Untracked Files", classes="section-header")
        yield ListView(id="git-untracked")
        yield Collapsible(
            DataTable(id="commits-table"),
            title="Recent Commits",
            id="git-commits",
        )

    def on_mount(self) -> None:
        table = self.query_one("#commits-table", DataTable)
        table.add_columns("Hash", "Message", "Author", "When")
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
        header = self.query_one("#git-header", Static)
        header.update(
            Text("Not a git repository", style="bold red")
        )
        for cid in ("git-unstaged", "git-staged", "git-untracked"):
            self.query_one(f"#{cid}", ListView).display = False
        self.query_one("#git-commits", Collapsible).display = False
        for sh in self.query(".section-header"):
            sh.display = False

    def _save_cursor_state(
        self, lv: ListView
    ) -> tuple[int, str | None]:
        """Save the current cursor index and selected file name for a ListView."""
        index = lv.index or 0
        selected_name: str | None = None
        if lv.index is not None and 0 <= lv.index < len(lv):
            item = lv.children[lv.index]
            if isinstance(item, ListItem) and item.name is not None:
                selected_name = item.name
        return index, selected_name

    def _restore_cursor_state(
        self, lv: ListView, saved_index: int, saved_name: str | None
    ) -> None:
        """Restore cursor position, preferring the previously selected file name."""
        if len(lv) == 0:
            return
        # Try to find the previously selected file by name
        if saved_name is not None:
            for i, child in enumerate(lv.children):
                if isinstance(child, ListItem) and child.name == saved_name:
                    lv.index = i
                    return
        # Fall back to saved index, clamped to valid range
        lv.index = min(saved_index, len(lv) - 1)

    def _update_list_view(
        self,
        lv_id: str,
        files: list[GitFile],
        empty_message: str,
    ) -> None:
        """Update a ListView, preserving cursor position across refresh."""
        lv = self.query_one(f"#{lv_id}", ListView)
        saved_index, saved_name = self._save_cursor_state(lv)
        lv.clear()
        if files:
            for f in files:
                lv.append(_make_list_item(f))
        else:
            lv.append(ListItem(Label(Text(empty_message, style="dim"))))
        self._restore_cursor_state(lv, saved_index, saved_name)

    def _update_display(self, status: GitStatusData, commits: list) -> None:
        header = self.query_one("#git-header", Static)
        header.update("")

        self._update_list_view(
            "git-unstaged", status.unstaged, "No unstaged changes"
        )
        self._update_list_view(
            "git-staged", status.staged, "No staged changes"
        )
        self._update_list_view(
            "git-untracked", status.untracked, "No untracked files"
        )

        # Commits
        commits_section = self.query_one("#git-commits", Collapsible)
        commits_section.display = True
        table = self.query_one("#commits-table", DataTable)
        table.clear()
        for c in commits:
            table.add_row(
                Text(c.hash, style="cyan"),
                c.message,
                c.author,
                Text(c.relative_time, style="dim"),
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle file selection in any of the ListViews."""
        item = event.item
        if item.name is None:
            return
        # Determine if selected from the staged list
        staged = False
        try:
            parent_lv = item.parent
            if parent_lv is not None and parent_lv.id == "git-staged":
                staged = True
        except Exception:
            pass
        self.post_message(self.FileSelected(path=item.name, staged=staged))

    def action_refresh(self) -> None:
        self._do_refresh()
