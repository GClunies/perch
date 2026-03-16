from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, TabbedContent, TabPane

from perch.commands import DiscoveryCommandProvider
from perch.services.editor import open_file
from perch.widgets.file_search import FileSearchScreen
from perch.widgets.file_tree import WorktreeFileTree
from perch.widgets.file_viewer import FileViewer
from perch.widgets.git_status import GitStatusPanel
from perch.widgets.pr_context import PRContextPanel
from perch.widgets.splitter import DraggableSplitter


class PerchApp(App):
    CSS_PATH = "app.tcss"
    COMMANDS = App.COMMANDS | {DiscoveryCommandProvider}

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "show_tab('tab-files')", "Files"),
        ("2", "show_tab('tab-git')", "Git"),
        ("3", "show_tab('tab-pr')", "PR"),
        ("tab", "focus_next_pane", "Next Pane"),
        ("shift+tab", "focus_prev_pane", "Prev Pane"),
        ("ctrl+p", "file_search", "Search Files"),
        ("ctrl+shift+p", "command_palette", "Command Palette"),
        ("e", "open_editor", "Open in Editor"),
        ("left_square_bracket", "shrink_left_pane", "Shrink Left"),
        ("right_square_bracket", "grow_left_pane", "Grow Left"),
    ]

    def __init__(self, worktree_path: Path, editor: str | None = None) -> None:
        super().__init__()
        self.worktree_path = worktree_path
        self.editor = editor
        self._branch: str | None = None
        try:
            from perch.services.git import get_current_branch, get_worktree_root

            git_root = get_worktree_root(worktree_path)
            self._branch = get_current_branch(git_root)
        except (RuntimeError, FileNotFoundError):
            pass

    def watch_theme(self, _value: str | None = None) -> None:
        """Re-render the file viewer when the app theme changes."""
        try:
            viewer = self.query_one(FileViewer)
        except Exception:
            return
        if viewer._current_path is not None:
            if viewer._diff_mode:
                viewer._load_diff()
            else:
                viewer.load_file(viewer._current_path)

    def on_mount(self) -> None:
        if self._branch:
            self.title = f"perch — {self._branch}"
        else:
            self.title = "perch"
        self.sub_title = str(self.worktree_path)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            yield FileViewer(worktree_root=self.worktree_path, id="left-pane")
            yield DraggableSplitter()
            with TabbedContent(id="right-pane"):
                with TabPane("Files", id="tab-files"):
                    yield WorktreeFileTree(self.worktree_path)
                with TabPane("Git", id="tab-git"):
                    yield GitStatusPanel(self.worktree_path)
                with TabPane("PR", id="tab-pr"):
                    yield PRContextPanel(self.worktree_path)
        yield Footer()

    def on_tree_node_highlighted(self, event) -> None:
        """Update the file viewer when a tree node is highlighted (cursor moves)."""
        node = event.node
        if node.data is None:
            return
        path = node.data.path if hasattr(node.data, "path") else node.data
        if isinstance(path, Path) and path.is_file():
            self.query_one(FileViewer).load_file(path)

    def action_show_tab(self, tab: str) -> None:
        """Switch to the specified tab."""
        self.query_one(TabbedContent).active = tab

    def action_focus_next_pane(self) -> None:
        """Move focus to the other pane."""
        viewer = self.query_one("#left-pane", FileViewer)
        if viewer.has_focus:
            self.query_one(WorktreeFileTree).focus()
        else:
            viewer.focus()

    def action_focus_prev_pane(self) -> None:
        """Move focus to the other pane (reverse direction)."""
        self.action_focus_next_pane()

    def action_file_search(self) -> None:
        """Open the fuzzy file search modal."""
        self.push_screen(FileSearchScreen(self.worktree_path), self._on_file_selected)

    def _on_file_selected(self, result: str | None) -> None:
        """Handle the result from the file search modal."""
        if result is not None:
            path = self.worktree_path / result
            if path.is_file():
                self.query_one(FileViewer).load_file(path)

    def action_open_editor(self) -> None:
        """Open the currently highlighted file in the external editor."""
        viewer = self.query_one(FileViewer)
        if viewer._current_path is not None:
            open_file(self.editor, viewer._current_path, self.worktree_path)

    def action_shrink_left_pane(self) -> None:
        """Shrink the left pane by 2 columns."""
        self.query_one(DraggableSplitter).resize_left_pane(-2)

    def action_grow_left_pane(self) -> None:
        """Grow the left pane by 2 columns."""
        self.query_one(DraggableSplitter).resize_left_pane(2)

