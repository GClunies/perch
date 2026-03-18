from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, TabbedContent, TabPane

from perch.commands import DiscoveryCommandProvider
from perch.services.editor import open_file
from perch.widgets.file_search import FileSearchScreen
from perch.widgets.file_tree import WorktreeFileTree
from perch.widgets.git_status import GitStatusPanel
from perch.widgets.github_panel import GitHubPanel
from perch.widgets.splitter import DraggableSplitter
from perch.widgets.viewer import Viewer


class PerchApp(App):
    CSS_PATH = "app.tcss"
    COMMANDS = App.COMMANDS | {DiscoveryCommandProvider}
    COMMAND_PALETTE_BINDING = "question_mark"

    BINDINGS = [
        ("q", "quit", "Quit"),
        Binding(
            "question_mark", "command_palette", "Help", key_display="?", priority=True
        ),
        Binding("tab", "focus_next_pane", "Switch Pane", priority=True),
        ("1", "show_tab('tab-files')", "Files"),
        ("2", "show_tab('tab-git')", "Git"),
        ("3", "show_tab('tab-github')", "GitHub"),
        ("f", "toggle_focus_mode", "Focus Mode"),
        ("ctrl+p", "file_search", "File Search"),
        Binding("d", "toggle_diff", "Toggle Diff", show=False),
        Binding("s", "toggle_diff_layout", "Diff Layout", show=False),
        Binding("n", "next_diff_file", "Next File", show=False),
        Binding("p", "prev_diff_file", "Prev File", show=False),
        Binding("o", "open_editor", "Open", show=False),
        Binding("left_square_bracket", "shrink_left_pane", "", show=False),
        Binding("right_square_bracket", "grow_left_pane", "", show=False),
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

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            yield Viewer(worktree_root=self.worktree_path, id="left-pane")
            yield DraggableSplitter()
            with TabbedContent(id="right-pane"):
                with TabPane("\uf0c5", id="tab-files"):
                    yield WorktreeFileTree(self.worktree_path)
                with TabPane("\ue725", id="tab-git"):
                    yield GitStatusPanel(self.worktree_path)
                with TabPane("\uf09b", id="tab-github"):
                    yield GitHubPanel(self.worktree_path)
        yield Footer()

    # ------------------------------------------------------------------
    # Event handlers — right-pane selections → viewer
    # ------------------------------------------------------------------

    def on_git_status_panel_file_selected(
        self, event: GitStatusPanel.FileSelected
    ) -> None:
        """Handle file selection in the git tab — open in viewer."""
        file_path = self.worktree_path / event.path
        viewer = self.query_one(Viewer)
        if file_path.is_file():
            viewer.load_file(file_path)
        else:
            viewer.show_deleted_file_diff(file_path, event.path, staged=event.staged)
        viewer.focus()

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

    def on_git_status_panel_commit_selected(
        self, event: GitStatusPanel.CommitSelected
    ) -> None:
        """Handle commit selection in the git tab — show full commit diff."""
        viewer = self.query_one(Viewer)
        viewer.worktree_root = self.worktree_path
        viewer.load_commit_diff(event.commit_hash)
        viewer.focus()

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
        elif event.preview_kind == "ci_check":
            viewer.show_ci_loading(title=event.title)
            viewer.fetch_ci_log(event.url)

    def on_git_status_panel_selection_restored(
        self, event: GitStatusPanel.SelectionRestored
    ) -> None:
        """Sync the viewer after an async git refresh, but only when Git tab is active."""
        if self.query_one(TabbedContent).active != "tab-git":
            return
        panel = self.query_one(GitStatusPanel)
        if not panel.activate_current_selection():
            self.query_one(Viewer).show_clean_tree()

    # ------------------------------------------------------------------
    # Tab navigation
    # ------------------------------------------------------------------

    def action_show_tab(self, tab: str) -> None:
        """Switch to the specified tab and focus its content."""
        self.query_one(TabbedContent).active = tab
        self._focus_active_tab()

    def action_focus_next_pane(self) -> None:
        """Move focus to the other pane."""
        viewer = self.query_one("#left-pane", Viewer)
        if viewer.has_focus:
            self._focus_active_tab()
        else:
            viewer.focus()

    def _focus_active_tab(self) -> None:
        """Focus the first navigable widget inside the active right-pane tab."""
        tabbed = self.query_one(TabbedContent)
        active = tabbed.active

        if active == "tab-files":
            tree = self.query_one(WorktreeFileTree)
            tree.focus()
            if tree.cursor_line == -1:
                tree.cursor_line = 0
            # Restore the last file viewed in the Files context
            viewer = self.query_one(Viewer)
            if self._files_tab_last_path and self._files_tab_last_path.is_file():
                viewer.load_file(self._files_tab_last_path)
            else:
                viewer.show_placeholder()
        elif active == "tab-git":
            panel = self.query_one(GitStatusPanel)
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
            self.query_one(WorktreeFileTree).focus()

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
        """Toggle the right pane and splitter to give the left pane full width."""
        self._focus_mode = not self._focus_mode
        right_pane = self.query_one("#right-pane", TabbedContent)
        splitter = self.query_one(DraggableSplitter)
        viewer = self.query_one("#left-pane", Viewer)

        if self._focus_mode:
            right_pane.display = False
            splitter.display = False
            viewer.styles.width = "100%"
            viewer.focus()
        else:
            right_pane.display = True
            splitter.display = True
            viewer.styles.width = "75%"
            self._focus_active_tab()

    def action_shrink_left_pane(self) -> None:
        """Shrink the left pane by 2 columns."""
        self.query_one(DraggableSplitter).resize_left_pane(-2)

    def action_grow_left_pane(self) -> None:
        """Grow the left pane by 2 columns."""
        self.query_one(DraggableSplitter).resize_left_pane(2)
