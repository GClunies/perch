"""Git worktree and branch picker modal screen."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from perch.models import Worktree

# Return value prefixes to distinguish selection types
_WORKTREE_PREFIX = "worktree:"
_BRANCH_PREFIX = "branch:"


class GitPickerScreen(ModalScreen[str | None]):
    """Modal screen for selecting a git worktree or branch to switch to."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    GitPickerScreen {
        align: center middle;
    }
    #git-picker-container {
        width: 80;
        max-height: 24;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #git-picker-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #git-picker-list {
        height: 1fr;
    }
    """

    def __init__(self, current_worktree: Path) -> None:
        super().__init__()
        self._current_worktree = current_worktree

    def compose(self) -> ComposeResult:
        with Vertical(id="git-picker-container"):
            yield Label("Switch Worktree / Branch", id="git-picker-title")
            yield ListView(id="git-picker-list")

    def on_mount(self) -> None:
        self._load_entries()

    @work(thread=True)
    def _load_entries(self) -> None:
        from perch.services.git import (
            get_branches,
            get_current_branch,
            get_worktrees,
        )

        worktrees = get_worktrees(self._current_worktree)
        branches = get_branches(self._current_worktree)
        try:
            current_branch = get_current_branch(self._current_worktree)
        except RuntimeError:
            current_branch = None
        self.app.call_from_thread(
            self._populate_list, worktrees, branches, current_branch
        )

    def _populate_list(
        self,
        worktrees: list[Worktree],
        branches: list[str],
        current_branch: str | None,
    ) -> None:
        list_view = self.query_one("#git-picker-list", ListView)
        list_view.clear()
        current_path = str(self._current_worktree)

        # Build a map of branch -> worktree for deduplication
        branch_to_worktree: dict[str, Worktree] = {}
        for wt in worktrees:
            if wt.branch:
                branch_to_worktree[wt.branch] = wt

        # Single unified list: worktrees take priority over branches
        seen_branches: set[str] = set()

        # Add worktree entries first
        for wt in worktrees:
            branch = wt.branch or f"(detached {wt.head[:7]})"
            is_current = wt.path == current_path
            marker = " \u2190 current" if is_current else ""
            label = f"{branch}  {wt.path}{marker}"
            list_view.append(
                ListItem(Label(label), name=f"{_WORKTREE_PREFIX}{wt.path}")
            )
            if wt.branch:
                seen_branches.add(wt.branch)

        # Add branches not already represented by a worktree
        for branch in branches:
            if branch in seen_branches:
                continue
            is_current = branch == current_branch
            marker = " \u2190 current" if is_current else ""
            label = f"{branch}{marker}"
            list_view.append(
                ListItem(Label(label), name=f"{_BRANCH_PREFIX}{branch}")
            )

    def _dismiss_selection(self, name: str | None) -> None:
        """Dismiss with the selected item, skipping current worktree."""
        if not name:
            self.dismiss(None)
            return
        # Don't switch if user selected the current worktree
        if name.startswith(_WORKTREE_PREFIX):
            path = name.removeprefix(_WORKTREE_PREFIX)
            if path == str(self._current_worktree):
                self.dismiss(None)
                return
        self.dismiss(name)

    @on(ListView.Selected, "#git-picker-list")
    def _on_selected(self, event: ListView.Selected) -> None:
        self._dismiss_selection(event.item.name)

    def key_enter(self) -> None:
        """Dismiss with the currently highlighted item."""
        list_view = self.query_one("#git-picker-list", ListView)
        if list_view.highlighted_child is not None:
            self._dismiss_selection(list_view.highlighted_child.name)

    def action_cancel(self) -> None:
        self.dismiss(None)
