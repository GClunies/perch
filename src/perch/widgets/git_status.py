"""Git status panel showing unstaged, staged, untracked files and recent commits."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, DataTable, Label, Static

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


class GitStatusPanel(VerticalScroll):
    """Displays git status: unstaged/staged/untracked files and recent commits."""

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
        yield Collapsible(Label(""), title="Unstaged Changes", id="git-unstaged")
        yield Collapsible(Label(""), title="Staged Changes", id="git-staged")
        yield Collapsible(Label(""), title="Untracked Files", id="git-untracked")
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
        for cid in ("git-unstaged", "git-staged", "git-untracked", "git-commits"):
            self.query_one(f"#{cid}", Collapsible).display = False

    def _update_display(self, status: GitStatusData, commits: list) -> None:
        header = self.query_one("#git-header", Static)
        header.update("")

        # Unstaged
        section = self.query_one("#git-unstaged", Collapsible)
        section.display = True
        if status.unstaged:
            section.query_one(Label).update(_render_file_list(status.unstaged))
        else:
            section.query_one(Label).update(Text("No unstaged changes", style="dim"))

        # Staged
        section = self.query_one("#git-staged", Collapsible)
        section.display = True
        if status.staged:
            section.query_one(Label).update(_render_file_list(status.staged))
        else:
            section.query_one(Label).update(Text("No staged changes", style="dim"))

        # Untracked
        section = self.query_one("#git-untracked", Collapsible)
        section.display = True
        if status.untracked:
            section.query_one(Label).update(_render_file_list(status.untracked))
        else:
            section.query_one(Label).update(Text("No untracked files", style="dim"))

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

    def action_refresh(self) -> None:
        self._do_refresh()
