"""Tests for the branch-diff picker modal and app integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from perch.models import Commit, GitStatusData


def _service_patches():
    return (
        patch("perch.services.git.get_status", return_value=GitStatusData()),
        patch("perch.services.git.get_log", return_value=[]),
        patch("perch.services.github.get_pr_context", return_value=None),
        patch("perch.services.github.get_checks", return_value=[]),
    )


class TestBranchDiffPickerScreen:
    async def test_escape_dismisses(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.branch_diff_picker import BranchDiffPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_merge_base", return_value=None),
            patch("perch.services.git.resolve_ref", return_value="abc1234"),
            patch("perch.services.git.get_commits_since", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_branch_diff()
                await pilot.pause(delay=0.15)
                assert isinstance(pilot.app.screen, BranchDiffPickerScreen)
                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, BranchDiffPickerScreen)

    async def test_h_picks_head(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.branch_diff_picker import BranchDiffPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_merge_base", return_value=("main", "base1234")),
            patch("perch.services.git.resolve_ref", return_value="head1234"),
            patch("perch.services.git.get_commits_since", return_value=[]),
            patch("perch.services.git.get_full_diff", return_value=""),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_branch_diff()
                await pilot.pause(delay=0.15)
                assert isinstance(pilot.app.screen, BranchDiffPickerScreen)
                await pilot.press("h")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, BranchDiffPickerScreen)
                assert pilot.app._last_branch_diff_ref == "HEAD"

    async def test_m_picks_merge_base(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.branch_diff_picker import BranchDiffPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_merge_base", return_value=("main", "base1234")),
            patch("perch.services.git.resolve_ref", return_value="head1234"),
            patch("perch.services.git.get_commits_since", return_value=[]),
            patch("perch.services.git.get_full_diff", return_value=""),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_branch_diff()
                await pilot.pause(delay=0.15)
                assert isinstance(pilot.app.screen, BranchDiffPickerScreen)
                await pilot.press("m")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, BranchDiffPickerScreen)
                assert pilot.app._last_branch_diff_ref == "base1234"

    async def test_m_with_no_merge_base_stays_open(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.branch_diff_picker import BranchDiffPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_merge_base", return_value=None),
            patch("perch.services.git.resolve_ref", return_value="head1234"),
            patch("perch.services.git.get_commits_since", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40), notifications=True) as pilot:
                await pilot.pause()
                pilot.app.action_branch_diff()
                await pilot.pause(delay=0.15)
                assert isinstance(pilot.app.screen, BranchDiffPickerScreen)
                await pilot.press("m")
                await pilot.pause()
                # Stays open; no ref set
                assert isinstance(pilot.app.screen, BranchDiffPickerScreen)
                assert pilot.app._last_branch_diff_ref is None

    async def test_commit_list_populated(self, tmp_path: Path) -> None:
        from textual.widgets import ListView

        from perch.app import PerchApp
        from perch.widgets.branch_diff_picker import BranchDiffPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        commits = [
            Commit(
                hash="abc1234",
                message="first",
                author="A",
                relative_time="1h",
                is_merge=False,
            ),
            Commit(
                hash="def5678",
                message="second",
                author="B",
                relative_time="2h",
                is_merge=False,
            ),
        ]
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_merge_base", return_value=("main", "base0000")),
            patch("perch.services.git.resolve_ref", return_value="head1234"),
            patch("perch.services.git.get_commits_since", return_value=commits),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_branch_diff()
                await pilot.pause(delay=0.2)
                screen = pilot.app.screen
                assert isinstance(screen, BranchDiffPickerScreen)
                list_view = screen.query_one("#branch-diff-picker-list", ListView)
                names = [c.name for c in list_view.children if c.name]
                assert "ref:HEAD" in names
                assert "ref:merge-base:base0000" in names
                assert "ref:commit:abc1234" in names
                assert "ref:commit:def5678" in names

    async def test_select_commit_from_list(self, tmp_path: Path) -> None:
        from textual.widgets import ListView

        from perch.app import PerchApp
        from perch.widgets.branch_diff_picker import BranchDiffPickerScreen

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        commits = [
            Commit(
                hash="abc1234",
                message="first",
                author="A",
                relative_time="1h",
                is_merge=False,
            ),
        ]
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_merge_base", return_value=("main", "base0000")),
            patch("perch.services.git.resolve_ref", return_value="head1234"),
            patch("perch.services.git.get_commits_since", return_value=commits),
            patch("perch.services.git.get_full_diff", return_value=""),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_branch_diff()
                await pilot.pause(delay=0.2)
                screen = pilot.app.screen
                assert isinstance(screen, BranchDiffPickerScreen)
                list_view = screen.query_one("#branch-diff-picker-list", ListView)
                for i, child in enumerate(list_view.children):
                    if child.name == "ref:commit:abc1234":
                        list_view.index = i
                        break
                await pilot.pause()
                screen.action_select()
                await pilot.pause()
                assert not isinstance(pilot.app.screen, BranchDiffPickerScreen)
                assert pilot.app._last_branch_diff_ref == "abc1234"


class TestViewerBranchDiff:
    async def test_show_branch_diff_renders_diff(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.viewer import Viewer

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        diff_text = (
            "diff --git a/file.py b/file.py\n"
            "--- a/file.py\n"
            "+++ b/file.py\n"
            "@@ -0,0 +1 @@\n"
            "+hello\n"
        )
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_full_diff", return_value=diff_text),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                viewer = pilot.app.query_one(Viewer)
                viewer.worktree_root = worktree
                viewer.show_branch_diff("abc1234", "abc1234")
                await pilot.pause()
                assert viewer._diff_mode is True
                assert "abc1234" in str(viewer.border_title)

    async def test_show_branch_diff_empty(self, tmp_path: Path) -> None:
        from perch.app import PerchApp
        from perch.widgets.viewer import Viewer

        worktree = tmp_path
        (worktree / "file.py").write_text("x")
        p1, p2, p3, p4 = _service_patches()
        with (
            p1,
            p2,
            p3,
            p4,
            patch("perch.services.git.get_full_diff", return_value=""),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                viewer = pilot.app.query_one(Viewer)
                viewer.worktree_root = worktree
                viewer.show_branch_diff("HEAD", "HEAD")
                await pilot.pause()
                # Diff mode still set; content should show "No changes"
                assert viewer._diff_mode is True
