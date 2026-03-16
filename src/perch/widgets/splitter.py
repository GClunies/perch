"""Draggable vertical splitter widget for resizing panes."""

from __future__ import annotations

from rich.text import Text
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widget import Widget


class DraggableSplitter(Widget):
    """A vertical splitter bar that can be dragged to resize adjacent panes."""

    DEFAULT_CSS = """
    DraggableSplitter {
        width: 1;
        height: 100%;
        background: $surface;
        color: $text-muted;
    }
    DraggableSplitter:hover {
        background: $accent;
        color: $text;
    }
    DraggableSplitter.-dragging {
        background: $accent;
        color: $text;
    }
    """

    MIN_LEFT = 20
    MIN_RIGHT = 25

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._dragging = False

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

    def on_mouse_down(self, event: MouseDown) -> None:
        self.capture_mouse()
        self._dragging = True
        self.add_class("-dragging")
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        new_width = self._clamp_width(event.screen_x)
        self.app.query_one("#left-pane").styles.width = new_width
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self.release_mouse()
            self._dragging = False
            self.remove_class("-dragging")
            event.stop()
