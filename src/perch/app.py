from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static


class PerchApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, worktree_path: Path, editor: str | None = None) -> None:
        super().__init__()
        self.worktree_path = worktree_path
        self.editor = editor

    def compose(self) -> ComposeResult:
        yield Static("File Viewer", id="left-pane")
        yield Static("Tabs", id="right-pane")
