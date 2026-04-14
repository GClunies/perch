"""Git status panel showing unstaged, staged, untracked files and commits."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Tree

from perch._bindings import (
    COPY_BINDING,
    FOCUS_BINDING,
    HELP_BINDING,
    PAGE_BINDINGS,
    QUIT_BINDING,
    REFRESH_BINDING,
    TAB_BINDINGS,
    make_nav_bindings,
)
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
    item._staged = staged  # ty: ignore[unresolved-attribute]
    return item


def _make_section_header(title: str, name: str | None = None) -> ListItem:
    """Create a non-selectable section header ListItem."""
    text = Text(f"\n{title}", style="bold")
    item = ListItem(Label(text), classes="section-header", name=name)
    item.disabled = True
    return item


class CommitTree(Tree[str]):
    """Tree widget for commit history. GitPanel handles j/k navigation."""

    can_focus = True
    auto_expand = False  # Expansion managed by GitPanel.toggle_commit

    BINDINGS = [
        Binding("l", "select_cursor", "Select", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    def action_select_cursor(self) -> None:
        """Post NodeSelected without toggling expand/collapse.

        Expansion is handled by GitPanel.toggle_commit via the app's
        CommitToggled handler.  The default Tree.action_select_cursor
        calls _toggle_node before posting, which would conflict.
        """
        node = self.cursor_node
        if node is not None:
            self.post_message(self.NodeSelected(node))

    def action_toggle_node(self) -> None:
        """Route space through NodeSelected so toggle_commit handles it."""
        node = self.cursor_node
        if node is not None:
            self.post_message(self.NodeSelected(node))


class GitPanel(Vertical):
    """Compound widget: ListView (files) + Tree (commits)."""

    can_focus = False  # children receive focus, not the container

    class FileSelected(Message):
        """Posted when a file is selected in the git status panel."""

        def __init__(self, path: str, staged: bool) -> None:
            super().__init__()
            self.path = path
            self.staged = staged

    class CommitHighlighted(Message):
        """Posted when a commit node is highlighted in the tree."""

        def __init__(self, commit_hash: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash

    class CommitFileHighlighted(Message):
        """Posted when a commit-file node is highlighted in the tree."""

        def __init__(self, commit_hash: str, path: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash
            self.path = path

    class CommitToggled(Message):
        """Posted when Enter/l is pressed on a commit node."""

        def __init__(self, commit_hash: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash

    class BranchChanged(Message):
        """Posted when the ref watcher detects a branch change."""

        def __init__(self, branch: str) -> None:
            super().__init__()
            self.branch = branch

    class SelectionRestored(Message):
        """Posted after each data refresh once the selection has been set.

        The app uses this to sync the viewer when the Git tab is active and the
        initial async load completes after the user switched to the tab.
        """

    BINDINGS = [
        QUIT_BINDING,
        Binding("d", "app.toggle_diff", "Diff"),
        REFRESH_BINDING,
        Binding("l", "select_cursor", "Select"),
        COPY_BINDING,
        *make_nav_bindings(),
        *TAB_BINDINGS,
        FOCUS_BINDING,
        *PAGE_BINDINGS,
        HELP_BINDING,
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
        self._commit_page_size: int = 50
        self._commits_loaded: int = 0
        self._loading_more: bool = False
        self._file_list = ListView(id="git-file-list")
        self._commit_tree = CommitTree("Commits", id="git-commit-tree")
        self._commit_tree.show_root = False

    def compose(self) -> ComposeResult:
        yield self._file_list
        yield Label("\nCommits", classes="section-header commits-header")
        yield self._commit_tree

    @property
    def has_focus(self) -> bool:
        """Return True if either child widget has focus."""
        return self._file_list.has_focus or self._commit_tree.has_focus

    def focus_default(self) -> None:
        """Focus the file list and ensure an item is highlighted."""
        self._file_list.focus()
        if self._file_list.index is None:
            # Select the first enabled (non-header) item
            for i, node in enumerate(self._file_list._nodes):
                if isinstance(node, ListItem) and not node.disabled:
                    self._file_list.index = i
                    break

    def on_mount(self) -> None:
        self._file_list.append(_make_section_header("Loading git status..."))
        self._do_refresh()  # initial full refresh
        self.set_interval(5, self._refresh_file_status_worker)  # auto-refresh files
        self._start_ref_watcher()

    # ------------------------------------------------------------------
    # Delegate API
    # ------------------------------------------------------------------

    def highlighted_item_name(self) -> str | None:
        """Return data from whichever internal widget has focus."""
        if self._commit_tree.has_focus:
            node = self._commit_tree.cursor_node
            if node is not None and node.data is not None:
                return node.data
            return None
        # Default to file list
        item = self._file_list.highlighted_child
        if isinstance(item, ListItem) and item.name is not None:
            return item.name
        return None

    def reload(self, new_path: Path) -> None:
        """Switch to a new worktree and refresh everything."""
        self._worktree_root = new_path
        self._expanded_commit = None
        self._commits_loaded = 0
        self._start_ref_watcher()
        self._do_refresh()

    def refresh_files(self) -> None:
        """Refresh file sections only."""
        self._refresh_file_status_worker()

    def refresh_commits(self) -> None:
        """Refresh commit tree only."""
        self._refresh_commits_section()

    def refresh_all(self) -> None:
        """Force-refresh everything."""
        self._do_refresh()

    def activate_current_selection(self) -> bool:
        """Post the appropriate message for the currently selected item.

        Returns True if an item was activated, False if nothing is selected.
        """
        item = self._file_list.highlighted_child
        if not isinstance(item, ListItem) or item.name is None:
            return False
        if item.name.startswith("commit:") or item.name.startswith("commit-file:"):
            return False  # Handled by app.py
        staged = getattr(item, "_staged", False)
        self.post_message(self.FileSelected(path=item.name, staged=staged))
        return True

    # ------------------------------------------------------------------
    # Navigation: j/k/arrow cross-widget boundary handling
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        """Intercept arrow keys to route through cross-boundary navigation.

        ListView and Tree consume up/down before GitPanel bindings can fire,
        so we catch them here and delegate to the same boundary logic as j/k.
        """
        if event.key == "down":
            event.prevent_default()
            event.stop()
            self.action_cursor_down()
        elif event.key == "up":
            event.prevent_default()
            event.stop()
            self.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move down -- transfer focus from file list to tree at boundary."""
        if self._file_list.has_focus:
            if (
                self._file_list.index is not None
                and self._file_list.index >= len(self._file_list) - 1
            ):
                if len(self._commit_tree.root.children) > 0:
                    self._commit_tree.focus()
                    return
            self._file_list.action_cursor_down()
        elif self._commit_tree.has_focus:
            self._commit_tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move up -- transfer focus from tree to file list at boundary."""
        if self._commit_tree.has_focus:
            if self._commit_tree.cursor_line <= 0:
                self._file_list.focus()
                return
            self._commit_tree.action_cursor_up()
        elif self._file_list.has_focus:
            self._file_list.action_cursor_up()

    def action_select_cursor(self) -> None:
        """Forward select to whichever child has focus."""
        if self._commit_tree.has_focus:
            self._commit_tree.action_select_cursor()
        elif self._file_list.has_focus:
            self._file_list.action_select_cursor()

    def action_page_up(self) -> None:
        """Forward page up to the focused child."""
        if self._commit_tree.has_focus:
            self._commit_tree.action_page_up()
        elif self._file_list.has_focus:
            if self._file_list.index is not None:
                page = max(1, self._file_list.scrollable_content_region.height)
                self._file_list.index = max(0, self._file_list.index - page)

    def action_page_down(self) -> None:
        """Forward page down to the focused child."""
        if self._commit_tree.has_focus:
            self._commit_tree.action_page_down()
        elif self._file_list.has_focus:
            if self._file_list.index is not None:
                page = max(1, self._file_list.scrollable_content_region.height)
                self._file_list.index = min(
                    len(self._file_list) - 1, self._file_list.index + page
                )

    # ------------------------------------------------------------------
    # Tree event handling
    # ------------------------------------------------------------------

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Post messages when tree nodes are highlighted.

        Stops propagation so the App-level on_tree_node_highlighted
        (which handles FileTree events) does not also fire.
        """
        event.stop()
        node = event.node
        if node.data is None:
            return
        if node.data.startswith("commit:"):
            commit_hash = node.data.removeprefix("commit:")
            self.post_message(self.CommitHighlighted(commit_hash))
        elif node.data.startswith("commit-file:"):
            parts = node.data.removeprefix("commit-file:").split(":", 1)
            if len(parts) == 2:
                self.post_message(self.CommitFileHighlighted(parts[0], parts[1]))
        elif node.data == "load-more-commits":
            self._load_more_commits()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Post CommitToggled when Enter is pressed on a commit node."""
        node = event.node
        if node.data and node.data.startswith("commit:"):
            commit_hash = node.data.removeprefix("commit:")
            self.post_message(self.CommitToggled(commit_hash))

    # ------------------------------------------------------------------
    # File list event handling
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle file selection in the internal ListView."""
        item = event.item
        if item.name is None:
            return
        if item.name.startswith("commit:") or item.name.startswith("commit-file:"):
            return  # Should not happen in new design, but guard anyway
        staged = getattr(item, "_staged", False)
        self.post_message(self.FileSelected(path=item.name, staged=staged))

    # ------------------------------------------------------------------
    # Refresh logic
    # ------------------------------------------------------------------

    def action_refresh(self) -> None:
        self.refresh_all()

    @work(thread=True)
    def _do_refresh(self) -> None:
        from perch.services.git import get_log, get_status

        try:
            status = get_status(self._worktree_root)
            commits = get_log(self._worktree_root, n=self._commit_page_size)
        except RuntimeError:
            self.app.call_from_thread(self._show_not_git_repo)
            return

        self.app.call_from_thread(self._update_display, status, commits)

    def _show_not_git_repo(self) -> None:
        self._is_git_repo = False
        self._file_list.clear()
        text = Text("Not a git repository", style="bold red")
        self._file_list.append(ListItem(Label(text)))

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

    def _update_display(self, status: GitStatusData, commits: list) -> None:
        """Full refresh: rebuild file list and commit tree."""
        saved_name = self._get_selected_name()
        # Rebuild file list
        self._file_list.clear()
        for item in self._build_file_items(status):
            self._file_list.append(item)
        # Rebuild commit tree
        self._build_commit_nodes(commits)
        self._restore_selection(saved_name)
        self.post_message(self.SelectionRestored())

    def _build_commit_nodes(self, commits: list) -> None:
        """Populate the tree root with commit nodes."""
        self._commit_tree.root.remove_children()
        self._commits_loaded = len(commits)
        for c in commits:
            label = Text()
            label.append(c.hash, style="cyan")
            label.append(f" {c.message}  ")
            label.append(c.author, style="dim")
            label.append(f"  {c.relative_time}", style="dim")
            self._commit_tree.root.add(label, data=f"commit:{c.hash}")
        if len(commits) == self._commit_page_size:
            sentinel_label = Text("\u2500\u2500 more history \u2500\u2500", style="dim")
            self._commit_tree.root.add_leaf(sentinel_label, data="load-more-commits")
        self._expanded_commit = None

    def _get_selected_name(self) -> str | None:
        """Get the name of the currently selected file list item."""
        item = self._file_list.highlighted_child
        if isinstance(item, ListItem) and item.name is not None:
            return item.name
        return None

    def _restore_selection(self, saved_name: str | None) -> None:
        """Restore selection by file name, or select the first enabled item."""
        target: int | None = None
        if saved_name is not None:
            for i, node in enumerate(self._file_list._nodes):
                if isinstance(node, ListItem) and node.name == saved_name:
                    target = i
                    break
        if target is None:
            for i, node in enumerate(self._file_list._nodes):
                if isinstance(node, ListItem) and not node.disabled:
                    target = i
                    break
        if target is not None:
            self._file_list.index = target

    # ------------------------------------------------------------------
    # File-only refresh (5s timer)
    # ------------------------------------------------------------------

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
        """Replace file list contents; commit tree is untouched."""
        saved_name = self._get_selected_name()
        self._file_list.clear()
        for item in self._build_file_items(status):
            self._file_list.append(item)
        self._restore_selection(saved_name)
        self.post_message(self.SelectionRestored())

    # ------------------------------------------------------------------
    # Commit tree refresh (ref watcher triggered)
    # ------------------------------------------------------------------

    @work(thread=True)
    def _refresh_commits_section(self) -> None:
        """Rebuild the commits section in a background thread."""
        from perch.services.git import get_commit_files, get_log

        commits = get_log(self._worktree_root, n=self._commit_page_size)
        expanded = self._expanded_commit
        expanded_files = None
        if expanded and any(c.hash == expanded for c in commits):
            try:
                expanded_files = get_commit_files(self._worktree_root, expanded)
            except RuntimeError:
                expanded = None
        else:
            expanded = None
        self.app.call_from_thread(
            self._apply_commits_update, commits, expanded, expanded_files
        )

    def _apply_commits_update(
        self, commits: list, expanded: str | None, expanded_files: list | None
    ) -> None:
        """Apply commit section rebuild on the main thread."""
        self._commit_tree.root.remove_children()
        self._expanded_commit = expanded
        self._commits_loaded = len(commits)
        for c in commits:
            label = Text()
            label.append(c.hash, style="cyan")
            label.append(f" {c.message}  ")
            label.append(c.author, style="dim")
            label.append(f"  {c.relative_time}", style="dim")
            node = self._commit_tree.root.add(label, data=f"commit:{c.hash}")
            if c.hash == expanded and expanded_files:
                for ef in expanded_files:
                    child_label = Text()
                    style = _STATUS_STYLES.get(ef.status, "")
                    child_label.append(f"{ef.status:<10}", style=style)
                    child_label.append(f" {ef.path}")
                    node.add_leaf(
                        child_label,
                        data=f"commit-file:{c.hash}:{ef.path}",
                    )
                node.expand()
        if len(commits) == self._commit_page_size:
            sentinel_label = Text("\u2500\u2500 more history \u2500\u2500", style="dim")
            self._commit_tree.root.add_leaf(sentinel_label, data="load-more-commits")
        if not expanded:
            self._expanded_commit = None

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_more_commits(self) -> None:
        """Load the next page of commits in a background thread."""
        if self._loading_more:
            return
        self._loading_more = True
        from perch.services.git import get_log

        commits = get_log(
            self._worktree_root, n=self._commit_page_size, skip=self._commits_loaded
        )
        self.app.call_from_thread(self._apply_more_commits, commits)

    def _apply_more_commits(self, commits: list) -> None:
        """Apply loaded commits on the main thread."""
        # Remove the sentinel node
        for node in list(self._commit_tree.root.children):
            if node.data == "load-more-commits":
                node.remove()
                break
        self._commits_loaded += len(commits)
        for c in commits:
            label = Text()
            label.append(c.hash, style="cyan")
            label.append(f" {c.message}  ")
            label.append(c.author, style="dim")
            label.append(f"  {c.relative_time}", style="dim")
            self._commit_tree.root.add(label, data=f"commit:{c.hash}")
        if len(commits) == self._commit_page_size:
            sentinel_label = Text("\u2500\u2500 more history \u2500\u2500", style="dim")
            self._commit_tree.root.add_leaf(sentinel_label, data="load-more-commits")
        self._loading_more = False

    # ------------------------------------------------------------------
    # Toggle commit (accordion, using native Tree expand/collapse)
    # ------------------------------------------------------------------

    def toggle_commit(self, commit_hash: str) -> None:
        """Expand or collapse a commit with accordion behavior."""
        target = None
        for node in self._commit_tree.root.children:
            if node.data == f"commit:{commit_hash}":
                target = node
                break
        if target is None:
            return

        if target.is_expanded:
            target.collapse()
            self._expanded_commit = None
        else:
            # Accordion: collapse previous
            if self._expanded_commit:
                for node in self._commit_tree.root.children:
                    if (
                        node.data == f"commit:{self._expanded_commit}"
                        and node.is_expanded
                    ):
                        node.collapse()
                        break
            # Show loading placeholder and fetch files in background
            target.remove_children()
            target.add_leaf(
                Text("Loading...", style="dim italic"),
                data=f"loading:{commit_hash}",
            )
            target.expand()
            self._expanded_commit = commit_hash
            self._fetch_commit_files(commit_hash, target)

    @work(thread=True)
    def _fetch_commit_files(self, commit_hash: str, target_node) -> None:
        """Fetch commit files in a background thread."""
        from perch.services.git import get_commit_files

        try:
            files = get_commit_files(self._worktree_root, commit_hash)
        except RuntimeError:
            return
        self.app.call_from_thread(
            self._populate_commit_files, commit_hash, target_node, files
        )

    def _populate_commit_files(self, commit_hash: str, target_node, files) -> None:
        """Populate commit tree node with fetched files (runs on main thread)."""
        if self._expanded_commit != commit_hash:
            return  # User collapsed or switched before fetch completed
        target_node.remove_children()
        for f in files:
            style = _STATUS_STYLES.get(f.status, "")
            child_label = Text()
            child_label.append(f"{f.status:<10}", style=style)
            child_label.append(f" {f.path}")
            target_node.add_leaf(
                child_label, data=f"commit-file:{commit_hash}:{f.path}"
            )

    # ------------------------------------------------------------------
    # Ref watcher (unchanged from original)
    # ------------------------------------------------------------------

    def _start_ref_watcher(self) -> None:
        """Start polling git refs for new commits."""
        from perch.services.git import get_current_branch

        try:
            self._watched_branch = get_current_branch(self._worktree_root)
        except RuntimeError:
            return
        self._last_ref_mtime: float | None = None
        self._last_head_mtime: float | None = None
        self._last_packed_mtime: float | None = None
        self._update_ref_mtimes()
        self.set_interval(2.5, self._check_refs)

    def _get_git_dir(self) -> Path:
        """Return the .git directory for the worktree."""
        git_dir = self._worktree_root / ".git"
        if git_dir.is_file():
            content = git_dir.read_text().strip()
            if content.startswith("gitdir: "):
                return Path(content.removeprefix("gitdir: "))
        return git_dir

    def _update_ref_mtimes(self) -> None:
        """Snapshot current mtimes for watched ref files."""
        git_dir = self._get_git_dir()
        ref_file = git_dir / "refs" / "heads" / self._watched_branch
        if ref_file.exists():
            self._last_ref_mtime = ref_file.stat().st_mtime
        else:
            self._last_ref_mtime = None
            head_file = git_dir / "HEAD"
            packed_file = git_dir / "packed-refs"
            self._last_head_mtime = (
                head_file.stat().st_mtime if head_file.exists() else None
            )
            self._last_packed_mtime = (
                packed_file.stat().st_mtime if packed_file.exists() else None
            )

    def _check_refs(self) -> None:
        """Poll ref mtimes and refresh commits if changed."""
        from perch.services.git import get_current_branch

        git_dir = self._get_git_dir()
        ref_file = git_dir / "refs" / "heads" / self._watched_branch
        changed = False
        if ref_file.exists():
            mtime = ref_file.stat().st_mtime
            if mtime != self._last_ref_mtime:
                changed = True
        else:
            head_file = git_dir / "HEAD"
            packed_file = git_dir / "packed-refs"
            head_mtime = head_file.stat().st_mtime if head_file.exists() else None
            packed_mtime = packed_file.stat().st_mtime if packed_file.exists() else None
            if (
                head_mtime != self._last_head_mtime
                or packed_mtime != self._last_packed_mtime
            ):
                changed = True
        if changed:
            try:
                new_branch = get_current_branch(self._worktree_root)
                if new_branch != self._watched_branch:
                    self._watched_branch = new_branch
                    self.post_message(self.BranchChanged(new_branch))
            except RuntimeError:
                pass
            self._update_ref_mtimes()
            self._refresh_commits_section()
