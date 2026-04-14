"""Tests for worktree/branch picker modal and git worktree/branch parsing."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from perch.models import Worktree
from perch.services.git import (
    get_branches,
    get_worktrees,
    parse_worktree_list,
    switch_branch,
)


class TestParseWorktreeList:
    """Tests for parsing `git worktree list --porcelain` output."""

    def test_empty(self) -> None:
        assert parse_worktree_list("") == []

    def test_single_worktree(self) -> None:
        raw = (
            "worktree /home/user/repo\n"
            "HEAD abc1234567890def\n"
            "branch refs/heads/main\n"
            "\n"
        )
        result = parse_worktree_list(raw)
        assert len(result) == 1
        assert result[0] == Worktree(
            path="/home/user/repo",
            head="abc1234567890def",
            branch="main",
        )

    def test_multiple_worktrees(self) -> None:
        raw = (
            "worktree /home/user/repo\n"
            "HEAD abc1234\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-feature\n"
            "HEAD def5678\n"
            "branch refs/heads/feature/cool\n"
            "\n"
        )
        result = parse_worktree_list(raw)
        assert len(result) == 2
        assert result[0].branch == "main"
        assert result[1].branch == "feature/cool"
        assert result[1].path == "/home/user/repo-feature"

    def test_detached_head(self) -> None:
        raw = "worktree /home/user/repo\nHEAD abc1234\ndetached\n\n"
        result = parse_worktree_list(raw)
        assert len(result) == 1
        assert result[0].branch is None

    def test_no_trailing_blank_line(self) -> None:
        raw = "worktree /home/user/repo\nHEAD abc1234\nbranch refs/heads/main\n"
        result = parse_worktree_list(raw)
        assert len(result) == 1
        assert result[0].branch == "main"

    def test_mixed_attached_and_detached(self) -> None:
        raw = (
            "worktree /home/user/repo\n"
            "HEAD abc1234\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/bisect\n"
            "HEAD def5678\n"
            "detached\n"
            "\n"
        )
        result = parse_worktree_list(raw)
        assert len(result) == 2
        assert result[0].branch == "main"
        assert result[1].branch is None


class TestGetWorktrees:
    """Tests for get_worktrees using real git repos."""

    def test_single_worktree(self, git_worktree: Path) -> None:
        worktrees = get_worktrees(git_worktree)
        assert len(worktrees) == 1
        assert worktrees[0].path == str(git_worktree)
        assert worktrees[0].branch is not None

    def test_with_linked_worktree(self, git_worktree: Path) -> None:
        linked = git_worktree.parent / "linked-wt"
        subprocess.run(
            ["git", "worktree", "add", str(linked), "-b", "test-branch"],
            cwd=git_worktree,
            capture_output=True,
            check=True,
        )
        worktrees = get_worktrees(git_worktree)
        assert len(worktrees) == 2
        paths = {wt.path for wt in worktrees}
        assert str(git_worktree) in paths
        assert str(linked) in paths
        branches = {wt.branch for wt in worktrees}
        assert "test-branch" in branches

    @patch("perch.services.git._run_git")
    def test_returns_empty_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "worktree", "list"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        result = get_worktrees(Path("/tmp"))
        assert result == []


class TestGetBranches:
    """Tests for get_branches."""

    def test_returns_branches(self, git_worktree: Path) -> None:
        branches = get_branches(git_worktree)
        assert len(branches) >= 1

    def test_includes_created_branch(self, git_worktree: Path) -> None:
        subprocess.run(
            ["git", "branch", "feature-x"],
            cwd=git_worktree,
            capture_output=True,
            check=True,
        )
        branches = get_branches(git_worktree)
        assert "feature-x" in branches

    @patch("perch.services.git._run_git")
    def test_returns_empty_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "branch"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        result = get_branches(Path("/tmp"))
        assert result == []


class TestSwitchBranch:
    """Tests for switch_branch."""

    def test_switches_to_existing_branch(self, git_worktree: Path) -> None:
        from perch.services.git import get_current_branch

        subprocess.run(
            ["git", "branch", "other"],
            cwd=git_worktree,
            capture_output=True,
            check=True,
        )
        switch_branch(git_worktree, "other")
        assert get_current_branch(git_worktree) == "other"

    def test_raises_on_nonexistent_branch(self, git_worktree: Path) -> None:
        import pytest

        with pytest.raises(RuntimeError, match="git switch failed"):
            switch_branch(git_worktree, "does-not-exist")


class TestGitPickerScreen:
    """Tests for the GitPickerScreen modal."""

    async def test_escape_dismisses(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.git_picker import GitPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_worktrees", return_value=[]),
            patch("perch.services.git.get_branches", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_switch_worktree()
                await pilot.pause(delay=0.15)
                assert isinstance(pilot.app.screen, GitPickerScreen)
                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, GitPickerScreen)

    async def test_deduplicates_worktrees_and_branches(self, tmp_path: Path) -> None:
        """Worktree branches should not appear again as plain branches."""
        from textual.widgets import ListView

        from perch.app import PerchApp
        from perch.widgets.git_picker import GitPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        mock_worktrees = [
            Worktree(path=str(worktree), head="abc1234", branch="main"),
            Worktree(path="/other/wt", head="def5678", branch="dev"),
        ]
        mock_branches = ["main", "dev", "feature-x"]
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_worktrees", return_value=mock_worktrees),
            patch("perch.services.git.get_branches", return_value=mock_branches),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_switch_worktree()
                await pilot.pause(delay=0.15)
                screen = pilot.app.screen
                assert isinstance(screen, GitPickerScreen)
                list_view = screen.query_one("#git-picker-list", ListView)
                names = [c.name for c in list_view.children if c.name]
                # Worktrees shown as worktree entries
                assert any("worktree:" in n for n in names)
                # feature-x shown as branch (no worktree for it)
                assert any("branch:feature-x" in n for n in names)
                # main and dev must NOT appear as branches (already worktrees)
                assert not any("branch:main" in n for n in names)
                assert not any("branch:dev" in n for n in names)
                # Total: 2 worktrees + 1 branch = 3 items
                assert len(names) == 3

    async def test_select_branch_dismisses(self, tmp_path: Path) -> None:
        """Selecting a branch item should dismiss with branch: prefix."""
        from textual.widgets import ListView

        from perch.app import PerchApp
        from perch.widgets.git_picker import GitPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        mock_worktrees = [
            Worktree(path=str(worktree), head="abc1234", branch="main"),
        ]
        mock_branches = ["main", "feature-a"]
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_worktrees", return_value=mock_worktrees),
            patch("perch.services.git.get_branches", return_value=mock_branches),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_switch_worktree()
                await pilot.pause(delay=0.15)
                screen = pilot.app.screen
                assert isinstance(screen, GitPickerScreen)
                list_view = screen.query_one("#git-picker-list", ListView)
                # Focus list and select the branch item (feature-a)
                list_view.focus()
                for i, child in enumerate(list_view.children):
                    if child.name and "branch:feature-a" in child.name:
                        list_view.index = i
                        break
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, GitPickerScreen)

    async def test_select_current_worktree_dismisses_none(self, tmp_path: Path) -> None:
        """Selecting the current worktree should dismiss without switching."""
        from textual.widgets import ListView

        from perch.app import PerchApp
        from perch.widgets.git_picker import GitPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        mock_worktrees = [
            Worktree(path=str(worktree), head="abc1234", branch="main"),
            Worktree(path="/other/wt", head="def5678", branch="dev"),
        ]
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_worktrees", return_value=mock_worktrees),
            patch("perch.services.git.get_branches", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_switch_worktree()
                await pilot.pause(delay=0.15)
                screen = pilot.app.screen
                assert isinstance(screen, GitPickerScreen)
                list_view = screen.query_one("#git-picker-list", ListView)
                # Select the current worktree (first item)
                list_view.focus()
                list_view.index = 0
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause(delay=0.1)
                # Should dismiss back to main screen
                assert not isinstance(pilot.app.screen, GitPickerScreen)


class TestAppWorktreeSwitching:
    """Tests for app-level worktree/branch switching."""

    async def test_on_worktree_selected_none(self, tmp_path: Path) -> None:
        """Selecting None should be a no-op."""
        from perch.app import PerchApp

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                original_path = pilot.app.worktree_path
                pilot.app._on_worktree_selected(None)
                await pilot.pause()
                assert pilot.app.worktree_path == original_path

    async def test_switch_to_worktree(self, tmp_path: Path) -> None:
        """Selecting a worktree should update worktree_path."""
        from perch.app import PerchApp

        worktree = tmp_path / "wt1"
        worktree.mkdir()
        (worktree / "file.py").write_text("x")
        other = tmp_path / "wt2"
        other.mkdir()
        (other / "other.py").write_text("y")
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app._on_worktree_selected(f"worktree:{other}")
                await pilot.pause()
                await pilot.pause()
                assert pilot.app.worktree_path == other
                assert str(other) in pilot.app.sub_title

    async def test_switch_to_nonexistent_worktree(self, tmp_path: Path) -> None:
        """Selecting a nonexistent worktree path should show error."""
        from perch.app import PerchApp

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40), notifications=True) as pilot:
                await pilot.pause()
                original_path = pilot.app.worktree_path
                pilot.app._on_worktree_selected("worktree:/nonexistent/path")
                await pilot.pause()
                assert pilot.app.worktree_path == original_path

    async def test_on_worktree_selected_branch(self, tmp_path: Path) -> None:
        """Selecting a branch should call _switch_to_branch."""
        from perch.app import PerchApp

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4, patch("perch.services.git.switch_branch") as mock_switch:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app._on_worktree_selected("branch:feature-x")
                await pilot.pause(delay=0.15)
                mock_switch.assert_called_once_with(worktree, "feature-x")


def _service_patches():
    """Patch git/github services to prevent real subprocess calls."""
    return (
        patch(
            "perch.services.git.get_status",
            return_value=__import__(
                "perch.models", fromlist=["GitStatusData"]
            ).GitStatusData(),
        ),
        patch("perch.services.git.get_log", return_value=[]),
        patch("perch.services.github.get_pr_context", return_value=None),
        patch("perch.services.github.get_checks", return_value=[]),
    )
