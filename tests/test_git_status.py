"""Tests for the compound GitPanel widget (ListView files + Tree commits)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from textual.widgets import Label, ListItem, ListView

from perch.models import Commit, CommitFile, GitFile, GitStatusData
from perch.widgets.git_status import (
    CommitTree,
    GitPanel,
    _make_file_item,
    _make_section_header,
)


# ---------------------------------------------------------------------------
# Pure helper tests (no async / no app needed)
# ---------------------------------------------------------------------------


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


class TestNewMessages:
    """Tests for the new message types."""

    def test_commit_highlighted(self) -> None:
        msg = GitPanel.CommitHighlighted(commit_hash="abc123")
        assert msg.commit_hash == "abc123"

    def test_commit_file_highlighted(self) -> None:
        msg = GitPanel.CommitFileHighlighted(commit_hash="abc123", path="file.py")
        assert msg.commit_hash == "abc123"
        assert msg.path == "file.py"

    def test_commit_toggled(self) -> None:
        msg = GitPanel.CommitToggled(commit_hash="abc123")
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
        hash="bbb222",
        message="second commit",
        author="Bob",
        relative_time="1 day ago",
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


# ---------------------------------------------------------------------------
# Composition tests
# ---------------------------------------------------------------------------


class TestGitPanelComposition:
    """GitPanel should be a Vertical container with both sub-widgets."""

    def test_is_vertical_not_list_view(self) -> None:
        from textual.containers import Vertical

        assert issubclass(GitPanel, Vertical)
        assert not issubclass(GitPanel, ListView)

    async def test_has_file_list_and_commit_tree(self, git_worktree):
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            assert panel._file_list is not None
            assert isinstance(panel._file_list, ListView)
            assert panel._commit_tree is not None
            assert isinstance(panel._commit_tree, CommitTree)
            # Tree root is hidden
            assert panel._commit_tree.show_root is False


# ---------------------------------------------------------------------------
# File list behaviour
# ---------------------------------------------------------------------------


class TestFileListBehavior:
    async def test_file_sections_populated(self, git_worktree):
        """File sections should appear in the internal ListView."""
        (git_worktree / "hello.py").write_text("modified\n")
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            file_items = [
                node
                for node in panel._file_list._nodes
                if isinstance(node, ListItem) and node.name and not node.disabled
            ]
            assert len(file_items) > 0

    async def test_empty_status_shows_placeholders(self, tmp_path: Path) -> None:
        """With no files, all sections show 'No ...' placeholders."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_EMPTY_STATUS, [])
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                # Force update
                panel._update_display(_EMPTY_STATUS, [])
                await pilot.pause()

                children = list(panel._file_list.children)
                disabled_items = [
                    c for c in children if isinstance(c, ListItem) and c.disabled
                ]
                # 3 section headers + 3 "No ..." placeholders = 6 disabled items
                assert len(disabled_items) >= 6


# ---------------------------------------------------------------------------
# Commit tree behaviour
# ---------------------------------------------------------------------------


class TestCommitTreeBehavior:
    async def test_commits_appear_as_tree_nodes(self, git_worktree):
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            commit_nodes = [
                n for n in root.children if n.data and n.data.startswith("commit:")
            ]
            assert len(commit_nodes) >= 1

    async def test_expand_commit_shows_files(self, git_worktree):
        """Expanding a commit node should add file children."""
        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify"], cwd=git_worktree, check=True)

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")
            panel.toggle_commit(commit_hash)
            # Wait for background worker to fetch and populate files
            for _ in range(10):
                await pilot.pause()
            assert commit_node.is_expanded
            file_children = [
                c
                for c in commit_node.children
                if c.data and c.data.startswith("commit-file:")
            ]
            assert len(file_children) >= 1

    async def test_toggle_commit_collapses(self, git_worktree):
        """Toggling an expanded commit should collapse it."""
        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify"], cwd=git_worktree, check=True)

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")
            panel.toggle_commit(commit_hash)
            for _ in range(10):
                await pilot.pause()
            assert panel._expanded_commit == commit_hash
            panel.toggle_commit(commit_hash)
            await pilot.pause()
            assert panel._expanded_commit is None
            assert not commit_node.is_expanded

    async def test_accordion_collapses_previous(self, git_worktree):
        """Expanding one commit should collapse the previously expanded one."""
        (git_worktree / "f1.txt").write_text("1\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "c1"], cwd=git_worktree, check=True)
        (git_worktree / "f2.txt").write_text("2\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "c2"], cwd=git_worktree, check=True)

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            commits = [
                n for n in root.children if n.data and n.data.startswith("commit:")
            ]
            assert len(commits) >= 2
            h1 = commits[0].data.removeprefix("commit:")
            h2 = commits[1].data.removeprefix("commit:")
            panel.toggle_commit(h1)
            for _ in range(10):
                await pilot.pause()
            assert commits[0].is_expanded
            panel.toggle_commit(h2)
            for _ in range(10):
                await pilot.pause()
            assert commits[1].is_expanded
            assert not commits[0].is_expanded

    async def test_arrow_down_crosses_to_commit_tree(self, git_worktree):
        """Arrow down at end of file list should focus the commit tree."""
        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify"], cwd=git_worktree, check=True)

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            panel.focus_default()
            await pilot.pause()
            # Navigate to last file list item
            last_idx = len(panel._file_list) - 1
            panel._file_list.index = last_idx
            await pilot.pause()
            # Press down arrow — should cross to commit tree
            await pilot.press("down")
            await pilot.pause()
            assert panel._commit_tree.has_focus

    async def test_arrow_up_crosses_to_file_list(self, git_worktree):
        """Arrow up at top of commit tree should focus the file list."""
        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify"], cwd=git_worktree, check=True)

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            # Focus commit tree at line 0
            panel._commit_tree.focus()
            panel._commit_tree.cursor_line = 0
            await pilot.pause()
            # Press up arrow — should cross to file list
            await pilot.press("up")
            await pilot.pause()
            assert panel._file_list.has_focus


# ---------------------------------------------------------------------------
# Delegate API
# ---------------------------------------------------------------------------


class TestGitPanelDelegateAPI:
    async def test_highlighted_item_name_from_file_list(self, tmp_path: Path):
        """highlighted_item_name should return file list selection when file list has focus."""
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
                panel._file_list.focus()
                await pilot.pause()
                name = panel.highlighted_item_name()
                assert name is not None

    async def test_highlighted_item_name_returns_none_when_empty(self, tmp_path: Path):
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                panel._file_list.clear()
                panel._file_list.index = None
                await pilot.pause()
                name = panel.highlighted_item_name()
                assert name is None


# ---------------------------------------------------------------------------
# FileSelected message
# ---------------------------------------------------------------------------


class TestOnListViewSelected:
    """Tests for the file list dispatching FileSelected."""

    async def test_file_selected_message(self, tmp_path: Path) -> None:
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
                event = ListView.Selected(panel._file_list, file_item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.FileSelected)
                assert msg.path == "file_a.py"
                assert msg.staged is False

    async def test_none_name_is_ignored(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                mock_post = MagicMock()
                item = ListItem(Label("header"))
                event = ListView.Selected(panel._file_list, item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                mock_post.assert_not_called()

    async def test_staged_file_selected_message(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                mock_post = MagicMock()
                file_item = _make_file_item(
                    GitFile(path="staged.py", status="added", staged=True),
                    staged=True,
                )
                event = ListView.Selected(panel._file_list, file_item, index=0)
                with patch.object(panel, "post_message", mock_post):
                    panel.on_list_view_selected(event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.FileSelected)
                assert msg.staged is True


# ---------------------------------------------------------------------------
# Refresh behaviour
# ---------------------------------------------------------------------------


class TestRefreshBehavior:
    async def test_refresh_files_preserves_tree(self, git_worktree):
        """refresh_files should not touch the commit tree."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            commit_count = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            assert commit_count >= 1
            panel.refresh_files()
            for _ in range(10):
                await pilot.pause()
            new_count = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            assert new_count == commit_count

    async def test_action_refresh_calls_do_refresh(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()

                called = []
                original = panel._do_refresh

                panel._do_refresh = lambda: called.append(True) or original()  # type: ignore[assignment]
                panel.action_refresh()
                assert len(called) == 1


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    async def test_sentinel_appears(self, git_worktree):
        """Sentinel node should appear when page is full."""
        for i in range(3):
            (git_worktree / f"p{i}.txt").write_text(f"{i}\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"c{i}"], cwd=git_worktree, check=True
            )

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            panel._commit_page_size = 2
            panel.refresh_commits()
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            sentinel = any(n.data == "load-more-commits" for n in root.children)
            assert sentinel

    async def test_load_more_commits(self, git_worktree):
        """_load_more_commits should append additional commit nodes."""
        for i in range(3):
            (git_worktree / f"page{i}.txt").write_text(f"{i}\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"page commit {i}"],
                cwd=git_worktree,
                check=True,
            )

        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            panel._commit_page_size = 2
            panel.refresh_commits()
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            initial_commits = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            assert initial_commits == 2
            panel._load_more_commits()
            for _ in range(10):
                await pilot.pause()
            final_commits = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            assert final_commits > initial_commits

    async def test_loading_more_flag_prevents_duplicate(self, git_worktree):
        """_load_more_commits returns early when _loading_more is True."""
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            panel._loading_more = True
            root = panel._commit_tree.root
            count_before = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            panel._load_more_commits()
            for _ in range(5):
                await pilot.pause()
            count_after = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            assert count_after == count_before


# ---------------------------------------------------------------------------
# Not a git repo
# ---------------------------------------------------------------------------


class TestShowNotGitRepo:
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
                assert len(list(panel._file_list.children)) == 1


class TestDoRefreshRuntimeError:
    async def test_runtime_error_shows_not_git_repo(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        with patch(
            "perch.services.git.get_status",
            side_effect=RuntimeError("not a git repo"),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                for _ in range(20):
                    await pilot.pause()
                assert panel._is_git_repo is False


# ---------------------------------------------------------------------------
# activate_current_selection
# ---------------------------------------------------------------------------


class TestActivateCurrentSelection:
    async def test_returns_false_when_no_selection(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                panel._file_list.index = None
                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    result = panel.activate_current_selection()
                assert result is False
                mock_post.assert_not_called()

    async def test_posts_file_selected_for_file_item(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()
                assert panel._file_list.index is not None

                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    result = panel.activate_current_selection()
                assert result is True
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.FileSelected)
                assert msg.path == "file_a.py"


# ---------------------------------------------------------------------------
# Selection restore
# ---------------------------------------------------------------------------


class TestRestoreSelection:
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

                panel._restore_selection(None)
                selected = panel._get_selected_name()
                assert selected == "file_a.py"

    async def test_update_display_restores_selection(self, tmp_path: Path) -> None:
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

                # Find and select file_b.py
                for i, child in enumerate(panel._file_list._nodes):
                    if isinstance(child, ListItem) and child.name == "file_b.py":
                        panel._file_list.index = i
                        break

                # Update again -- selection should be restored
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()
                assert panel._get_selected_name() == "file_b.py"


# ---------------------------------------------------------------------------
# Refresh file status RuntimeError
# ---------------------------------------------------------------------------


class TestRefreshFileStatusWorkerRuntimeError:
    async def test_runtime_error_is_swallowed(self, tmp_path: Path) -> None:
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
                    "perch.services.git.get_status",
                    side_effect=RuntimeError("git not found"),
                ):
                    panel._refresh_file_status_worker()
                    for _ in range(10):
                        await pilot.pause()
                assert len(list(panel._file_list.children)) > 0


# ---------------------------------------------------------------------------
# Commits section refresh with expanded state
# ---------------------------------------------------------------------------


class TestRefreshCommitsSectionExpanded:
    async def test_expanded_commit_error_clears_expansion(self, git_worktree):
        from perch.app import PerchApp

        (git_worktree / "extra.txt").write_text("extra\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add extra file"],
            cwd=git_worktree,
            check=True,
        )

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()

            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")
            panel.toggle_commit(commit_hash)
            await pilot.pause()
            assert panel._expanded_commit == commit_hash

            with patch(
                "perch.services.git.get_commit_files",
                side_effect=RuntimeError("bad commit"),
            ):
                panel._refresh_commits_section()
                for _ in range(10):
                    await pilot.pause()
            assert panel._expanded_commit is None

    async def test_apply_commits_with_expanded_files(self, tmp_path: Path) -> None:
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

                expanded_files = [
                    CommitFile(path="file_a.py", status="modified"),
                    CommitFile(path="file_b.py", status="added"),
                ]
                panel._apply_commits_update(_SAMPLE_COMMITS, "aaa111", expanded_files)
                await pilot.pause()

                # Find the expanded node
                root = panel._commit_tree.root
                expanded_node = next(
                    n for n in root.children if n.data == "commit:aaa111"
                )
                child_data = [c.data for c in expanded_node.children]
                assert len(child_data) == 2
                assert "commit-file:aaa111:file_a.py" in child_data
                assert panel._expanded_commit == "aaa111"

    async def test_apply_commits_sentinel_at_page_size(self, tmp_path: Path) -> None:
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

                panel._commit_page_size = len(_SAMPLE_COMMITS)
                panel._apply_commits_update(_SAMPLE_COMMITS, None, None)
                await pilot.pause()

                root = panel._commit_tree.root
                sentinel = any(n.data == "load-more-commits" for n in root.children)
                assert sentinel, "Sentinel should appear when commits == page_size"


# ---------------------------------------------------------------------------
# toggle_commit error paths
# ---------------------------------------------------------------------------


class TestToggleCommitErrors:
    async def test_toggle_commit_not_found(self, tmp_path: Path) -> None:
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

                panel.toggle_commit("nonexistent_hash")
                await pilot.pause()
                assert panel._expanded_commit is None

    async def test_toggle_commit_runtime_error(self, tmp_path: Path) -> None:
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
                    panel.toggle_commit("aaa111")
                    for _ in range(10):
                        await pilot.pause()

                # Node expands with loading placeholder, but files are not populated
                commit_node = next(
                    n
                    for n in panel._commit_tree.root.children
                    if n.data == "commit:aaa111"
                )
                file_children = [
                    c
                    for c in commit_node.children
                    if c.data and c.data.startswith("commit-file:")
                ]
                assert len(file_children) == 0


# ---------------------------------------------------------------------------
# Ref watcher
# ---------------------------------------------------------------------------


class TestRefWatcher:
    async def test_new_commit_triggers_refresh(self, git_worktree):
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            for _ in range(10):
                await pilot.pause()
            root = panel._commit_tree.root
            initial_commits = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            # Make a new commit.
            #
            # The running app has background workers (file status refresh every
            # 5s, ref watcher every 2.5s) that run git commands on this same
            # repo.  Those commands can hold .git/index.lock, causing our
            # `git add` / `git commit` to fail with "index.lock: File exists".
            # We retry up to 5 times with short sleeps to wait out the lock.
            import time as _time

            (git_worktree / "newfile.txt").write_text("new\n")
            for _attempt in range(5):
                lock = git_worktree / ".git" / "index.lock"
                if lock.exists():
                    _time.sleep(0.5)
                    continue
                try:
                    subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
                    subprocess.run(
                        ["git", "commit", "-m", "new commit"],
                        cwd=git_worktree,
                        check=True,
                    )
                    break
                except subprocess.CalledProcessError:
                    if _attempt == 4:
                        raise
                    _time.sleep(0.5)
            # Wait for ref watcher
            for _ in range(20):
                await pilot.pause(delay=0.2)
            final_commits = len(
                [n for n in root.children if n.data and n.data.startswith("commit:")]
            )
            assert final_commits > initial_commits


class TestGetGitDirWorktree:
    async def test_git_file_redirect(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        real_git_dir = tmp_path / ".real_git"
        real_git_dir.mkdir()
        (real_git_dir / "HEAD").write_text("ref: refs/heads/main\n")

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


class TestUpdateRefMtimesFallback:
    async def test_packed_refs_fallback(self, git_worktree) -> None:
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))

            packed = git_dir / "packed-refs"
            packed.write_text("# pack-refs\n")

            panel._update_ref_mtimes()
            assert panel._last_ref_mtime is None
            assert (
                panel._last_head_mtime is not None
                or panel._last_packed_mtime is not None
            )


class TestCheckRefsPacked:
    async def test_check_refs_packed_fallback_triggers_refresh(self, git_worktree):
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))

            packed = git_dir / "packed-refs"
            packed.write_text("# initial\n")
            panel._update_ref_mtimes()

            import time

            time.sleep(0.05)
            packed.write_text("# changed\n")

            refresh_called = []
            original = panel._refresh_commits_section
            panel._refresh_commits_section = lambda: (
                refresh_called.append(True) or original()
            )

            panel._check_refs()
            assert len(refresh_called) == 1

    async def test_check_refs_branch_change(self, git_worktree):
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

            if ref_file.exists():
                ref_file.rename(ref_file.with_suffix(".bak"))
            packed = git_dir / "packed-refs"
            packed.write_text("# v1\n")
            panel._update_ref_mtimes()

            import time

            time.sleep(0.05)
            packed.write_text("# v2\n")

            with patch(
                "perch.services.git.get_current_branch",
                return_value="new-branch",
            ):
                panel._check_refs()

            assert panel._watched_branch == "new-branch"

    async def test_check_refs_branch_error(self, git_worktree):
        from perch.app import PerchApp

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            git_dir = panel._get_git_dir()
            ref_file = git_dir / "refs" / "heads" / panel._watched_branch

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

            assert panel._watched_branch == old_branch


# ---------------------------------------------------------------------------
# Update display sentinel
# ---------------------------------------------------------------------------


class TestUpdateDisplaySentinel:
    async def test_update_display_adds_sentinel_at_page_size(
        self, tmp_path: Path
    ) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()

                panel._commit_page_size = len(_SAMPLE_COMMITS)
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                root = panel._commit_tree.root
                sentinel = any(n.data == "load-more-commits" for n in root.children)
                assert sentinel


# ---------------------------------------------------------------------------
# Navigation: j/k/pageup/pagedown cross-widget boundary handling
# ---------------------------------------------------------------------------


class TestNavigationActions:
    """Tests for action_cursor_down/up/select/page_up/page_down."""

    async def test_cursor_down_transfers_focus_to_tree(self, tmp_path: Path) -> None:
        """At the bottom of the file list, j should transfer focus to the tree."""
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

                # Focus file list and move to the last item
                panel._file_list.focus()
                await pilot.pause()
                panel._file_list.index = len(panel._file_list) - 1
                await pilot.pause()

                # action_cursor_down should transfer focus to commit tree
                panel.action_cursor_down()
                await pilot.pause()
                assert panel._commit_tree.has_focus

    async def test_cursor_down_in_middle_stays_in_file_list(
        self, tmp_path: Path
    ) -> None:
        """In the middle of the file list, j should just move down."""
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

                panel._file_list.focus()
                await pilot.pause()
                # Set index to first enabled item (not at boundary)
                panel._file_list.index = 1
                await pilot.pause()

                panel.action_cursor_down()
                await pilot.pause()
                assert panel._file_list.has_focus

    async def test_cursor_down_in_tree(self, tmp_path: Path) -> None:
        """When commit tree has focus, j should move down within the tree."""
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

                panel._commit_tree.focus()
                await pilot.pause()
                panel.action_cursor_down()
                await pilot.pause()
                assert panel._commit_tree.has_focus

    async def test_cursor_up_transfers_focus_to_file_list(self, tmp_path: Path) -> None:
        """At the top of the tree, k should transfer focus to the file list."""
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

                # Focus tree and set cursor to line 0 (top)
                panel._commit_tree.focus()
                await pilot.pause()
                panel._commit_tree.cursor_line = 0
                await pilot.pause()

                panel.action_cursor_up()
                await pilot.pause()
                assert panel._file_list.has_focus

    async def test_cursor_up_in_tree_not_at_top(self, tmp_path: Path) -> None:
        """When not at the top of the tree, k should move up within the tree."""
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

                panel._commit_tree.focus()
                await pilot.pause()
                # Move to line 1 so we're not at top
                panel._commit_tree.cursor_line = 1
                await pilot.pause()

                panel.action_cursor_up()
                await pilot.pause()
                assert panel._commit_tree.has_focus

    async def test_cursor_up_in_file_list(self, tmp_path: Path) -> None:
        """When file list has focus, k should move up within the file list."""
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

                panel._file_list.focus()
                await pilot.pause()
                panel._file_list.index = 3
                await pilot.pause()

                panel.action_cursor_up()
                await pilot.pause()
                assert panel._file_list.has_focus

    async def test_select_cursor_on_tree(self, tmp_path: Path) -> None:
        """action_select_cursor should delegate to commit tree when it has focus."""
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

                panel._commit_tree.focus()
                await pilot.pause()
                with patch.object(panel._commit_tree, "action_select_cursor") as mock:
                    panel.action_select_cursor()
                    mock.assert_called_once()

    async def test_select_cursor_on_file_list(self, tmp_path: Path) -> None:
        """action_select_cursor should delegate to file list when it has focus."""
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

                panel._file_list.focus()
                await pilot.pause()
                with patch.object(panel._file_list, "action_select_cursor") as mock:
                    panel.action_select_cursor()
                    mock.assert_called_once()

    async def test_page_up_on_tree(self, tmp_path: Path) -> None:
        """action_page_up should delegate to tree when it has focus."""
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

                panel._commit_tree.focus()
                await pilot.pause()
                with patch.object(panel._commit_tree, "action_page_up") as mock:
                    panel.action_page_up()
                    mock.assert_called_once()

    async def test_page_up_on_file_list(self, tmp_path: Path) -> None:
        """action_page_up should adjust file list index when it has focus."""
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

                panel._file_list.focus()
                await pilot.pause()
                # Set index to something > 0 so page up can move it
                panel._file_list.index = 5
                await pilot.pause()

                panel.action_page_up()
                await pilot.pause()
                # Index should have decreased or stayed at 0
                assert panel._file_list.index is not None
                assert panel._file_list.index <= 5

    async def test_page_down_on_tree(self, tmp_path: Path) -> None:
        """action_page_down should delegate to tree when it has focus."""
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

                panel._commit_tree.focus()
                await pilot.pause()
                with patch.object(panel._commit_tree, "action_page_down") as mock:
                    panel.action_page_down()
                    mock.assert_called_once()

    async def test_page_down_on_file_list(self, tmp_path: Path) -> None:
        """action_page_down should adjust file list index when it has focus."""
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

                panel._file_list.focus()
                await pilot.pause()
                panel._file_list.index = 0
                await pilot.pause()

                panel.action_page_down()
                await pilot.pause()
                assert panel._file_list.index is not None


# ---------------------------------------------------------------------------
# Tree event handling: on_tree_node_highlighted / on_tree_node_selected
# ---------------------------------------------------------------------------


class TestTreeEventHandling:
    """Tests for tree node highlighted/selected dispatching messages."""

    async def test_commit_node_highlighted_posts_message(self, tmp_path: Path) -> None:
        """Highlighting a commit node should post CommitHighlighted."""
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

                # Find a commit node
                commit_node = next(
                    n
                    for n in panel._commit_tree.root.children
                    if n.data and n.data.startswith("commit:")
                )
                mock_post = MagicMock()
                # Create a fake event with the right .node attribute
                fake_event = MagicMock()
                fake_event.node = commit_node
                with patch.object(panel, "post_message", mock_post):
                    panel.on_tree_node_highlighted(fake_event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.CommitHighlighted)
                assert msg.commit_hash == "aaa111"

    async def test_commit_file_node_highlighted_posts_message(
        self, tmp_path: Path
    ) -> None:
        """Highlighting a commit-file node should post CommitFileHighlighted."""
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

                # Add a commit-file child to a commit node
                commit_node = next(
                    n
                    for n in panel._commit_tree.root.children
                    if n.data and n.data.startswith("commit:")
                )
                file_child = commit_node.add_leaf(
                    "file.py", data="commit-file:aaa111:file.py"
                )

                mock_post = MagicMock()
                fake_event = MagicMock()
                fake_event.node = file_child
                with patch.object(panel, "post_message", mock_post):
                    panel.on_tree_node_highlighted(fake_event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.CommitFileHighlighted)
                assert msg.commit_hash == "aaa111"
                assert msg.path == "file.py"

    async def test_load_more_sentinel_highlighted_triggers_load(
        self, tmp_path: Path
    ) -> None:
        """Highlighting the sentinel node should trigger _load_more_commits."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._commit_page_size = len(_SAMPLE_COMMITS)
                panel._update_display(_SAMPLE_STATUS, _SAMPLE_COMMITS)
                await pilot.pause()

                sentinel = next(
                    n
                    for n in panel._commit_tree.root.children
                    if n.data == "load-more-commits"
                )
                fake_event = MagicMock()
                fake_event.node = sentinel
                with patch.object(panel, "_load_more_commits") as mock:
                    panel.on_tree_node_highlighted(fake_event)
                    mock.assert_called_once()

    async def test_commit_node_selected_posts_toggled(self, tmp_path: Path) -> None:
        """Selecting a commit node should post CommitToggled."""
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

                commit_node = next(
                    n
                    for n in panel._commit_tree.root.children
                    if n.data and n.data.startswith("commit:")
                )
                mock_post = MagicMock()
                fake_event = MagicMock()
                fake_event.node = commit_node
                with patch.object(panel, "post_message", mock_post):
                    panel.on_tree_node_selected(fake_event)
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitPanel.CommitToggled)
                assert msg.commit_hash == "aaa111"

    async def test_none_data_node_highlighted_is_noop(self, tmp_path: Path) -> None:
        """Highlighting a node with None data should not post any message."""
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, _SAMPLE_COMMITS)
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()

                # Root node has data=None
                root = panel._commit_tree.root
                mock_post = MagicMock()
                fake_event = MagicMock()
                fake_event.node = root
                with patch.object(panel, "post_message", mock_post):
                    panel.on_tree_node_highlighted(fake_event)
                mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# highlighted_item_name when commit tree has focus
# ---------------------------------------------------------------------------


class TestHighlightedItemNameFromTree:
    """Test highlighted_item_name returns tree data when tree has focus."""

    async def test_returns_commit_data(self, tmp_path: Path) -> None:
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

                panel._commit_tree.focus()
                await pilot.pause()
                # Move cursor to the first visible line (first commit node)
                panel._commit_tree.cursor_line = 0
                await pilot.pause()
                name = panel.highlighted_item_name()
                assert name is not None
                assert name.startswith("commit:")

    async def test_returns_none_when_tree_empty(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services(_SAMPLE_STATUS, [])
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                await pilot.pause()
                panel._update_display(_SAMPLE_STATUS, [])
                await pilot.pause()

                panel._commit_tree.focus()
                await pilot.pause()
                name = panel.highlighted_item_name()
                # With no children, cursor_node may be root with data=None
                assert name is None


# ---------------------------------------------------------------------------
# _update_file_sections
# ---------------------------------------------------------------------------


class TestUpdateFileSections:
    """Tests for the file-only refresh path."""

    async def test_update_file_sections_rebuilds_list(self, tmp_path: Path) -> None:
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

                # Update with different status
                new_status = GitStatusData(
                    unstaged=[
                        GitFile(path="changed.py", status="modified", staged=False)
                    ],
                )
                panel._update_file_sections(new_status)
                await pilot.pause()

                # Check that the new file appears
                names = [
                    n.name
                    for n in panel._file_list._nodes
                    if isinstance(n, ListItem) and n.name
                ]
                assert "changed.py" in names


# ---------------------------------------------------------------------------
# activate_current_selection with commit-prefixed names
# ---------------------------------------------------------------------------


class TestActivateCurrentSelectionCommitPrefix:
    """Test that activate_current_selection returns False for commit items."""

    async def test_commit_prefixed_returns_false(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        _init_git_repo(tmp_path)
        patches = _patch_git_services()
        with patches[0], patches[1], patches[2], patches[3]:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitPanel)
                await pilot.pause()
                # Manually insert a commit-prefixed item
                panel._file_list.clear()
                item = ListItem(Label("commit item"), name="commit:abc123")
                panel._file_list.append(item)
                panel._file_list.index = 0
                await pilot.pause()

                result = panel.activate_current_selection()
                assert result is False


# ---------------------------------------------------------------------------
# focus_default
# ---------------------------------------------------------------------------


class TestFocusDefault:
    """Tests for GitPanel.focus_default() public API."""

    async def test_focus_default_focuses_file_list(self, tmp_path: Path) -> None:
        """focus_default() should focus the internal file list widget."""
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

                # Focus something else first (the commit tree)
                panel._commit_tree.focus()
                await pilot.pause()
                assert not panel._file_list.has_focus

                # Call focus_default and verify file list gets focus
                panel.focus_default()
                await pilot.pause()
                assert panel._file_list.has_focus
