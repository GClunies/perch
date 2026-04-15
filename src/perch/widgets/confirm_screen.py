"""Simple yes/no confirmation modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label


class ConfirmScreen(ModalScreen[bool]):
    """Modal that asks a yes/no question and returns True/False."""

    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #confirm-message {
        margin-bottom: 1;
    }
    #confirm-hint {
        text-style: dim;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Label(self._message, id="confirm-message")
            yield Label("Press y to confirm, n or Esc to cancel", id="confirm-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
