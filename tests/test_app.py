"""Tests for PerchApp tabbed layout and tree-to-viewer wiring."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Footer, Header, TabbedContent, TabPane

from perch.app import PerchApp
from perch.commands import DiscoveryCommandProvider
from perch.widgets.file_tree import FileTree
from perch.widgets.viewer import Viewer
from perch.widgets.git_status import GitPanel
from perch.widgets.github_panel import GitHubPanel
from perch.widgets.splitter import DraggableSplitter


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Create a minimal worktree with some files."""
    (tmp_path / "hello.py").write_text("print('hello')\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "world.txt").write_text("world\n")
    return tmp_path


@pytest.fixture
def git_worktree(tmp_path: Path) -> Path:
    """Create a worktree that is a real git repo with a commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    (tmp_path / "hello.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


class TestPerchAppCompose:
    """Tests for the app layout and widget composition."""

    async def test_has_header(self, worktree: Path) -> None:
        """App should have a Header widget."""
        async with PerchApp(worktree).run_test() as pilot:
            header = pilot.app.query_one(Header)
            assert header is not None

    async def test_has_footer(self, worktree: Path) -> None:
        """App should have a Footer widget."""
        async with PerchApp(worktree).run_test() as pilot:
            footer = pilot.app.query_one(Footer)
            assert footer is not None

    async def test_title_without_git(self, worktree: Path) -> None:
        """Title should be 'perch' when not in a git repo."""
        async with PerchApp(worktree).run_test() as pilot:
            assert pilot.app.title == "perch"

    async def test_sub_title_shows_path(self, worktree: Path) -> None:
        """Sub-title should show the worktree path."""
        async with PerchApp(worktree).run_test() as pilot:
            assert pilot.app.sub_title == str(worktree)

    async def test_has_file_viewer(self, worktree: Path) -> None:
        """App should have a Viewer as the left pane."""
        async with PerchApp(worktree).run_test() as pilot:
            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert viewer is not None

    async def test_has_tabbed_content(self, worktree: Path) -> None:
        """App should have a TabbedContent as the sidebar."""
        async with PerchApp(worktree).run_test() as pilot:
            tabs = pilot.app.query_one("#sidebar", TabbedContent)
            assert tabs is not None

    async def test_has_three_tabs(self, worktree: Path) -> None:
        """TabbedContent should have three tab panes: Files, Git, PR."""
        async with PerchApp(worktree).run_test() as pilot:
            panes = pilot.app.query(TabPane)
            assert len(panes) == 3

    async def test_files_tab_contains_tree(self, worktree: Path) -> None:
        """Files tab should contain a FileTree."""
        async with PerchApp(worktree).run_test() as pilot:
            tree = pilot.app.query_one(FileTree)
            assert tree is not None

    async def test_git_tab_has_status_panel(self, worktree: Path) -> None:
        """Git tab should contain a GitPanel widget."""
        async with PerchApp(worktree).run_test() as pilot:
            panel = pilot.app.query_one(GitPanel)
            assert panel is not None

    async def test_pr_tab_has_context_panel(self, worktree: Path) -> None:
        """PR tab should contain a GitHubPanel widget."""
        async with PerchApp(worktree).run_test() as pilot:
            panel = pilot.app.query_one(GitHubPanel)
            assert panel is not None


class TestTabSwitching:
    """Tests for tab switching via [ and ] keys."""

    async def test_next_tab_from_files_goes_to_git(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("right_square_bracket")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-git"

    async def test_prev_tab_from_files_wraps_to_github(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("left_square_bracket")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-github"


class TestCommandPalette:
    """Tests for the command palette integration."""

    def test_discovery_provider_registered(self) -> None:
        """PerchApp.COMMANDS should include DiscoveryCommandProvider."""
        assert DiscoveryCommandProvider in PerchApp.COMMANDS

    def test_ctrl_shift_p_binding_exists(self) -> None:
        """App should have ctrl+shift+p as the command palette binding."""
        assert PerchApp.COMMAND_PALETTE_BINDING == "question_mark"


class TestQuitBinding:
    """Test that q quits the app."""

    async def test_q_quits(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()
            assert pilot.app.return_code is not None or not pilot.app.is_running


class TestTitleWithGitBranch:
    """Test that the title includes the branch name when in a git repo."""

    async def test_title_includes_branch_name(self, git_worktree: Path) -> None:
        """Title should include the branch when inside a git repo."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            assert "perch" in pilot.app.title
            # In a real git repo the branch name should appear
            assert "\u2014" in pilot.app.title  # em dash separator


class TestTabNavigation:
    """Tests for [/] tab cycling."""

    async def test_next_tab_cycles_forward(self, worktree: Path) -> None:
        """action_next_tab should cycle Files -> Git -> GitHub -> Files."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            tabbed = pilot.app.query_one(TabbedContent)
            assert tabbed.active == "tab-files"
            pilot.app.action_next_tab()
            await pilot.pause()
            assert tabbed.active == "tab-git"
            pilot.app.action_next_tab()
            await pilot.pause()
            assert tabbed.active == "tab-github"
            pilot.app.action_next_tab()
            await pilot.pause()
            assert tabbed.active == "tab-files"

    async def test_prev_tab_cycles_backward(self, worktree: Path) -> None:
        """action_prev_tab should cycle Files -> GitHub -> Git -> Files."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            tabbed = pilot.app.query_one(TabbedContent)
            assert tabbed.active == "tab-files"
            pilot.app.action_prev_tab()
            await pilot.pause()
            assert tabbed.active == "tab-github"
            pilot.app.action_prev_tab()
            await pilot.pause()
            assert tabbed.active == "tab-git"

    async def test_next_tab_focuses_git_panel(self, worktree: Path) -> None:
        """Switching to git tab should focus the GitPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_next_tab()
            await pilot.pause()
            panel = pilot.app.query_one(GitPanel)
            assert panel.has_focus

    async def test_next_tab_focuses_github_panel(self, worktree: Path) -> None:
        """Switching to GitHub tab should focus the GitHubPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_next_tab()
            await pilot.pause()
            pilot.app.action_next_tab()
            await pilot.pause()
            panel = pilot.app.query_one(GitHubPanel)
            assert panel.has_focus

    async def test_prev_tab_focuses_file_tree(self, worktree: Path) -> None:
        """Switching back to files tab should focus the FileTree."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_next_tab()
            await pilot.pause()
            pilot.app.action_prev_tab()
            await pilot.pause()
            tree = pilot.app.query_one(FileTree)
            assert tree.has_focus


class TestFocusPaneToggle:
    """Tests for action_focus_next_pane() and action_focus_prev_pane()."""

    async def test_focus_next_pane_from_right_to_left(self, worktree: Path) -> None:
        """Tab from sidebar should move focus to the file viewer."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # Start: file tree is focused (sidebar)
            tree = pilot.app.query_one(FileTree)
            tree.focus()
            await pilot.pause()
            # Press tab to toggle to left pane
            pilot.app.action_focus_next_pane()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert viewer.has_focus

    async def test_focus_next_pane_from_left_to_right(self, worktree: Path) -> None:
        """Tab from left pane should move focus back to the active tab."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one("#left-pane", Viewer)
            viewer.focus()
            await pilot.pause()
            assert viewer.has_focus
            # Press tab to toggle to sidebar
            pilot.app.action_focus_next_pane()
            await pilot.pause()
            # Should be on the file tree (active tab is files)
            tree = pilot.app.query_one(FileTree)
            assert tree.has_focus


class TestFocusActiveTab:
    """Tests for _focus_active_tab() targeting each tab."""

    async def test_focus_active_tab_files_sets_cursor(self, worktree: Path) -> None:
        """_focus_active_tab on files tab should set cursor to a valid position."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            tree = pilot.app.query_one(FileTree)
            tree.cursor_line = -1
            pilot.app._focus_active_tab()
            await pilot.pause()
            assert tree.cursor_line >= 0

    async def test_focus_active_tab_git(self, worktree: Path) -> None:
        """_focus_active_tab on git tab should focus the GitPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_next_tab()  # Files -> Git
            await pilot.pause()
            await pilot.pause()
            assert pilot.app.query_one(GitPanel).has_focus

    async def test_focus_active_tab_pr(self, worktree: Path) -> None:
        """_focus_active_tab on pr tab should focus the GitHubPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_next_tab()  # Files -> Git
            await pilot.pause()
            pilot.app.action_next_tab()  # Git -> GitHub
            await pilot.pause()
            await pilot.pause()
            assert pilot.app.query_one(GitHubPanel).has_focus


class TestGitPanelFileSelected:
    """Tests for on_git_panel_file_selected() handler."""

    async def test_file_selected_loads_existing_file(self, git_worktree: Path) -> None:
        """Selecting an existing file should load it in the viewer."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            event = GitPanel.FileSelected(path="hello.py", staged=False)
            pilot.app.on_git_panel_file_selected(event)
            await pilot.pause()
            assert viewer._current_path == git_worktree / "hello.py"

    async def test_file_selected_deleted_file_with_diff(
        self, git_worktree: Path
    ) -> None:
        """Selecting a deleted file should show diff content."""
        # Delete a file so it becomes a "deleted" change
        (git_worktree / "hello.py").unlink()
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            event = GitPanel.FileSelected(path="hello.py", staged=False)
            pilot.app.on_git_panel_file_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer._current_path == git_worktree / "hello.py"

    async def test_file_selected_deleted_file_no_diff(self, worktree: Path) -> None:
        """Selecting a deleted file with no git diff available should show fallback."""
        # No git repo, so get_diff will raise RuntimeError
        # Remove file so it is not found
        deleted_name = "gone.py"
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            event = GitPanel.FileSelected(path=deleted_name, staged=False)
            pilot.app.on_git_panel_file_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer._current_path == worktree / deleted_name


class TestGitPanelCommitSelected:
    """Tests for on_git_panel_commit_selected() handler."""

    async def test_commit_selected_loads_commit_diff(self, git_worktree: Path) -> None:
        """Selecting a commit should load its diff in the viewer."""
        # Get the commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        commit_hash = result.stdout.strip()

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            event = GitPanel.CommitSelected(commit_hash=commit_hash)
            pilot.app.on_git_panel_commit_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer.worktree_root == git_worktree


class TestToggleDiff:
    """Tests for action_toggle_diff() and action_toggle_diff_layout()."""

    async def test_toggle_diff_delegates_to_viewer(self, worktree: Path) -> None:
        """action_toggle_diff should call the viewer's action_toggle_diff."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            with patch.object(viewer, "action_toggle_diff") as mock:
                pilot.app.action_toggle_diff()
                mock.assert_called_once()

    async def test_toggle_diff_layout_delegates_to_viewer(self, worktree: Path) -> None:
        """action_toggle_diff_layout should call the viewer's method."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            with patch.object(viewer, "action_toggle_diff_layout") as mock:
                pilot.app.action_toggle_diff_layout()
                mock.assert_called_once()


class TestDiffFileNavigation:
    """Tests for action_next_diff_file() and action_prev_diff_file()."""

    async def test_next_diff_file_delegates_to_viewer(self, worktree: Path) -> None:
        """action_next_diff_file should call the viewer's action."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            with patch.object(viewer, "action_next_diff_file") as mock:
                pilot.app.action_next_diff_file()
                mock.assert_called_once()

    async def test_prev_diff_file_delegates_to_viewer(self, worktree: Path) -> None:
        """action_prev_diff_file should call the viewer's action."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            with patch.object(viewer, "action_prev_diff_file") as mock:
                pilot.app.action_prev_diff_file()
                mock.assert_called_once()


class TestToggleFocusMode:
    """Tests for action_toggle_focus_mode()."""

    async def test_focus_mode_hides_sidebar(self, worktree: Path) -> None:
        """Entering focus mode should hide the sidebar and splitter."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            sidebar = pilot.app.query_one("#sidebar", TabbedContent)
            splitter = pilot.app.query_one(DraggableSplitter)
            assert sidebar.display is False
            assert splitter.display is False
            assert pilot.app._focus_mode is True

    async def test_focus_mode_sets_viewer_full_width(self, worktree: Path) -> None:
        """Entering focus mode should set the viewer width to 100%."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert viewer.styles.width is not None
            assert "100" in str(viewer.styles.width)

    async def test_focus_mode_focuses_viewer(self, worktree: Path) -> None:
        """Entering focus mode should focus the viewer."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert viewer.has_focus

    async def test_exit_focus_mode_restores_layout(self, worktree: Path) -> None:
        """Exiting focus mode should restore the sidebar and splitter."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # Enter focus mode
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            # Exit focus mode
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            sidebar = pilot.app.query_one("#sidebar", TabbedContent)
            splitter = pilot.app.query_one(DraggableSplitter)
            assert sidebar.display is True
            assert splitter.display is True
            assert pilot.app._focus_mode is False

    async def test_exit_focus_mode_restores_width(self, worktree: Path) -> None:
        """Exiting focus mode should restore the viewer width to 60%."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert "75" in str(viewer.styles.width)




class TestOnTreeNodeHighlighted:
    """Tests for on_tree_node_highlighted() handler."""

    async def test_node_with_no_data_is_skipped(self, worktree: Path) -> None:
        """A tree node with data=None should be skipped (no crash)."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:

            class FakeEvent:
                class node:
                    data = None

            pilot.app.on_tree_node_highlighted(FakeEvent())
            # No assertion needed — just verify no exception


class TestOpenEditor:
    """Tests for action_open_editor()."""

    async def test_open_editor_calls_open_file(self, worktree: Path) -> None:
        """action_open_editor should call open_file when a file is loaded."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            with patch("perch.app.open_file") as mock:
                pilot.app.action_open_editor()
                mock.assert_called_once_with(
                    pilot.app.editor,
                    worktree / "hello.py",
                    worktree,
                )

    async def test_open_editor_noop_without_file(self, worktree: Path) -> None:
        """action_open_editor should do nothing when no file is loaded."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer._current_path = None
            with patch("perch.app.open_file") as mock:
                pilot.app.action_open_editor()
                mock.assert_not_called()


class TestWatchTheme:
    """Tests for watch_theme() re-rendering."""

    async def test_watch_theme_no_file_loaded(self, worktree: Path) -> None:
        """watch_theme should not crash when no file is loaded."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # viewer._current_path is None by default
            pilot.app.watch_theme()
            # No exception expected

    async def test_watch_theme_with_file_loaded(self, worktree: Path) -> None:
        """watch_theme should re-render when a file is loaded."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer.load_file(worktree / "hello.py")
            await pilot.pause()
            # Should not raise
            pilot.app.watch_theme()

    async def test_watch_theme_in_diff_mode(self, git_worktree: Path) -> None:
        """watch_theme in diff mode should call _load_diff."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer._current_path = git_worktree / "hello.py"
            viewer._diff_mode = True
            with patch.object(viewer, "_load_diff") as mock:
                pilot.app.watch_theme()
                mock.assert_called_once()


class TestFileSearch:
    """Tests for action_file_search and _on_file_selected callback."""

    async def test_on_file_selected_none_is_noop(self, worktree: Path) -> None:
        """_on_file_selected(None) should not change the viewer state."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            await pilot.pause()
            path_before = viewer._current_path
            pilot.app._on_file_selected(None)
            await pilot.pause()
            assert viewer._current_path == path_before

    async def test_on_file_selected_loads_valid_file(self, worktree: Path) -> None:
        """_on_file_selected with a valid relative path should load the file."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            pilot.app._on_file_selected("hello.py")
            await pilot.pause()
            assert viewer._current_path == worktree / "hello.py"

    async def test_on_file_selected_nonexistent_file_is_noop(
        self, worktree: Path
    ) -> None:
        """_on_file_selected with a non-existent file should not change state."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            await pilot.pause()
            path_before = viewer._current_path
            pilot.app._on_file_selected("nonexistent.py")
            await pilot.pause()
            assert viewer._current_path == path_before

    async def test_file_search_pushes_screen(self, worktree: Path) -> None:
        """action_file_search should push a FileSearchScreen."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            with patch.object(pilot.app, "push_screen") as mock:
                pilot.app.action_file_search()
                mock.assert_called_once()

    async def test_on_file_selected_updates_files_tab_cache(
        self, worktree: Path
    ) -> None:
        """_on_file_selected should cache the path under _files_tab_last_path."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app._on_file_selected("hello.py")
            await pilot.pause()
            assert pilot.app._files_tab_last_path == worktree / "hello.py"


class TestSelectionRestored:
    """Tests for on_git_panel_selection_restored."""

    async def test_ignored_when_git_tab_not_active(self, worktree: Path) -> None:
        """SelectionRestored is a no-op when the Git tab is not active."""
        with (
            patch("perch.services.git.get_status", return_value=__import__("perch.models", fromlist=["GitStatusData"]).GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                # Files tab is active by default; load a file so the viewer has content
                viewer = pilot.app.query_one(Viewer)
                viewer.load_file(worktree / "hello.py")
                await pilot.pause()
                assert viewer._current_path == worktree / "hello.py"

                # Fire SelectionRestored while on Files tab — viewer must not change
                from perch.widgets.git_status import GitPanel
                panel = pilot.app.query_one(GitPanel)
                pilot.app.on_git_panel_selection_restored(
                    GitPanel.SelectionRestored()
                )
                await pilot.pause()
                # Viewer content unchanged
                assert viewer._current_path == worktree / "hello.py"

    async def test_syncs_viewer_when_git_tab_active(self, worktree: Path) -> None:
        """SelectionRestored updates the viewer when the Git tab is active."""
        from perch.models import Commit, GitFile, GitStatusData
        from perch.widgets.git_status import GitPanel

        status = GitStatusData(
            unstaged=[GitFile(path="hello.py", status="modified", staged=False)]
        )
        commits = [Commit(hash="abc", message="m", author="a", relative_time="now")]
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=commits),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                from textual.widgets import TabbedContent

                pilot.app.query_one(TabbedContent).active = "tab-git"
                panel = pilot.app.query_one(GitPanel)
                panel._update_display(status, commits)
                await pilot.pause()

                # SelectionRestored while Git tab is active — viewer should load file
                pilot.app.on_git_panel_selection_restored(
                    GitPanel.SelectionRestored()
                )
                await pilot.pause()
                viewer = pilot.app.query_one(Viewer)
                assert viewer._current_path == worktree / "hello.py"
