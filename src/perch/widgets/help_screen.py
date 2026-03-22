"""Help screen modal displaying all keybindings organized by section."""

from __future__ import annotations

from rich.markup import escape

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static


def _build_help_content(registry: dict[str, list[Binding]]) -> str:
    """Build a formatted string of keybindings grouped by section.

    Pure function for testability.  Returns a Rich-markup string suitable
    for rendering inside a ``Static`` widget.
    """
    lines: list[str] = []
    for section, bindings in registry.items():
        lines.append(f"[bold]{section}[/bold] " + "\u2500" * (40 - len(section)))
        for b in bindings:
            key = escape(b.key_display or b.key)
            desc = b.description
            lines.append(f"  {key:<12} {desc}")
        lines.append("")  # blank line between sections
    return "\n".join(lines)


class HelpScreen(ModalScreen[None]):
    """Modal screen showing all keybindings organised by section."""

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-container {
        width: 60;
        max-height: 40;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        registry = getattr(self.app, "BINDING_REGISTRY", {})
        content = _build_help_content(registry)
        yield Static(content, id="help-container")

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
