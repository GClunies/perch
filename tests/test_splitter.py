"""Tests for DraggableSplitter widget."""

from pathlib import Path

import pytest

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


class TestKeyboardResize:
    """Tests for [ and ] keyboard shortcuts."""

    async def test_right_bracket_grows_left_pane(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test(size=(80, 24)) as pilot:
            left = pilot.app.query_one("#left-pane")
            initial_outer = left.outer_size.width
            await pilot.press("right_square_bracket")
            await pilot.pause()
            assert left.outer_size.width == initial_outer + 2

    async def test_left_bracket_shrinks_left_pane(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test(size=(80, 24)) as pilot:
            left = pilot.app.query_one("#left-pane")
            initial_outer = left.outer_size.width
            await pilot.press("left_square_bracket")
            await pilot.pause()
            assert left.outer_size.width == initial_outer - 2

    async def test_shrink_respects_min_left(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test(size=(80, 24)) as pilot:
            left = pilot.app.query_one("#left-pane")
            for _ in range(30):
                await pilot.press("left_square_bracket")
            await pilot.pause()
            assert left.outer_size.width >= DraggableSplitter.MIN_LEFT

    async def test_grow_respects_min_right(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test(size=(80, 24)) as pilot:
            left = pilot.app.query_one("#left-pane")
            for _ in range(30):
                await pilot.press("right_square_bracket")
            await pilot.pause()
            app_width = pilot.app.size.width
            max_left = app_width - DraggableSplitter.MIN_RIGHT - 1
            assert left.outer_size.width <= max_left
