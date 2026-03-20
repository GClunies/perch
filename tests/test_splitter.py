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
