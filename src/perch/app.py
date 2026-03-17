from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
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
    COMMAND_PALETTE_BINDING = "question_mark"

    BINDINGS = [
        ("q", "quit", "Quit"),
        Binding("question_mark", "command_palette", "Help", key_display="?", priority=True),
        Binding("tab", "focus_next_pane", "Switch Pane", priority=True),
        ("1", "show_tab('tab-files')", "Files"),
        ("2", "show_tab('tab-git')", "Git"),
        ("3", "show_tab('tab-pr')", "PR"),
        ("f", "toggle_focus_mode", "Focus Mode"),
        ("ctrl+p", "file_search", "File Search"),
        Binding("d", "toggle_diff", "Toggle Diff", show=False),
        Binding("s", "toggle_diff_layout", "Diff Layout", show=False),
        Binding("n", "next_diff_file", "Next File", show=False),
        Binding("p", "prev_diff_file", "Prev File", show=False),
        Binding("e", "open_editor", "Editor", show=False),
        Binding("[", "shrink_left_pane", "", show=False),
        Binding("]", "grow_left_pane", "", show=False),
    ]

    def __init__(self, worktree_path: Path, editor: str | None = None) -> None:
        super().__init__()
        self.worktree_path = worktree_path
        self.editor = editor
        self._focus_mode = False
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
        self._focus_active_tab()

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

    def on_git_status_panel_file_selected(
        self, event: GitStatusPanel.FileSelected
    ) -> None:
        """Handle file selection in the git tab — open in file viewer."""
        file_path = self.worktree_path / event.path
        viewer = self.query_one(FileViewer)
        if file_path.is_file():
            viewer.load_file(file_path)
            viewer.focus()
        else:
            # File was deleted — show message and offer diff view
            viewer._current_path = file_path
            viewer.worktree_root = self.worktree_path
            viewer._diff_mode = True
            viewer._diff_layout = "unified"
            viewer._show_content_view()
            from perch.services.git import get_diff

            rel_path = event.path
            try:
                diff_text = get_diff(self.worktree_path, rel_path, staged=event.staged)
            except RuntimeError:
                diff_text = ""
            from rich.console import Group
            from rich.text import Text

            from perch.widgets.file_viewer import render_diff

            if diff_text:
                styled = render_diff(diff_text, dark=viewer._is_dark_theme())
                header = Text("File deleted — showing diff\n", style="bold red")
                viewer._content.update(Group(header, styled))
            else:
                viewer._content.update(
                    Text("File deleted — no diff available", style="bold red")
                )
            viewer.focus()

    def on_tree_node_highlighted(self, event) -> None:
        """Update the file viewer when a tree node is highlighted (cursor moves)."""
        node = event.node
        if node.data is None:
            return
        path = node.data.path if hasattr(node.data, "path") else node.data
        if isinstance(path, Path) and path.is_file():
            self.query_one(FileViewer).load_file(path)

    def on_directory_tree_file_selected(self, event) -> None:
        """Focus the file viewer when a file is selected with enter."""
        viewer = self.query_one(FileViewer)
        viewer.load_file(event.path)
        viewer.focus()

    def action_show_tab(self, tab: str) -> None:
        """Switch to the specified tab and focus its content."""
        self.query_one(TabbedContent).active = tab
        self._focus_active_tab()

    def action_focus_next_pane(self) -> None:
        """Move focus to the other pane."""
        viewer = self.query_one("#left-pane", FileViewer)
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
            # Ensure the cursor is on the root so arrow keys work immediately
            if tree.cursor_line == -1:
                tree.cursor_line = 0
        elif active == "tab-git":
            panel = self.query_one(GitStatusPanel)
            panel.focus()
            if panel.index is None:
                panel._restore_selection(None)
        elif active == "tab-pr":
            self.query_one(PRContextPanel).focus()
        else:
            self.query_one(WorktreeFileTree).focus()


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

    def on_git_status_panel_commit_selected(
        self, event: GitStatusPanel.CommitSelected
    ) -> None:
        """Handle commit selection in the git tab — show full commit diff."""
        viewer = self.query_one(FileViewer)
        viewer.worktree_root = self.worktree_path
        viewer.load_commit_diff(event.commit_hash)
        viewer.focus()

    def action_toggle_diff(self) -> None:
        """Toggle diff view in the file viewer (command palette entry)."""
        self.query_one(FileViewer).action_toggle_diff()

    def action_toggle_diff_layout(self) -> None:
        """Toggle diff layout in the file viewer (command palette entry)."""
        self.query_one(FileViewer).action_toggle_diff_layout()

    def action_next_diff_file(self) -> None:
        """Jump to the next file in a multi-file diff."""
        self.query_one(FileViewer).action_next_diff_file()

    def action_prev_diff_file(self) -> None:
        """Jump to the previous file in a multi-file diff."""
        self.query_one(FileViewer).action_prev_diff_file()

    def action_toggle_focus_mode(self) -> None:
        """Toggle the right pane and splitter to give the left pane full width."""
        self._focus_mode = not self._focus_mode
        right_pane = self.query_one("#right-pane", TabbedContent)
        splitter = self.query_one(DraggableSplitter)
        viewer = self.query_one("#left-pane", FileViewer)

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
