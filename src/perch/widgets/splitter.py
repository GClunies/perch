"""Vertical splitter widget for visually separating panes."""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget


class DraggableSplitter(Widget):
    """A vertical splitter bar between panes. Resized via keyboard (- / =)."""

    DEFAULT_CSS = """
    DraggableSplitter {
        width: 1;
        height: 100%;
        background: $surface;
        color: $text-muted;
    }
    """

    MIN_LEFT = 20
    MIN_RIGHT = 25

    def render(self) -> Text:
        """Render a vertical line of │ characters."""
        return Text("\n".join("│" for _ in range(self.size.height)))

    def _clamp_width(self, desired: int) -> int:
        """Clamp the left pane width to enforce minimum widths on both panes."""
        app_width = self.app.size.width
        max_left = app_width - self.MIN_RIGHT - 1  # -1 for splitter column
        return max(self.MIN_LEFT, min(desired, max_left))

    def resize_left_pane(self, delta: int) -> None:
        """Resize the left pane by delta columns, enforcing min widths."""
        left_pane = self.app.query_one("#left-pane")
        current_width = left_pane.outer_size.width
        new_width = self._clamp_width(current_width + delta)
        left_pane.styles.width = new_width
