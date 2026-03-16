from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static, TabbedContent, TabPane

from perch.widgets.file_tree import WorktreeFileTree
from perch.widgets.file_viewer import FileViewer


class PerchApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "show_tab('tab-files')", "Files"),
        ("2", "show_tab('tab-git')", "Git"),
        ("3", "show_tab('tab-pr')", "PR"),
        ("tab", "focus_next_pane", "Next Pane"),
        ("shift+tab", "focus_prev_pane", "Prev Pane"),
    ]

    def __init__(self, worktree_path: Path, editor: str | None = None) -> None:
        super().__init__()
        self.worktree_path = worktree_path
        self.editor = editor

    def compose(self) -> ComposeResult:
        yield FileViewer(id="left-pane")
        with TabbedContent(id="right-pane"):
            with TabPane("Files", id="tab-files"):
                yield WorktreeFileTree(self.worktree_path)
            with TabPane("Git", id="tab-git"):
                yield Static("Coming soon", classes="placeholder")
            with TabPane("PR", id="tab-pr"):
                yield Static("Coming soon", classes="placeholder")

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
