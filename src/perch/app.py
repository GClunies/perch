from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, ListItem, ListView, TabbedContent, TabPane

from perch.commands import DiscoveryCommandProvider
from perch.services.editor import open_file
from perch.widgets.file_search import FileSearchScreen
from perch.widgets.file_tree import FileTree
from perch.widgets.git_status import GitPanel
from perch.widgets.github_panel import GitHubPanel
from perch.widgets.splitter import DraggableSplitter
from perch.widgets.viewer import Viewer

_AUTO_SELECT_INTERVAL = 0.15  # seconds between retries
_AUTO_SELECT_MAX_ATTEMPTS = 20  # give up after ~3 seconds


class PerchApp(App):
    CSS_PATH = "app.tcss"
    COMMANDS = App.COMMANDS | {DiscoveryCommandProvider}
    COMMAND_PALETTE_BINDING = "question_mark"

    BINDINGS = [
        ("q", "quit", "Quit"),
        Binding("tab", "focus_next_pane", "Switch Pane", priority=True),
        Binding("left_square_bracket", "prev_tab", "Prev Tab", key_display="["),
        Binding("right_square_bracket", "next_tab", "Next Tab", key_display="]"),
        Binding("f", "toggle_focus_mode", "Focus Mode", show=False),
        Binding("ctrl+p", "file_search", "File Search", show=False),
        Binding("d", "toggle_diff", "Toggle Diff", show=False),
        Binding("s", "toggle_diff_layout", "Diff Layout", show=False),
        Binding("m", "toggle_markdown_preview", "Markdown Preview", show=False),
        Binding("n", "next_diff_file", "Next File", show=False),
        Binding("p", "prev_diff_file", "Prev File", show=False),
        Binding("o", "open_editor", "Open", show=False),
        Binding(
            "question_mark", "command_palette", "Help", key_display="?", priority=True
        ),
    ]

    def __init__(self, worktree_path: Path, editor: str | None = None) -> None:
        super().__init__()
        self.worktree_path = worktree_path
        self.editor = editor
        self._focus_mode = False
        self._branch: str | None = None
        self._files_tab_last_path: Path | None = None
        self._git_tab_first_visit = True
        try:
            from perch.services.git import get_current_branch, get_worktree_root

            git_root = get_worktree_root(worktree_path)
            self._branch = get_current_branch(git_root)
        except (RuntimeError, FileNotFoundError):
            pass

    def watch_theme(self, _value: str | None = None) -> None:
        """Re-render the viewer when the app theme changes."""
        try:
            viewer = self.query_one(Viewer)
        except Exception:
            return
        viewer.refresh_content()

    def on_mount(self) -> None:
        if self._branch:
            self.title = f"perch — {self._branch}"
        else:
            self.title = "perch"
        self.sub_title = str(self.worktree_path)
        self.query_one(TabbedContent).active = "tab-files"
        self._focus_active_tab()
        self._auto_select_done = False
        self._auto_select_attempts = 0
        self.set_timer(_AUTO_SELECT_INTERVAL, self._auto_select_first_file)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            yield Viewer(worktree_root=self.worktree_path, id="left-pane")
            yield DraggableSplitter()
            with TabbedContent(id="sidebar"):
                with TabPane("\uf0c5", id="tab-files"):
                    yield FileTree(self.worktree_path)
                with TabPane("\ue725", id="tab-git"):
                    yield GitPanel(self.worktree_path)
                with TabPane("\uf09b", id="tab-github"):
                    yield GitHubPanel(self.worktree_path)
        yield Footer()

    # ------------------------------------------------------------------
    # Auto-select first file on startup
    # ------------------------------------------------------------------

    def _auto_select_first_file(self) -> None:
        """Find and highlight the first file in the tree after it loads."""
        if self._auto_select_done:
            return

        try:
            tree = self.query_one(FileTree)
            viewer = self.query_one(Viewer)
        except Exception:
            return  # Widget not available (e.g. during shutdown)

        self._auto_select_attempts += 1

        if tree.last_line <= 0:
            if self._auto_select_attempts < _AUTO_SELECT_MAX_ATTEMPTS:
                self.set_timer(_AUTO_SELECT_INTERVAL, self._auto_select_first_file)
            else:
                self._auto_select_done = True
                viewer.show_empty_directory()
            return

        self._auto_select_done = True

        # Bail out if something was already loaded (e.g. user switched tabs)
        if viewer._current_path is not None or viewer._diff_mode:
            return

        for line in range(tree.last_line + 1):
            node = tree.get_node_at_line(line)
            if node is None or node.data is None:
                continue
            path = node.data.path if hasattr(node.data, "path") else node.data
            if isinstance(path, Path) and path.is_file():
                tree.cursor_line = line
                return

        viewer.show_empty_directory()

    # ------------------------------------------------------------------
    # Tree ↔ viewer sync
    # ------------------------------------------------------------------

    def _sync_tree_to_path(self, path: Path) -> None:
        """Move the file tree cursor to the node matching *path*."""
        try:
            tree = self.query_one(FileTree)
        except Exception:
            return
        for line in range(tree.last_line + 1):
            node = tree.get_node_at_line(line)
            if node is None or node.data is None:
                continue
            node_path = node.data.path if hasattr(node.data, "path") else node.data
            if isinstance(node_path, Path) and node_path == path:
                tree.cursor_line = line
                return

    # ------------------------------------------------------------------
    # Event handlers — sidebar selections → viewer
    # ------------------------------------------------------------------

    def on_git_panel_file_selected(
        self, event: GitPanel.FileSelected
    ) -> None:
        """Handle file selection in the git tab — open in viewer."""
        file_path = self.worktree_path / event.path
        viewer = self.query_one(Viewer)
        if file_path.is_file():
            viewer.load_file(file_path)
        else:
            viewer.show_deleted_file_diff(file_path, event.path, staged=event.staged)

    def on_tree_node_highlighted(self, event) -> None:
        """Update the viewer when a tree node is highlighted (cursor moves)."""
        node = event.node
        if node.data is None:
            return
        path = node.data.path if hasattr(node.data, "path") else node.data
        if isinstance(path, Path) and path.is_file():
            self.query_one(Viewer).load_file(path)
            self._files_tab_last_path = path

    def on_directory_tree_file_selected(self, event) -> None:
        """Focus the viewer when a file is selected with enter."""
        viewer = self.query_one(Viewer)
        viewer.load_file(event.path)
        viewer.focus()

    def on_git_panel_commit_selected(
        self, event: GitPanel.CommitSelected
    ) -> None:
        """Handle commit selection in the git tab — show full commit diff."""
        viewer = self.query_one(Viewer)
        viewer.worktree_root = self.worktree_path
        viewer.load_commit_diff(event.commit_hash)

    def on_git_hub_panel_preview_requested(
        self, event: GitHubPanel.PreviewRequested
    ) -> None:
        """Show preview content in the viewer when a PR item is highlighted."""
        if self.query_one(TabbedContent).active != "tab-github":
            return
        viewer = self.query_one(Viewer)
        if event.preview_kind == "pr_body":
            viewer.show_pr_body(event.body, title=event.title)
        elif event.preview_kind == "review":
            viewer.show_review(event.body, title=event.title)
        elif event.preview_kind == "comment":
            viewer.show_review(event.body, title=event.title)
        elif event.preview_kind == "ci_check":
            viewer.show_ci_loading(title=event.title)
            viewer.fetch_ci_log(event.url)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Focus the viewer when an item is explicitly selected (Enter/l)."""
        try:
            if self.query_one(TabbedContent).active == "tab-git":
                self.query_one(Viewer).focus()
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Preview the highlighted item in the viewer when navigating with j/k."""
        try:
            if self.query_one(TabbedContent).active != "tab-git":
                return
        except Exception:
            return
        item = event.item
        if not isinstance(item, ListItem) or item.name is None:
            return
        viewer = self.query_one(Viewer)
        if item.name.startswith("commit:"):
            commit_hash = item.name.removeprefix("commit:")
            viewer.worktree_root = self.worktree_path
            viewer.load_commit_diff(commit_hash)
        else:
            file_path = self.worktree_path / item.name
            staged = getattr(item, "_staged", False)
            if file_path.is_file():
                viewer.load_file(file_path)
            else:
                viewer.show_deleted_file_diff(file_path, item.name, staged=staged)

    def on_git_panel_selection_restored(
        self, event: GitPanel.SelectionRestored
    ) -> None:
        """Sync the viewer after an async git refresh, but only when Git tab is active."""
        try:
            if self.query_one(TabbedContent).active != "tab-git":
                return
            panel = self.query_one(GitPanel)
        except Exception:
            return
        if not panel.activate_current_selection():
            self.query_one(Viewer).show_clean_tree()

    # ------------------------------------------------------------------
    # Tab navigation
    # ------------------------------------------------------------------

    _TAB_ORDER = ["tab-files", "tab-git", "tab-github"]

    def action_next_tab(self) -> None:
        """Switch to the next sidebar tab."""
        tabbed = self.query_one(TabbedContent)
        try:
            idx = self._TAB_ORDER.index(tabbed.active)
        except ValueError:
            idx = -1
        tabbed.active = self._TAB_ORDER[(idx + 1) % len(self._TAB_ORDER)]
        self._focus_active_tab()

    def action_prev_tab(self) -> None:
        """Switch to the previous sidebar tab."""
        tabbed = self.query_one(TabbedContent)
        try:
            idx = self._TAB_ORDER.index(tabbed.active)
        except ValueError:
            idx = 1
        tabbed.active = self._TAB_ORDER[(idx - 1) % len(self._TAB_ORDER)]
        self._focus_active_tab()

    def action_focus_next_pane(self) -> None:
        """Move focus to the other pane."""
        viewer = self.query_one("#left-pane", Viewer)
        if viewer.has_focus:
            self._focus_active_tab()
        else:
            viewer.focus()

    def _focus_active_tab(self) -> None:
        """Focus the first navigable widget inside the active sidebar tab."""
        tabbed = self.query_one(TabbedContent)
        active = tabbed.active

        if active == "tab-files":
            tree = self.query_one(FileTree)
            tree.focus()
            if tree.cursor_line == -1:
                tree.cursor_line = 0
            # Restore the last file viewed in the Files context
            viewer = self.query_one(Viewer)
            if self._files_tab_last_path and self._files_tab_last_path.is_file():
                viewer.load_file(self._files_tab_last_path)
                self._sync_tree_to_path(self._files_tab_last_path)
            else:
                viewer.show_placeholder()
        elif active == "tab-git":
            panel = self.query_one(GitPanel)
            panel.focus()
            if self._git_tab_first_visit or panel.index is None:
                panel._restore_selection(None)
                self._git_tab_first_visit = False
            # Data may still be loading; SelectionRestored will sync the viewer
            # once the async refresh completes. Handle the already-loaded case now.
            if not panel.activate_current_selection():
                self.query_one(Viewer).show_clean_tree()
        elif active == "tab-github":
            github = self.query_one(GitHubPanel)
            github.focus()
            github.activate_current_preview()
        else:
            self.query_one(FileTree).focus()

    # ------------------------------------------------------------------
    # File search
    # ------------------------------------------------------------------

    def action_file_search(self) -> None:
        """Open the fuzzy file search modal."""
        self.push_screen(FileSearchScreen(self.worktree_path), self._on_file_selected)

    def _on_file_selected(self, result: str | None) -> None:
        """Handle the result from the file search modal."""
        if result is not None:
            path = self.worktree_path / result
            if path.is_file():
                self.query_one(Viewer).load_file(path)
                self._files_tab_last_path = path
                self._sync_tree_to_path(path)

    def action_open_editor(self) -> None:
        """Open the currently highlighted file in the external editor."""
        viewer = self.query_one(Viewer)
        if viewer._current_path is not None:
            open_file(self.editor, viewer._current_path, self.worktree_path)

    # ------------------------------------------------------------------
    # Viewer action delegates
    # ------------------------------------------------------------------

    def action_toggle_diff(self) -> None:
        """Toggle diff view in the viewer (command palette entry)."""
        self.query_one(Viewer).action_toggle_diff()

    def action_toggle_diff_layout(self) -> None:
        """Toggle diff layout in the viewer (command palette entry)."""
        self.query_one(Viewer).action_toggle_diff_layout()

    def action_next_diff_file(self) -> None:
        """Jump to the next file in a multi-file diff."""
        self.query_one(Viewer).action_next_diff_file()

    def action_prev_diff_file(self) -> None:
        """Jump to the previous file in a multi-file diff."""
        self.query_one(Viewer).action_prev_diff_file()

    # ------------------------------------------------------------------
    # Focus mode & pane resizing
    # ------------------------------------------------------------------

    def action_toggle_focus_mode(self) -> None:
        """Toggle the sidebar and splitter to give the left pane full width."""
        self._focus_mode = not self._focus_mode
        sidebar = self.query_one("#sidebar", TabbedContent)
        splitter = self.query_one(DraggableSplitter)
        viewer = self.query_one("#left-pane", Viewer)

        if self._focus_mode:
            sidebar.display = False
            splitter.display = False
            viewer.styles.width = "100%"
            viewer.focus()
        else:
            sidebar.display = True
            splitter.display = True
            viewer.styles.width = "75%"
            self._focus_active_tab()

