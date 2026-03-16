"""Tests for PerchApp tabbed layout and tree-to-viewer wiring."""

from pathlib import Path

import pytest
from textual.widgets import TabbedContent, TabPane

from perch.app import PerchApp
from perch.widgets.file_tree import WorktreeFileTree
from perch.widgets.file_viewer import FileViewer
from perch.widgets.git_status import GitStatusPanel
from perch.widgets.pr_context import PRContextPanel


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Create a minimal worktree with some files."""
    (tmp_path / "hello.py").write_text("print('hello')\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "world.txt").write_text("world\n")
    return tmp_path


class TestPerchAppCompose:
    """Tests for the app layout and widget composition."""

    async def test_has_file_viewer(self, worktree: Path) -> None:
        """App should have a FileViewer as the left pane."""
        async with PerchApp(worktree).run_test() as pilot:
            viewer = pilot.app.query_one("#left-pane", FileViewer)
            assert viewer is not None

    async def test_has_tabbed_content(self, worktree: Path) -> None:
        """App should have a TabbedContent as the right pane."""
        async with PerchApp(worktree).run_test() as pilot:
            tabs = pilot.app.query_one("#right-pane", TabbedContent)
            assert tabs is not None

    async def test_has_three_tabs(self, worktree: Path) -> None:
        """TabbedContent should have three tab panes: Files, Git, PR."""
        async with PerchApp(worktree).run_test() as pilot:
            panes = pilot.app.query(TabPane)
            assert len(panes) == 3

    async def test_files_tab_contains_tree(self, worktree: Path) -> None:
        """Files tab should contain a WorktreeFileTree."""
        async with PerchApp(worktree).run_test() as pilot:
            tree = pilot.app.query_one(WorktreeFileTree)
            assert tree is not None

    async def test_git_tab_has_status_panel(self, worktree: Path) -> None:
        """Git tab should contain a GitStatusPanel widget."""
        async with PerchApp(worktree).run_test() as pilot:
            panel = pilot.app.query_one(GitStatusPanel)
            assert panel is not None

    async def test_pr_tab_has_context_panel(self, worktree: Path) -> None:
        """PR tab should contain a PRContextPanel widget."""
        async with PerchApp(worktree).run_test() as pilot:
            panel = pilot.app.query_one(PRContextPanel)
            assert panel is not None


class TestTabSwitching:
    """Tests for tab switching via number keys."""

    async def test_key_1_activates_files_tab(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            # Switch away first, then back
            pilot.app.query_one(TabbedContent).active = "tab-git"
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-files"

    async def test_key_2_activates_git_tab(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("2")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-git"

    async def test_key_3_activates_pr_tab(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("3")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-pr"


class TestQuitBinding:
    """Test that q quits the app."""

    async def test_q_quits(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()
            assert pilot.app.return_code is not None or not pilot.app.is_running
