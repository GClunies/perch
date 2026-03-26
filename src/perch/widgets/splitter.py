"""Vertical splitter widget for visually separating panes."""

from __future__ import annotations

from textual import events
from textual.widget import Widget

from rich.text import Text


class DraggableSplitter(Widget):
    """A vertical splitter bar between panes. Resized via keyboard (- / =) or mouse drag."""

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

    _dragging: bool = False
    _drag_start_x: float = 0

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

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Start drag when mouse is pressed on the splitter."""
        self._dragging = True
        self._drag_start_x = event.screen_x if event.screen_x is not None else 0
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Resize the left pane as the mouse moves during drag."""
        if not self._dragging:
            return
        current_x = event.screen_x if event.screen_x is not None else 0
        delta = int(current_x - self._drag_start_x)
        if delta != 0:
            self.resize_left_pane(delta)
            self._drag_start_x = current_x
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Stop drag when mouse is released."""
        if self._dragging:
            self._dragging = False
            self.release_mouse()
            event.stop()
