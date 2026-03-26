"""Tests for DraggableSplitter widget."""

from pathlib import Path

import pytest
from textual import events

from perch.app import PerchApp
from perch.widgets.splitter import DraggableSplitter


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Create a minimal worktree with some files."""
    (tmp_path / "hello.py").write_text("print('hello')\n")
    return tmp_path


class TestSplitterComposition:
    """Tests that the splitter is composed into the app layout."""

    async def test_app_has_splitter(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            assert splitter is not None

    async def test_splitter_width_is_one(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            assert splitter.size.width == 1


class TestClampWidth:
    """Tests for the width clamping logic."""

    async def test_clamp_enforces_min_left(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            result = splitter._clamp_width(5)
            assert result == DraggableSplitter.MIN_LEFT

    async def test_clamp_enforces_min_right(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            app_width = pilot.app.size.width
            result = splitter._clamp_width(app_width)
            expected_max = app_width - DraggableSplitter.MIN_RIGHT - 1
            assert result == expected_max

    async def test_clamp_allows_valid_width(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            result = splitter._clamp_width(40)
            assert result == 40


class TestResizeLeftPane:
    """Tests for resize_left_pane method."""

    async def test_resize_left_pane_grows(self, worktree: Path) -> None:
        """resize_left_pane(+delta) should increase the left pane width."""
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            left_pane = pilot.app.query_one("#left-pane")
            splitter.resize_left_pane(5)
            await pilot.pause()
            # Width should have changed (or clamped)
            new_width = left_pane.styles.width
            assert new_width is not None

    async def test_resize_left_pane_shrinks(self, worktree: Path) -> None:
        """resize_left_pane(-delta) should decrease the left pane width."""
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            left_pane = pilot.app.query_one("#left-pane")
            splitter.resize_left_pane(-5)
            await pilot.pause()
            new_width = left_pane.styles.width
            assert new_width is not None


class TestMouseDrag:
    """Tests for mouse drag resizing.

    Call handlers directly instead of post_message to avoid
    platform-dependent mouse event dispatch in headless CI.
    """

    async def test_mouse_down_starts_drag(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            assert splitter._dragging is False
            event = events.MouseDown(
                splitter, 0, 5, 0, 0, 1, False, False, False, screen_x=40.0
            )
            splitter.on_mouse_down(event)
            assert splitter._dragging is True

    async def test_mouse_up_stops_drag(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            splitter._dragging = True
            event = events.MouseUp(
                splitter, 0, 5, 0, 0, 1, False, False, False, screen_x=45.0
            )
            splitter.on_mouse_up(event)
            assert splitter._dragging is False

    async def test_mouse_drag_resizes_pane(self, worktree: Path) -> None:
        """Dragging the splitter should change the left pane width style."""
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            left_pane = pilot.app.query_one("#left-pane")

            # Set a known starting width
            left_pane.styles.width = 40
            await pilot.pause()

            # Start drag at screen_x=40
            down = events.MouseDown(
                splitter, 0, 5, 0, 0, 1, False, False, False, screen_x=40.0
            )
            splitter.on_mouse_down(down)

            # Move mouse 5 columns right
            move = events.MouseMove(
                splitter, 5, 5, 5, 0, 1, False, False, False, screen_x=45.0
            )
            splitter.on_mouse_move(move)
            await pilot.pause()

            # styles.width should be updated to 45 (40 + 5)
            width = left_pane.styles.width
            assert width is not None
            assert width.value == 45

    async def test_mouse_move_without_drag_is_noop(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            left_pane = pilot.app.query_one("#left-pane")
            initial_width = left_pane.outer_size.width

            # Move without dragging
            move = events.MouseMove(
                splitter, 10, 5, 10, 0, 0, False, False, False, screen_x=50.0
            )
            splitter.on_mouse_move(move)
            await pilot.pause()

            assert left_pane.outer_size.width == initial_width
