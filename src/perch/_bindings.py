"""Shared binding constants and factory functions for Perch widgets."""

from __future__ import annotations

from textual.binding import Binding

_HERO_KEY_DISPLAY = "hjkl/\u2190\u2193\u2191\u2192"


def make_nav_bindings(
    down: str = "cursor_down",
    up: str = "cursor_up",
    left: str | None = None,
    right: str | None = None,
) -> tuple[Binding, ...]:
    """Build navigation bindings with the hero-display pattern.

    The first binding (``j``) gets ``show=True`` with a combined key_display;
    the rest are hidden.  When *left* and *right* are provided, ``h`` and ``l``
    bindings are appended.
    """
    bindings: list[Binding] = [
        Binding("j", down, "Navigate", key_display=_HERO_KEY_DISPLAY),
        Binding("k", up, "Up", show=False),
    ]
    if left is not None:
        bindings.append(Binding("h", left, "Left", show=False))
    if right is not None:
        bindings.append(Binding("l", right, "Right", show=False))
    return tuple(bindings)


QUIT_BINDING = Binding("ctrl+q", "app.quit", "Quit", key_display="^q")

COPY_BINDING = Binding("c", "app.copy", "Copy Path")

HELP_BINDING = Binding("question_mark", "app.show_help", "Help", key_display="?")

TAB_BINDINGS: tuple[Binding, ...] = (
    Binding("tab", "app.focus_next_pane", "Tab", key_display="tab"),
    Binding("left_square_bracket", "app.prev_tab", "Prev/Next Tab", key_display="[/]"),
)

FOCUS_BINDING = Binding("f", "app.toggle_focus_mode", "Focus", show=False)

REFRESH_BINDING = Binding("r", "refresh", "Refresh")

PAGE_BINDINGS: tuple[Binding, ...] = (
    Binding("pageup", "page_up", "Page Up", show=False),
    Binding("pagedown", "page_down", "Page Down", show=False),
)
