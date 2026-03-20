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


class TestCommitSelectedMessage:
    """Tests for GitPanel.CommitSelected message."""

    def test_attributes(self) -> None:
        msg = GitPanel.CommitSelected(commit_hash="abc123")
        assert msg.commit_hash == "abc123"


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
    """Tests for on_list_view_selected dispatching FileSelected / CommitSelected."""

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

    async def test_commit_selected_message(self, tmp_path: Path) -> None:
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
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.CommitSelected)
                assert msg.commit_hash == "abc123"

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

    async def test_posts_commit_selected_for_commit_item(self, tmp_path: Path) -> None:
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
                assert result is True
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.CommitSelected)
                assert msg.commit_hash in {"aaa111", "bbb222"}


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
