"""Tests for GitPanel widget and helpers."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Label, ListItem

from perch.models import Commit, GitFile, GitStatusData
from perch.widgets.git_status import (
    GitPanel,
    _make_file_item,
    _make_section_header,
)


class TestMakeFileItem:
    """Tests for _make_file_item helper."""

    def test_single_modified_file(self) -> None:
        f = GitFile(path="src/app.py", status="modified", staged=False)
        item = _make_file_item(f)
        assert item.name == "src/app.py"

    def test_staged_flag(self) -> None:
        f = GitFile(path="a.py", status="added", staged=True)
        item = _make_file_item(f, staged=True)
        assert getattr(item, "_staged", False) is True

    def test_unstaged_flag(self) -> None:
        f = GitFile(path="a.py", status="modified", staged=False)
        item = _make_file_item(f, staged=False)
        assert getattr(item, "_staged", True) is False

    def test_all_status_types_render(self) -> None:
        statuses = [
            "modified",
            "added",
            "deleted",
            "renamed",
            "copied",
            "unmerged",
            "type-changed",
            "untracked",
        ]
        for s in statuses:
            f = GitFile(path=f"{s}.py", status=s, staged=False)
            item = _make_file_item(f)
            assert item.name == f"{s}.py"


class TestMakeSectionHeader:
    """Tests for _make_section_header helper."""

    def test_returns_disabled_list_item(self) -> None:
        item = _make_section_header("Unstaged Changes")
        assert isinstance(item, ListItem)
        assert item.disabled is True

    def test_has_section_header_class(self) -> None:
        item = _make_section_header("Staged Changes")
        assert "section-header" in item.classes


class TestFileSelectedMessage:
    """Tests for GitPanel.FileSelected message."""

    def test_attributes(self) -> None:
        msg = GitPanel.FileSelected(path="src/app.py", staged=True)
        assert msg.path == "src/app.py"
        assert msg.staged is True

    def test_unstaged(self) -> None:
        msg = GitPanel.FileSelected(path="README.md", staged=False)
        assert msg.path == "README.md"
        assert msg.staged is False


# ---------------------------------------------------------------------------
# Helpers for async widget tests
# ---------------------------------------------------------------------------

_EMPTY_STATUS = GitStatusData()
_SAMPLE_STATUS = GitStatusData(
    unstaged=[GitFile(path="file_a.py", status="modified", staged=False)],
    staged=[GitFile(path="file_b.py", status="added", staged=True)],
    untracked=[GitFile(path="new.txt", status="untracked", staged=False)],
)
_SAMPLE_COMMITS = [
    Commit(
        hash="aaa111",
        message="first commit",
        author="Alice",
        relative_time="2 hours ago",
    ),
    Commit(
        hash="bbb222", message="second commit", author="Bob", relative_time="1 day ago"
    ),
]


def _patch_git_services(status=_EMPTY_STATUS, commits=None):
    """Return a tuple of patches for get_status, get_log, and github services."""
    if commits is None:
        commits = []
    return (
        patch("perch.services.git.get_status", return_value=status),
        patch("perch.services.git.get_log", return_value=commits),
        patch("perch.services.github.get_pr_context", return_value=None),
        patch("perch.services.github.get_checks", return_value=[]),
    )


def _init_git_repo(path: Path) -> None:
    """Initialise a tiny git repo so PerchApp can resolve a branch."""
    import subprocess

    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(path),
        },
    )


class TestGitPanelIsListView:
    """GitPanel should be a ListView subclass."""

    def test_inherits_list_view(self) -> None:
        from textual.widgets import ListView

        assert issubclass(GitPanel, ListView)


class TestUpdateDisplay:
    """Tests for GitPanel._update_display()."""

    async def test_empty_status_shows_placeholders(self, tmp_path: Path) -> None:
        """With no files and no commits, all sections show 'No ...' placeholders."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_EMPTY_STATUS, [])
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                # Force an update so we don't rely on the threaded worker
                panel._update_display(_EMPTY_STATUS, [])
                await pilot.pause()

                children = list(panel.children)
                # Should have 4 section headers + 3 placeholder items = 7
                disabled_items = [
                    c for c in children if isinstance(c, ListItem) and c.disabled
                ]
                assert len(disabled_items) >= 7

    async def test_status_with_files_and_commits(self, tmp_path: Path) -> None:
        """Files and commits are rendered as selectable ListItems."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Check file items exist by name
                names = [
                    c.name for c in panel.children if isinstance(c, ListItem) and c.name
                ]
                assert "file_a.py" in names
                assert "file_b.py" in names
                assert "new.txt" in names
                assert "commit:aaa111" in names
                assert "commit:bbb222" in names

    async def test_update_display_restores_selection(self, tmp_path: Path) -> None:
        """_update_display should restore the previously-selected item."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Find index of file_b.py and select it
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.name == "file_b.py":
                        panel.index = i
                        break

                # Update again — selection should be restored to file_b.py
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                selected_name = panel._get_selected_name()
                assert selected_name == "file_b.py"


class TestGetSelectedName:
    """Tests for _get_selected_name."""

    async def test_returns_none_when_no_selection(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                panel.clear()
                panel.index = None
                assert panel._get_selected_name() is None

    async def test_returns_name_of_selected_item(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Select file_a.py
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.name == "file_a.py":
                        panel.index = i
                        break
                assert panel._get_selected_name() == "file_a.py"


class TestRestoreSelection:
    """Tests for _restore_selection."""

    async def test_restores_by_name(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                panel._restore_selection("file_b.py")
                assert panel._get_selected_name() == "file_b.py"

    async def test_falls_back_to_first_enabled(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Passing None should select the first enabled item
                panel._restore_selection(None)
                selected = panel._get_selected_name()
                # First enabled item should be file_a.py (first non-header)
                assert selected == "file_a.py"


class TestOnListViewSelected:
    """Tests for on_list_view_selected dispatching FileSelected."""

    async def test_file_selected_message(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                mock_post = MagicMock()

                file_item = _make_file_item(
                    GitFile(path="file_a.py", status="modified", staged=False),
                    staged=False,
                )
                from textual.widgets import ListView

                event = ListView.Selected(panel, file_item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.FileSelected)
                assert msg.path == "file_a.py"
                assert msg.staged is False

    async def test_commit_item_returns_early(self, tmp_path: Path) -> None:
        """Commit items should not post a message (handled by app.py)."""
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()

                mock_post = MagicMock()
                commit_item = ListItem(Label("commit"), name="commit:abc123")
                from textual.widgets import ListView

                event = ListView.Selected(panel, commit_item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                mock_post.assert_not_called()

    async def test_none_name_is_ignored(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()

                mock_post = MagicMock()
                item = ListItem(Label("header"))
                from textual.widgets import ListView

                event = ListView.Selected(panel, item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                mock_post.assert_not_called()

    async def test_staged_file_selected_message(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()

                mock_post = MagicMock()
                file_item = _make_file_item(
                    GitFile(path="staged.py", status="added", staged=True), staged=True
                )
                from textual.widgets import ListView

                event = ListView.Selected(panel, file_item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.FileSelected)
                assert msg.staged is True


class TestPageUpDown:
    """Tests for action_page_up and action_page_down."""

    async def test_page_down_moves_index_forward(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Set index to first enabled item
                panel._restore_selection(None)
                old_index = panel.index
                assert old_index is not None

                panel.action_page_down()
                assert panel.index is not None
                assert panel.index >= old_index

    async def test_page_up_moves_index_backward(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Select the last commit item
                last_idx = len(panel.children) - 1
                panel.index = last_idx

                panel.action_page_up()
                assert panel.index is not None
                assert panel.index <= last_idx

    async def test_page_up_with_none_index(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                panel.clear()
                panel.index = None
                # Should not raise
                panel.action_page_up()
                assert panel.index is None

    async def test_page_down_with_none_index(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                panel.clear()
                panel.index = None
                panel.action_page_down()
                assert panel.index is None


class TestShowNotGitRepo:
    """Tests for _show_not_git_repo."""

    async def test_displays_not_git_repo_message(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()

                panel._show_not_git_repo()
                await pilot.pause()

                assert panel._is_git_repo is False
                assert len(panel.children) == 1


class TestDoRefreshRuntimeError:
    """Tests for _do_refresh RuntimeError handling."""

    async def test_runtime_error_shows_not_git_repo(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        # Make get_status raise RuntimeError on the FIRST call so the
        # on_mount refresh triggers _show_not_git_repo.
        with patch(
            "perch.services.git.get_status", side_effect=RuntimeError("not a git repo")
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                # Give the threaded worker time to complete and call back
                for _ in range(20):
                    await pilot.pause()
                assert panel._is_git_repo is False


class TestActivateCurrentSelection:
    """Tests for GitPanel.activate_current_selection()."""

    async def test_returns_false_when_no_selection(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                panel.index = None
                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    result = panel.activate_current_selection()
                assert result is False
                mock_post.assert_not_called()

    async def test_posts_file_selected_for_file_item(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                # _update_display calls _restore_selection which selects the first
                # enabled item (file_a.py — first unstaged file)
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()
                assert panel.index is not None

                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    result = panel.activate_current_selection()
                assert result is True
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.FileSelected)
                assert msg.path == "file_a.py"

    async def test_returns_false_for_commit_item(self, tmp_path: Path) -> None:
        """Commit items should return False (handled by app.py)."""
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_EMPTY_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                # With empty status + commits, first enabled item is the first commit
                panel._update_display(_EMPTY_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()
                assert panel.index is not None

                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    result = panel.activate_current_selection()
                assert result is False
                mock_post.assert_not_called()


class TestActionRefresh:
    """Tests for action_refresh."""

    async def test_action_refresh_calls_do_refresh(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()

                # Patch _do_refresh to track calls
                called = []
                original = panel._do_refresh
                panel._do_refresh = lambda: called.append(True) or original()  # type: ignore[assignment]

                panel.action_refresh()
                assert len(called) == 1


class TestCommitExpandCollapse:
    async def test_toggle_commit_expands(self, git_worktree: Path) -> None:
        """toggle_commit should insert child file items below the commit."""
        from perch.app import PerchApp

        # Create a second commit so diff-tree can compare against a parent
        (git_worktree / "extra.txt").write_text("extra\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add extra file"],
            cwd=git_worktree, check=True,
        )

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            commit_item = None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commit_item = node
                    break
            assert commit_item is not None
            commit_hash = commit_item.name.removeprefix("commit:")

            panel.toggle_commit(commit_hash)
            await pilot.pause()

            assert panel._expanded_commit == commit_hash
            found_child = any(
                isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:")
                for node in panel._nodes
            )
            assert found_child

    async def test_toggle_commit_collapses(self, git_worktree: Path) -> None:
        """Toggling an already expanded commit should remove children."""
        from perch.app import PerchApp

        # Create a second commit so diff-tree can compare against a parent
        (git_worktree / "extra.txt").write_text("extra\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add extra file"],
            cwd=git_worktree, check=True,
        )

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            commit_item = None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commit_item = node
                    break
            assert commit_item is not None
            commit_hash = commit_item.name.removeprefix("commit:")

            panel.toggle_commit(commit_hash)
            await pilot.pause()
            panel.toggle_commit(commit_hash)
            await pilot.pause()

            assert panel._expanded_commit is None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:"):
                    pytest.fail("Child items should be removed after collapse")

    async def test_accordion_collapses_previous(self, git_worktree: Path) -> None:
        """Expanding a new commit should collapse the previously expanded one."""
        from perch.app import PerchApp

        (git_worktree / "second.txt").write_text("second\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "second commit"],
            cwd=git_worktree, check=True,
        )
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            commits = []
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commits.append(node.name.removeprefix("commit:"))
            assert len(commits) >= 2

            panel.toggle_commit(commits[0])
            await pilot.pause()
            panel.toggle_commit(commits[1])
            await pilot.pause()

            assert panel._expanded_commit == commits[1]
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:"):
                    assert node.name.startswith(f"commit-file:{commits[1]}:")


class TestSplitRefresh:
    async def test_file_status_refresh_preserves_commits(self, git_worktree: Path) -> None:
        """_refresh_file_status_worker should not touch commit items."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            commit_count_before = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )
            panel._refresh_file_status_worker()
            await pilot.pause()
            await pilot.pause()
            commit_count_after = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )
            assert commit_count_after == commit_count_before


class TestCommitPagination:
    async def test_load_more_commits(self, git_worktree: Path) -> None:
        """_load_more_commits should append additional commit items."""
        from perch.app import PerchApp

        for i in range(3):
            (git_worktree / f"page{i}.txt").write_text(f"{i}\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(["git", "commit", "-m", f"page commit {i}"], cwd=git_worktree, check=True)
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            panel._commit_page_size = 2
            panel._refresh_commits_section()
            await pilot.pause()
            await pilot.pause()
            initial_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:")
            )
            assert initial_commits == 2
            sentinel = any(
                isinstance(node, ListItem) and node.name == "load-more-commits"
                for node in panel._nodes
            )
            assert sentinel, "Sentinel should be present when more commits exist"
            panel._load_more_commits()
            await pilot.pause()
            await pilot.pause()
            final_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:")
            )
            assert final_commits > initial_commits


class TestRefWatcher:
    async def test_new_commit_triggers_refresh(self, git_worktree: Path) -> None:
        """Making a new commit should trigger a commits refresh via ref watcher."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            initial_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:")
            )
            # Make a new commit
            (git_worktree / "newfile.txt").write_text("new\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(["git", "commit", "-m", "new commit"], cwd=git_worktree, check=True)
            # Wait for ref watcher to detect
            for _ in range(20):
                await pilot.pause(delay=0.2)
            final_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:")
            )
            assert final_commits > initial_commits


# ---------------------------------------------------------------------------
# Coverage: _refresh_file_status_worker RuntimeError (lines 152-153)
# ---------------------------------------------------------------------------
class TestRefreshFileStatusWorkerRuntimeError:
    async def test_runtime_error_is_swallowed(self, tmp_path: Path) -> None:
        """RuntimeError in _refresh_file_status_worker should not crash."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Now make the next refresh fail
                with patch(
                    "perch.services.git.get_status",
                    side_effect=RuntimeError("git not found"),
                ):
                    panel._refresh_file_status_worker()
                    for _ in range(10):
                        await pilot.pause()
                # Panel should still be intact (no crash)
                assert len(list(panel.children)) > 0


# ---------------------------------------------------------------------------
# Coverage: _update_file_sections early return (line 164)
# ---------------------------------------------------------------------------
class TestUpdateFileSectionsNoBoundary:
    async def test_returns_early_when_no_commits_section(self, tmp_path: Path) -> None:
        """_update_file_sections returns early when section-commits not present."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                # Clear everything so there is no section-commits header
                panel.clear()
                await pilot.pause()
                count_before = len(list(panel.children))
                # Should be a no-op (no crash, no change)
                panel._update_file_sections(_SAMPLE_STATUS)
                await pilot.pause()
                count_after = len(list(panel.children))
                assert count_after == count_before


# ---------------------------------------------------------------------------
# Coverage: on_list_view_selected commit-file items (lines 198-199)
# ---------------------------------------------------------------------------
class TestOnListViewSelectedCommitFile:
    async def test_commit_file_item_returns_early(self, tmp_path: Path) -> None:
        """commit-file: items should not post a FileSelected message."""
        from unittest.mock import MagicMock

        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()

                mock_post = MagicMock()
                commit_file_item = ListItem(
                    Label("commit file"), name="commit-file:abc123:file.py"
                )
                from textual.widgets import ListView

                event = ListView.Selected(panel, commit_file_item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Coverage: _refresh_commits_section expanded commit error (lines 273-276)
# ---------------------------------------------------------------------------
class TestRefreshCommitsSectionExpandedError:
    async def test_expanded_commit_error_clears_expansion(self, git_worktree: Path) -> None:
        """If get_commit_files raises during refresh, expanded should be cleared."""
        from perch.app import PerchApp

        (git_worktree / "extra.txt").write_text("extra\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add extra file"],
            cwd=git_worktree, check=True,
        )

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            # Find a commit hash
            commit_item = None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commit_item = node
                    break
            assert commit_item is not None
            commit_hash = commit_item.name.removeprefix("commit:")

            # Expand the commit first
            panel.toggle_commit(commit_hash)
            await pilot.pause()
            assert panel._expanded_commit == commit_hash

            # Now refresh commits with get_commit_files raising
            with patch(
                "perch.services.git.get_commit_files",
                side_effect=RuntimeError("bad commit"),
            ):
                panel._refresh_commits_section()
                for _ in range(10):
                    await pilot.pause()
            # Expansion should be cleared
            assert panel._expanded_commit is None


# ---------------------------------------------------------------------------
# Coverage: _apply_commits_update with expanded files (lines 309-315) and
#           sentinel when commits == page_size (line 329)
# ---------------------------------------------------------------------------
class TestApplyCommitsUpdateExpanded:
    async def test_apply_commits_with_expanded_files(self, tmp_path: Path) -> None:
        """_apply_commits_update should re-expand children for preserved commit."""
        from perch.app import PerchApp
        from perch.models import CommitFile

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                expanded_files = [
                    CommitFile(path="file_a.py", status="modified"),
                    CommitFile(path="file_b.py", status="added"),
                ]
                panel._apply_commits_update(
                    _SAMPLE_COMMITS, "aaa111", expanded_files
                )
                await pilot.pause()

                # Should have commit-file items
                child_names = [
                    n.name for n in panel._nodes
                    if isinstance(n, ListItem) and n.name and n.name.startswith("commit-file:")
                ]
                assert len(child_names) == 2
                assert "commit-file:aaa111:file_a.py" in child_names
                assert panel._expanded_commit == "aaa111"

    async def test_apply_commits_sentinel_at_page_size(self, tmp_path: Path) -> None:
        """When len(commits) == page_size, a load-more sentinel is appended."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Set page size to match the number of commits
                panel._commit_page_size = len(_SAMPLE_COMMITS)
                panel._apply_commits_update(_SAMPLE_COMMITS, None, None)
                await pilot.pause()

                sentinel = any(
                    isinstance(n, ListItem) and n.name == "load-more-commits"
                    for n in panel._nodes
                )
                assert sentinel, "Sentinel should appear when commits == page_size"


# ---------------------------------------------------------------------------
# Coverage: _expand_commit error paths (lines 379, 385-386)
# ---------------------------------------------------------------------------
class TestExpandCommitErrors:
    async def test_expand_commit_not_found(self, tmp_path: Path) -> None:
        """_expand_commit returns early if commit hash not found in nodes."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Try to expand a non-existent commit
                panel._expand_commit("nonexistent_hash")
                await pilot.pause()
                # No crash, no expanded commit
                assert panel._expanded_commit is None

    async def test_expand_commit_runtime_error(self, tmp_path: Path) -> None:
        """_expand_commit catches RuntimeError from get_commit_files."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                with patch(
                    "perch.services.git.get_commit_files",
                    side_effect=RuntimeError("git failed"),
                ):
                    panel._expand_commit("aaa111")
                    await pilot.pause()

                # No child items should be added
                child_items = [
                    n for n in panel._nodes
                    if isinstance(n, ListItem) and n.name
                    and n.name.startswith("commit-file:")
                ]
                assert len(child_items) == 0


# ---------------------------------------------------------------------------
# Coverage: _set_commit_chevron guard conditions (lines 419, 424, 427)
# ---------------------------------------------------------------------------
class TestSetCommitChevronGuards:
    async def test_set_chevron_on_non_list_item(self, tmp_path: Path) -> None:
        """_set_commit_chevron returns early if node isn't a named ListItem."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Index 0 is a section header with no name (or section-header class)
                # It's disabled with name=None
                panel._set_commit_chevron(0, expanded=True)
                # Should not raise

    async def test_set_chevron_bad_content_type(self, tmp_path: Path) -> None:
        """_set_commit_chevron returns early if __content is not Text."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Find a commit item and corrupt its label content
                for i, node in enumerate(panel._nodes):
                    if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                        label = node.query_one(Label)
                        # Set __content to a string instead of Text
                        label._Static__content = "not a Text object"
                        panel._set_commit_chevron(i, expanded=True)
                        break

    async def test_set_chevron_no_arrow_prefix(self, tmp_path: Path) -> None:
        """_set_commit_chevron returns early if text doesn't start with arrow."""
        from perch.app import PerchApp
        from rich.text import Text

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Find a commit item and replace its text with no arrow
                for i, node in enumerate(panel._nodes):
                    if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                        label = node.query_one(Label)
                        label._Static__content = Text("no arrow here")
                        panel._set_commit_chevron(i, expanded=True)
                        break


# ---------------------------------------------------------------------------
# Coverage: _get_git_dir worktree .git file (lines 452-454)
# ---------------------------------------------------------------------------
class TestGetGitDirWorktree:
    async def test_git_file_redirect(self, tmp_path: Path) -> None:
        """When .git is a file (worktree), _get_git_dir follows the redirect."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        real_git_dir = tmp_path / ".real_git"
        real_git_dir.mkdir()
        (real_git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        # Create a worktree-like .git file
        worktree_dir = tmp_path / "wt"
        worktree_dir.mkdir()
        (worktree_dir / ".git").write_text(f"gitdir: {real_git_dir}")
        (worktree_dir / "hello.py").write_text("print('hi')\n")

        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(worktree_dir)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                result = panel._get_git_dir()
                assert result == real_git_dir


# ---------------------------------------------------------------------------
# Coverage: _update_ref_mtimes packed refs fallback (lines 464-468)
# ---------------------------------------------------------------------------
class TestUpdateRefMtimesFallback:
    async def test_packed_refs_fallback(self, git_worktree: Path) -> None:
        """When ref file doesn't exist, _update_ref_mtimes checks packed-refs."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            # Rename the ref file so it doesn't exist
            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))

            # Create a packed-refs file
            packed = git_dir / "packed-refs"
            packed.write_text("# pack-refs\n")

            panel._update_ref_mtimes()
            assert panel._last_ref_mtime is None
            assert panel._last_head_mtime is not None or panel._last_packed_mtime is not None


# ---------------------------------------------------------------------------
# Coverage: _check_refs packed refs polling (lines 482-487) and branch change (492-494)
# ---------------------------------------------------------------------------
class TestCheckRefsPacked:
    async def test_check_refs_packed_fallback_triggers_refresh(self, git_worktree: Path) -> None:
        """When ref file doesn't exist, _check_refs uses HEAD/packed-refs."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            # First, set mtimes with ref file absent
            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))

            packed = git_dir / "packed-refs"
            packed.write_text("# initial\n")
            panel._update_ref_mtimes()

            # Now change packed-refs to simulate a change
            import time
            time.sleep(0.05)
            packed.write_text("# changed\n")

            refresh_called = []
            original = panel._refresh_commits_section
            panel._refresh_commits_section = lambda: refresh_called.append(True) or original()

            panel._check_refs()
            assert len(refresh_called) == 1

    async def test_check_refs_branch_change(self, git_worktree: Path) -> None:
        """_check_refs detects branch name changes."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            # Remove ref file to enter packed-refs path
            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))
            packed = git_dir / "packed-refs"
            packed.write_text("# v1\n")
            panel._update_ref_mtimes()

            # Change packed-refs and mock a branch change
            import time
            time.sleep(0.05)
            packed.write_text("# v2\n")

            with patch(
                "perch.services.git.get_current_branch",
                return_value="new-branch",
            ):
                panel._check_refs()

            assert panel._watched_branch == "new-branch"

    async def test_check_refs_branch_error(self, git_worktree: Path) -> None:
        """_check_refs handles RuntimeError from get_current_branch."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            # Remove ref file
            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))
            packed = git_dir / "packed-refs"
            packed.write_text("# v1\n")
            panel._update_ref_mtimes()

            import time
            time.sleep(0.05)
            packed.write_text("# v2\n")

            old_branch = panel._watched_branch
            with patch(
                "perch.services.git.get_current_branch",
                side_effect=RuntimeError("detached HEAD"),
            ):
                panel._check_refs()

            # Branch should not change on error
            assert panel._watched_branch == old_branch


# ---------------------------------------------------------------------------
# Coverage: _update_display sentinel (lines 198-199) and
#           _load_more_commits early return (line 329)
# ---------------------------------------------------------------------------
class TestUpdateDisplaySentinel:
    async def test_update_display_adds_sentinel_at_page_size(self, tmp_path: Path) -> None:
        """_update_display adds load-more sentinel when commits == page_size."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()

                # Set page size to match sample commits count
                panel._commit_page_size = len(_SAMPLE_COMMITS)
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                sentinel = any(
                    isinstance(n, ListItem) and n.name == "load-more-commits"
                    for n in panel._nodes
                )
                assert sentinel


class TestLoadMoreCommitsEarlyReturn:
    async def test_loading_more_flag_prevents_duplicate(self, git_worktree: Path) -> None:
        """_load_more_commits returns early when _loading_more is True."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            panel._loading_more = True
            count_before = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:")
            )
            panel._load_more_commits()
            for _ in range(5):
                await pilot.pause()
            count_after = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:")
            )
            # No new commits should be loaded
            assert count_after == count_before


# ---------------------------------------------------------------------------
# Coverage: activate_current_selection for commit-file items
# ---------------------------------------------------------------------------
class TestActivateCurrentSelectionCommitFile:
    async def test_returns_false_for_commit_file_item(self, tmp_path: Path) -> None:
        """commit-file: items should return False from activate_current_selection."""
        from unittest.mock import MagicMock

        from perch.app import PerchApp
        from perch.models import CommitFile

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                # Expand the first commit to get commit-file items
                expanded_files = [
                    CommitFile(path="file_a.py", status="modified"),
                ]
                panel._apply_commits_update(
                    _SAMPLE_COMMITS, "aaa111", expanded_files
                )
                await pilot.pause()

                # Find and select a commit-file item
                for i, node in enumerate(panel._nodes):
                    if isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:"):
                        panel.index = i
                        break

                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    result = panel.activate_current_selection()
                assert result is False
                mock_post.assert_not_called()
