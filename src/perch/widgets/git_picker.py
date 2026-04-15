"""Git worktree and branch picker modal screen."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
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
        Binding("enter", "select", "Select"),
        Binding("d", "delete", "Delete"),
        Binding("shift+d", "force_delete", "Force Delete"),
        Binding("escape", "cancel", "Cancel"),
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
    #git-picker-hint {
        text-style: dim;
        margin-top: 1;
    }
    """

    def __init__(self, current_worktree: Path) -> None:
        super().__init__()
        self._current_worktree = current_worktree

    def compose(self) -> ComposeResult:
        with Vertical(id="git-picker-container"):
            yield Label("Switch Worktree / Branch", id="git-picker-title")
            yield ListView(id="git-picker-list")
            yield Label(
                "[bold]enter[/] Select · [bold]d[/] Delete · [bold]shift+d[/] Force Delete · [bold]esc[/] Cancel",
                id="git-picker-hint",
            )

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
            list_view.append(ListItem(Label(label), name=f"{_BRANCH_PREFIX}{branch}"))

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

    def action_select(self) -> None:
        """Dismiss with the currently highlighted item."""
        list_view = self.query_one("#git-picker-list", ListView)
        if list_view.highlighted_child is not None:
            self._dismiss_selection(list_view.highlighted_child.name)

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def _get_highlighted_name(self) -> str | None:
        list_view = self.query_one("#git-picker-list", ListView)
        if list_view.highlighted_child is not None:
            return list_view.highlighted_child.name
        return None

    def _is_deletable(self, name: str) -> bool:
        """Return True if the item can be deleted, otherwise notify why not."""
        if name.startswith(_WORKTREE_PREFIX):
            path = name.removeprefix(_WORKTREE_PREFIX)
            if path == str(self._current_worktree):
                self.app.notify("Cannot delete the current worktree", severity="error")
                return False
        elif name.startswith(_BRANCH_PREFIX):
            from perch.services.git import get_current_branch

            try:
                current = get_current_branch(self._current_worktree)
            except RuntimeError:
                current = None
            branch = name.removeprefix(_BRANCH_PREFIX)
            if branch == current:
                self.app.notify("Cannot delete the current branch", severity="error")
                return False
        return True

    def action_delete(self) -> None:
        """Safe-delete the highlighted worktree or branch."""
        self._request_delete(force=False)

    def action_force_delete(self) -> None:
        """Force-delete the highlighted worktree or branch."""
        self._request_delete(force=True)

    def _request_delete(self, *, force: bool) -> None:
        name = self._get_highlighted_name()
        if not name:
            return
        if not self._is_deletable(name):
            return

        from perch.widgets.confirm_screen import ConfirmScreen

        if name.startswith(_WORKTREE_PREFIX):
            path = name.removeprefix(_WORKTREE_PREFIX)
            label = f"worktree {path}"
        else:
            label = f"branch {name.removeprefix(_BRANCH_PREFIX)}"

        prefix = "FORCE delete" if force else "Delete"
        self.app.push_screen(
            ConfirmScreen(f"{prefix} {label}?"),
            lambda confirmed: self._on_delete_confirmed(confirmed, name, force),
        )

    def _on_delete_confirmed(
        self, confirmed: bool | None, name: str, force: bool
    ) -> None:
        if not confirmed:
            return
        self._run_delete(name, force)

    @work(thread=True)
    def _run_delete(self, name: str, force: bool) -> None:
        from perch.services.git import delete_branch, remove_worktree

        try:
            if name.startswith(_WORKTREE_PREFIX):
                path = name.removeprefix(_WORKTREE_PREFIX)
                remove_worktree(self._current_worktree, path, force=force)
                label = f"Worktree {path}"
            else:
                branch = name.removeprefix(_BRANCH_PREFIX)
                delete_branch(self._current_worktree, branch, force=force)
                label = f"Branch {branch}"
        except RuntimeError as e:
            hint = " (press shift+d to force)" if not force else ""
            self.app.call_from_thread(
                self.app.notify, f"{e}{hint}", severity="error", timeout=5
            )
            return

        self.app.call_from_thread(self.app.notify, f"Deleted {label}")
        self.app.call_from_thread(self._load_entries)
