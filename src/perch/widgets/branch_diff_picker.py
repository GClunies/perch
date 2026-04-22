"""Picker modal for selecting the base commit of a branch diff."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from perch.models import Commit


class BranchDiffPickerScreen(ModalScreen[str | None]):
    """Modal for picking the base ref used by the branch diff view.

    Dismisses with a ref string (SHA, "HEAD", or the merge-base SHA) or
    None when cancelled.
    """

    BINDINGS = [
        Binding("enter", "select", "Select"),
        Binding("h", "pick_head", "HEAD"),
        Binding("m", "pick_merge_base", "Merge-Base"),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    BranchDiffPickerScreen {
        align: center middle;
    }
    #branch-diff-picker-container {
        width: 90;
        max-height: 26;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #branch-diff-picker-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #branch-diff-picker-list {
        height: 1fr;
    }
    #branch-diff-picker-hint {
        text-style: dim;
        margin-top: 1;
    }
    """

    _HEAD_NAME = "ref:HEAD"
    _MERGE_BASE_PREFIX = "ref:merge-base:"
    _COMMIT_PREFIX = "ref:commit:"

    def __init__(self, worktree_path: Path) -> None:
        super().__init__()
        self._worktree_path = worktree_path
        self._merge_base_sha: str | None = None
        self._base_branch: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="branch-diff-picker-container"):
            yield Label("Diff from…", id="branch-diff-picker-title")
            yield ListView(id="branch-diff-picker-list")
            yield Label(
                "[bold]h[/] HEAD · [bold]m[/] merge-base · "
                "[bold]enter[/] Select · [bold]esc[/] Cancel",
                id="branch-diff-picker-hint",
            )

    def on_mount(self) -> None:
        self._load_entries()

    @work(thread=True)
    def _load_entries(self) -> None:
        from perch.services.git import (
            get_commits_since,
            get_merge_base,
            resolve_ref,
        )

        merge_base = get_merge_base(self._worktree_path)
        base_branch, base_sha = merge_base if merge_base else (None, None)
        head_sha = resolve_ref(self._worktree_path, "HEAD")
        commits = get_commits_since(self._worktree_path, base_sha, limit=50)
        self.app.call_from_thread(
            self._populate_list, base_branch, base_sha, head_sha, commits
        )

    def _populate_list(
        self,
        base_branch: str | None,
        base_sha: str | None,
        head_sha: str | None,
        commits: list[Commit],
    ) -> None:
        self._base_branch = base_branch
        self._merge_base_sha = base_sha
        list_view = self.query_one("#branch-diff-picker-list", ListView)
        list_view.clear()

        head_label = f"HEAD ({head_sha[:7]})" if head_sha else "HEAD"
        list_view.append(
            ListItem(Label(f"[bold][h][/] {head_label}"), name=self._HEAD_NAME)
        )

        if base_branch and base_sha:
            list_view.append(
                ListItem(
                    Label(
                        f"[bold][m][/] merge-base with {base_branch} ({base_sha[:7]})"
                    ),
                    name=f"{self._MERGE_BASE_PREFIX}{base_sha}",
                )
            )
        else:
            list_view.append(
                ListItem(
                    Label("[dim][m] merge-base (default branch not found)[/]"),
                    name=f"{self._MERGE_BASE_PREFIX}",
                )
            )

        list_view.append(ListItem(Label("[dim]── commits ──[/]"), name="separator"))

        for commit in commits:
            label = f"{commit.hash}  {commit.message}  [dim]{commit.relative_time}[/]"
            list_view.append(
                ListItem(Label(label), name=f"{self._COMMIT_PREFIX}{commit.hash}")
            )

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _dismiss_name(self, name: str | None) -> None:
        if not name or name == "separator":
            return
        if name == self._HEAD_NAME:
            self.dismiss("HEAD")
            return
        if name.startswith(self._MERGE_BASE_PREFIX):
            sha = name.removeprefix(self._MERGE_BASE_PREFIX)
            if not sha:
                self.app.notify(
                    "No default branch detected — cannot compute merge-base",
                    severity="warning",
                )
                return
            self.dismiss(sha)
            return
        if name.startswith(self._COMMIT_PREFIX):
            self.dismiss(name.removeprefix(self._COMMIT_PREFIX))

    @on(ListView.Selected, "#branch-diff-picker-list")
    def _on_selected(self, event: ListView.Selected) -> None:
        self._dismiss_name(event.item.name)

    def action_select(self) -> None:
        list_view = self.query_one("#branch-diff-picker-list", ListView)
        if list_view.highlighted_child is not None:
            self._dismiss_name(list_view.highlighted_child.name)

    def action_pick_head(self) -> None:
        self.dismiss("HEAD")

    def action_pick_merge_base(self) -> None:
        if self._merge_base_sha is None:
            self.app.notify(
                "No default branch detected — cannot compute merge-base",
                severity="warning",
            )
            return
        self.dismiss(self._merge_base_sha)

    def action_cancel(self) -> None:
        self.dismiss(None)
