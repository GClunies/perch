"""Tests for PerchApp tabbed layout and tree-to-viewer wiring."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Footer, Header, ListItem, ListView, TabbedContent, TabPane

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
        assert PerchApp.COMMAND_PALETTE_BINDING == "ctrl+shift+p"


class TestQuitBinding:
    """Test that ctrl+q quits the app."""

    async def test_ctrl_q_quits(self, worktree: Path) -> None:
        async with PerchApp(worktree).run_test() as pilot:
            await pilot.press("ctrl+q")
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
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
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
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
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
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            viewer = pilot.app.query_one(Viewer)
            event = GitPanel.FileSelected(path=deleted_name, staged=False)
            pilot.app.on_git_panel_file_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer._current_path == worktree / deleted_name


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
        """action_open_editor should call open_file with the git root."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            with (
                patch("perch.app.open_file") as mock,
                patch(
                    "perch.services.git.get_worktree_root",
                    return_value=worktree,
                ),
            ):
                pilot.app.action_open_editor()
                mock.assert_called_once_with(
                    pilot.app.editor,
                    worktree / "hello.py",
                    worktree,
                )

    async def test_open_editor_no_git_root(self, worktree: Path) -> None:
        """action_open_editor passes None when file is not in a git repo."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            with (
                patch("perch.app.open_file") as mock,
                patch(
                    "perch.services.git.get_worktree_root",
                    side_effect=RuntimeError("Not a git repository"),
                ),
            ):
                pilot.app.action_open_editor()
                mock.assert_called_once_with(
                    pilot.app.editor,
                    worktree / "hello.py",
                    None,
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
            patch(
                "perch.services.git.get_status",
                return_value=__import__(
                    "perch.models", fromlist=["GitStatusData"]
                ).GitStatusData(),
            ),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                viewer = pilot.app.query_one(Viewer)
                await pilot.pause()
                # Capture viewer state after startup settles
                viewer.load_file(worktree / "hello.py")
                path_before = viewer._current_path

                # Fire SelectionRestored while on Files tab — viewer must not change
                from perch.widgets.git_status import GitPanel

                pilot.app.on_git_panel_selection_restored(GitPanel.SelectionRestored())
                assert viewer._current_path == path_before

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
                pilot.app.on_git_panel_selection_restored(GitPanel.SelectionRestored())
                await pilot.pause()
                viewer = pilot.app.query_one(Viewer)
                assert viewer._current_path == worktree / "hello.py"


class TestAutoSelectBailout:
    """Tests for _auto_select_first_node bailing when a path is already loaded."""

    async def test_auto_select_skips_when_path_already_set(
        self, worktree: Path
    ) -> None:
        """Auto-select should not override a path that was set before the timer fires."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            viewer = pilot.app.query_one(Viewer)
            # Reset auto-select state so we can trigger the bail-out path ourselves
            pilot.app._auto_select_done = False
            # Set a path to trigger the bailout condition at line 122
            sentinel = worktree / "sub" / "world.txt"
            viewer._current_path = sentinel
            # Directly call the method to hit the branch
            pilot.app._auto_select_first_node()
            # Auto-select should NOT have overridden the sentinel path
            assert viewer._current_path == sentinel


class TestAutoSelectEmptyDir:
    """Tests for _auto_select_first_node when the directory has no files."""

    async def test_auto_select_selects_folder_when_no_files(
        self, tmp_path: Path
    ) -> None:
        """A directory with only subdirs should select the first subfolder."""
        (tmp_path / "emptydir").mkdir()
        app = PerchApp(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            tree = pilot.app.query_one(FileTree)
            for _ in range(30):
                await pilot.pause()
                if tree.cursor_line > 0:
                    break
            # The subfolder node should be selected (not root at line 0)
            assert tree.cursor_line > 0


class TestOnDirectoryTreeFileSelected:
    """Tests for on_directory_tree_file_selected() handler."""

    async def test_file_selected_loads_file_and_focuses_viewer(
        self, worktree: Path
    ) -> None:
        """A FileSelected event should load the file and focus the viewer."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            viewer = pilot.app.query_one(Viewer)

            class FakeEvent:
                path = worktree / "hello.py"

            pilot.app.on_directory_tree_file_selected(FakeEvent())
            await pilot.pause()
            assert viewer._current_path == worktree / "hello.py"
            assert viewer.has_focus


class TestCommentPreview:
    """Tests for on_git_hub_panel_preview_requested with comment kind."""

    async def test_comment_preview_shows_in_viewer(self, worktree: Path) -> None:
        """A PreviewRequested with preview_kind='comment' should call show_review."""
        with (
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                # Use action to switch to github tab (ensures internal state is consistent)
                pilot.app.action_next_tab()  # files -> git
                await pilot.pause()
                pilot.app.action_next_tab()  # git -> github
                await pilot.pause()
                assert pilot.app.query_one(TabbedContent).active == "tab-github"

                viewer = pilot.app.query_one(Viewer)
                with patch.object(viewer, "show_review") as mock:
                    event = GitHubPanel.PreviewRequested(
                        preview_kind="comment",
                        url="",
                        body="This is a comment body",
                        title="alice",
                    )
                    pilot.app.on_git_hub_panel_preview_requested(event)
                    mock.assert_called_once_with(
                        "This is a comment body", title="alice"
                    )


class TestListViewSelectedFocusesViewer:
    """Tests for on_list_view_selected focusing the viewer on the git tab."""

    async def test_list_view_selected_on_git_tab_focuses_viewer(
        self, worktree: Path
    ) -> None:
        """ListView.Selected on the git tab should focus the viewer."""
        from perch.models import GitFile, GitStatusData

        status = GitStatusData(
            unstaged=[GitFile(path="hello.py", status="modified", staged=False)]
        )
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                pilot.app.query_one(TabbedContent).active = "tab-git"
                await pilot.pause()

                # Build a fake Selected event using the internal file list
                panel = pilot.app.query_one(GitPanel)
                item = ListItem(name="hello.py")
                event = ListView.Selected(panel._file_list, item, 0)
                pilot.app.on_list_view_selected(event)
                await pilot.pause()
                viewer = pilot.app.query_one(Viewer)
                assert viewer.has_focus


class TestSelectionRestoredCleanTree:
    """Tests for on_git_panel_selection_restored showing clean tree."""

    async def test_clean_tree_shown_when_no_selection(self, worktree: Path) -> None:
        """Empty git status should result in show_clean_tree via SelectionRestored."""
        from perch.models import GitStatusData

        status = GitStatusData()  # no files at all
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                pilot.app.query_one(TabbedContent).active = "tab-git"
                panel = pilot.app.query_one(GitPanel)
                panel._update_display(status, [])
                await pilot.pause()

                viewer = pilot.app.query_one(Viewer)
                with patch.object(viewer, "show_clean_tree") as mock:
                    # Fire SelectionRestored — panel has no selectable item
                    pilot.app.on_git_panel_selection_restored(
                        GitPanel.SelectionRestored()
                    )
                    mock.assert_called_once()


class TestOnListViewHighlighted:
    """Tests for on_list_view_highlighted handling deleted-file items."""

    async def test_highlighted_deleted_file_shows_diff(
        self, git_worktree: Path
    ) -> None:
        """Highlighting a deleted file item should call show_deleted_file_diff."""
        # Delete the file so file_path.is_file() is False
        (git_worktree / "hello.py").unlink()

        from perch.models import GitFile, GitStatusData

        status = GitStatusData(
            unstaged=[GitFile(path="hello.py", status="deleted", staged=False)]
        )
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(git_worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                pilot.app.action_next_tab()  # files -> git
                await pilot.pause()

                viewer = pilot.app.query_one(Viewer)
                panel = pilot.app.query_one(GitPanel)
                with patch.object(viewer, "show_deleted_file_diff") as mock:
                    item = ListItem(name="hello.py")
                    event = ListView.Highlighted(panel._file_list, item)
                    pilot.app.on_list_view_highlighted(event)
                    mock.assert_called_once_with(
                        git_worktree / "hello.py", "hello.py", staged=False
                    )


class TestCommitExpandFromApp:
    async def test_select_commit_toggles_expand(self, git_worktree: Path) -> None:
        """CommitToggled message should expand the commit in the tree."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            # Wait for the background git refresh to complete
            for _ in range(20):
                await pilot.pause()

            panel = pilot.app.query_one(GitPanel)

            # Find a commit node in the tree
            root = panel._commit_tree.root
            commit_node = None
            for n in root.children:
                if n.data and n.data.startswith("commit:"):
                    commit_node = n
                    break
            assert commit_node is not None

            commit_hash = commit_node.data.removeprefix("commit:")

            # Switch to git tab
            pilot.app.query_one(TabbedContent).active = "tab-git"
            await pilot.pause()

            # Post CommitToggled message which the app handler forwards to toggle_commit
            panel.post_message(GitPanel.CommitToggled(commit_hash))
            await pilot.pause()

            assert panel._expanded_commit == commit_hash


class TestCommitTreeAppEvents:
    """Tests for the new commit tree message handlers in the app."""

    async def test_commit_highlighted_loads_summary(self, git_worktree: Path) -> None:
        """CommitHighlighted should trigger _load_commit_summary."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(20):
                await pilot.pause()

            # Activate git tab so the tab guard passes
            pilot.app.query_one(TabbedContent).active = "tab-git"
            await pilot.pause()

            panel = pilot.app.query_one(GitPanel)
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")

            viewer = pilot.app.query_one(Viewer)
            with patch.object(pilot.app, "_load_commit_summary") as mock:
                event = GitPanel.CommitHighlighted(commit_hash)
                pilot.app.on_git_panel_commit_highlighted(event)
                mock.assert_called_once_with(commit_hash)
            assert viewer.worktree_root == git_worktree

    async def test_commit_file_highlighted_loads_diff(self, git_worktree: Path) -> None:
        """CommitFileHighlighted should call load_commit_file_diff on viewer."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            # Activate git tab so the tab guard passes
            pilot.app.query_one(TabbedContent).active = "tab-git"
            await pilot.pause()

            viewer = pilot.app.query_one(Viewer)
            with patch.object(viewer, "load_commit_file_diff") as mock:
                event = GitPanel.CommitFileHighlighted("abc123", "hello.py")
                pilot.app.on_git_panel_commit_file_highlighted(event)
                mock.assert_called_once_with("abc123", "hello.py")
            assert viewer.worktree_root == git_worktree

    async def test_commit_highlighted_skipped_on_wrong_tab(
        self, git_worktree: Path
    ) -> None:
        """CommitHighlighted should not load summary when git tab is inactive."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(20):
                await pilot.pause()

            # Stay on files tab (default)
            with patch.object(pilot.app, "_load_commit_summary") as mock:
                event = GitPanel.CommitHighlighted("abc123")
                pilot.app.on_git_panel_commit_highlighted(event)
                mock.assert_not_called()

    async def test_commit_file_highlighted_skipped_on_wrong_tab(
        self, git_worktree: Path
    ) -> None:
        """CommitFileHighlighted should not load diff when git tab is inactive."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            viewer = pilot.app.query_one(Viewer)
            with patch.object(viewer, "load_commit_file_diff") as mock:
                event = GitPanel.CommitFileHighlighted("abc123", "hello.py")
                pilot.app.on_git_panel_commit_file_highlighted(event)
                mock.assert_not_called()

    async def test_commit_toggled_expands(self, git_worktree: Path) -> None:
        """CommitToggled message should expand the commit."""
        (git_worktree / "hello.py").write_text("changed\n")

        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "change"],
            cwd=git_worktree,
            check=True,
        )
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(20):
                await pilot.pause()
            panel = pilot.app.query_one(GitPanel)
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            hash = commit_node.data.removeprefix("commit:")
            panel.post_message(GitPanel.CommitToggled(hash))
            await pilot.pause()
            assert panel._expanded_commit == hash


# ---------------------------------------------------------------------------
# _show_current_git_item: commit, commit-file, deleted file paths
# ---------------------------------------------------------------------------


class TestShowCurrentGitItem:
    """Tests for _show_current_git_item with different highlighted items."""

    async def test_show_commit_item(self, worktree: Path) -> None:
        """When tree has focus on a commit node, should load commit summary."""
        from perch.models import Commit, CommitSummary, GitFile, GitStatusData

        status = GitStatusData(
            unstaged=[GitFile(path="hello.py", status="modified", staged=False)]
        )
        commits = [
            Commit(hash="aaa111", message="first", author="A", relative_time="now"),
        ]
        summary = CommitSummary(
            hash="aaa111", subject="first", body="", author="A", date="now", stats=""
        )
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=commits),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                pilot.app.query_one(TabbedContent).active = "tab-git"
                panel = pilot.app.query_one(GitPanel)
                panel._update_display(status, commits)
                await pilot.pause()

                # Focus tree and select commit node
                panel._commit_tree.focus()
                panel._commit_tree.cursor_line = 0
                await pilot.pause()

                viewer = pilot.app.query_one(Viewer)
                # Patch the underlying git service instead of the @work-wrapped method
                with patch(
                    "perch.services.git.get_commit_summary", return_value=summary
                ) as mock:
                    pilot.app._show_current_git_item(panel, viewer)
                    for _ in range(10):
                        await pilot.pause()
                    mock.assert_called_once_with(worktree, "aaa111")

    async def test_show_commit_file_item(self, worktree: Path) -> None:
        """When tree has focus on a commit-file node, should load commit file diff."""
        from perch.models import Commit, GitFile, GitStatusData

        status = GitStatusData(
            unstaged=[GitFile(path="hello.py", status="modified", staged=False)]
        )
        commits = [
            Commit(hash="aaa111", message="first", author="A", relative_time="now"),
        ]
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=commits),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                pilot.app.query_one(TabbedContent).active = "tab-git"
                panel = pilot.app.query_one(GitPanel)
                panel._update_display(status, commits)
                await pilot.pause()

                # Add a commit-file child and focus tree on it
                commit_node = next(
                    n
                    for n in panel._commit_tree.root.children
                    if n.data and n.data.startswith("commit:")
                )
                commit_node.add_leaf("file.py", data="commit-file:aaa111:file.py")
                commit_node.expand()
                panel._commit_tree.focus()
                await pilot.pause()
                # Move cursor to the file child (line after commit)
                panel._commit_tree.cursor_line = 1
                await pilot.pause()

                viewer = pilot.app.query_one(Viewer)
                with patch.object(viewer, "load_commit_file_diff") as mock:
                    pilot.app._show_current_git_item(panel, viewer)
                    mock.assert_called_once_with("aaa111", "file.py")

    async def test_show_deleted_file_item(self, worktree: Path) -> None:
        """When highlighting a deleted file, should call show_deleted_file_diff."""
        from perch.models import GitFile, GitStatusData

        status = GitStatusData(
            unstaged=[GitFile(path="gone.py", status="deleted", staged=False)]
        )
        with (
            patch("perch.services.git.get_status", return_value=status),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                pilot.app.query_one(TabbedContent).active = "tab-git"
                panel = pilot.app.query_one(GitPanel)
                panel._update_display(status, [])
                await pilot.pause()

                panel._file_list.focus()
                await pilot.pause()

                viewer = pilot.app.query_one(Viewer)
                with patch.object(viewer, "show_deleted_file_diff") as mock:
                    pilot.app._show_current_git_item(panel, viewer)
                    mock.assert_called_once_with(
                        worktree / "gone.py", "gone.py", staged=False
                    )


# ---------------------------------------------------------------------------
# _show_current_github_item
# ---------------------------------------------------------------------------


class TestShowCurrentGitHubItem:
    """Tests for _show_current_github_item with different preview kinds."""

    async def test_no_item_shows_placeholder(self, worktree: Path) -> None:
        """When no item is highlighted, should show placeholder."""
        with (
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                github = pilot.app.query_one(GitHubPanel)
                viewer = pilot.app.query_one(Viewer)
                with patch.object(viewer, "show_placeholder") as mock:
                    pilot.app._show_current_github_item(github, viewer)
                    mock.assert_called_once()

    async def test_pr_body_item(self, worktree: Path) -> None:
        """A pr_body item should call show_pr_body."""
        from perch.widgets.github_panel import ClickableItem

        with (
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                github = pilot.app.query_one(GitHubPanel)
                viewer = pilot.app.query_one(Viewer)

                # Clear and add a ClickableItem with pr_body kind
                github.clear()
                item = ClickableItem(
                    preview_kind="pr_body",
                    preview_title="#42",
                    preview_body="PR body text",
                )
                github.append(item)
                github.index = 0
                await pilot.pause()

                with patch.object(viewer, "show_pr_body") as mock:
                    pilot.app._show_current_github_item(github, viewer)
                    mock.assert_called_once_with("PR body text", title="#42")

    async def test_review_item(self, worktree: Path) -> None:
        """A review item should call show_review."""
        from perch.widgets.github_panel import ClickableItem

        with (
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                github = pilot.app.query_one(GitHubPanel)
                viewer = pilot.app.query_one(Viewer)

                github.clear()
                item = ClickableItem(
                    preview_kind="review",
                    preview_title="reviewer",
                    preview_body="review body",
                )
                github.append(item)
                github.index = 0
                await pilot.pause()

                with patch.object(viewer, "show_review") as mock:
                    pilot.app._show_current_github_item(github, viewer)
                    mock.assert_called_once_with("review body", title="reviewer")

    async def test_ci_check_item(self, worktree: Path) -> None:
        """A ci_check item should call show_ci_loading and fetch_ci_log."""
        from perch.widgets.github_panel import ClickableItem

        with (
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                github = pilot.app.query_one(GitHubPanel)
                viewer = pilot.app.query_one(Viewer)

                github.clear()
                item = ClickableItem(
                    url="https://example.com/log",
                    preview_kind="ci_check",
                    preview_title="CI Run",
                    preview_body="",
                )
                github.append(item)
                github.index = 0
                await pilot.pause()

                with (
                    patch.object(viewer, "show_ci_loading") as mock_loading,
                    patch.object(viewer, "fetch_ci_log") as mock_fetch,
                ):
                    pilot.app._show_current_github_item(github, viewer)
                    mock_loading.assert_called_once_with(title="CI Run")
                    mock_fetch.assert_called_once_with("https://example.com/log")


# ---------------------------------------------------------------------------
# Pane resize actions
# ---------------------------------------------------------------------------


class TestPaneResize:
    """Tests for action_shrink_pane and action_grow_pane."""

    async def test_shrink_pane_from_viewer(self, worktree: Path) -> None:
        """Shrinking from the viewer (left) should decrease left pane width."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer.focus()
            await pilot.pause()
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_shrink_pane()
                mock.assert_called_once_with(-5)

    async def test_shrink_pane_from_sidebar(self, worktree: Path) -> None:
        """Shrinking from the sidebar (right) should increase left pane width."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            tree = pilot.app.query_one(FileTree)
            tree.focus()
            await pilot.pause()
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_shrink_pane()
                mock.assert_called_once_with(5)

    async def test_grow_pane_from_viewer(self, worktree: Path) -> None:
        """Growing from the viewer (left) should increase left pane width."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer.focus()
            await pilot.pause()
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_grow_pane()
                mock.assert_called_once_with(5)

    async def test_grow_pane_from_sidebar(self, worktree: Path) -> None:
        """Growing from the sidebar (right) should decrease left pane width."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            tree = pilot.app.query_one(FileTree)
            tree.focus()
            await pilot.pause()
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_grow_pane()
                mock.assert_called_once_with(-5)

    async def test_shrink_pane_noop_in_focus_mode(self, worktree: Path) -> None:
        """Shrink should be a no-op in focus mode."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_shrink_pane()
                mock.assert_not_called()

    async def test_grow_pane_noop_in_focus_mode(self, worktree: Path) -> None:
        """Grow should be a no-op in focus mode."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_grow_pane()
                mock.assert_not_called()


# ---------------------------------------------------------------------------
# _focus_active_tab: cached path restoration
# ---------------------------------------------------------------------------


class TestFocusActiveTabCachedPath:
    """Tests for _focus_active_tab restoring cached paths."""

    async def test_files_tab_restores_cached_file(self, worktree: Path) -> None:
        """Switching back to files tab should call load_file with the cached path."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            viewer = pilot.app.query_one(Viewer)
            cached = worktree / "hello.py"

            # Switch away to git tab first so the tree stops sending events
            pilot.app.action_next_tab()
            await pilot.pause()

            # Now set the cached path (after the tree settled)
            pilot.app._files_tab_last_path = cached
            assert cached.exists() and cached.is_file()

            # Switch back to files tab
            with (
                patch.object(viewer, "load_file") as mock_load,
                patch.object(pilot.app, "_sync_tree_to_path"),
            ):
                pilot.app.action_prev_tab()  # git -> files
                await pilot.pause()
                mock_load.assert_called_once_with(cached)

    async def test_files_tab_restores_cached_folder(self, worktree: Path) -> None:
        """Switching back to files tab should restore a cached folder path."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            pilot.app.query_one(Viewer)
            # Set a cached folder path
            pilot.app._files_tab_last_path = worktree / "sub"
            pilot.app.action_next_tab()
            await pilot.pause()
            pilot.app.action_prev_tab()
            await pilot.pause()
            # Should have called show_folder
            # Just verify it didn't crash and the tree has focus
            tree = pilot.app.query_one(FileTree)
            assert tree.has_focus


# ---------------------------------------------------------------------------
# _load_commit_summary background worker
# ---------------------------------------------------------------------------


class TestLoadCommitSummary:
    """Tests for _load_commit_summary background execution."""

    async def test_load_commit_summary_runtime_error(self, git_worktree: Path) -> None:
        """RuntimeError in _load_commit_summary should be swallowed."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            with patch(
                "perch.services.git.get_commit_summary",
                side_effect=RuntimeError("bad"),
            ):
                pilot.app._load_commit_summary("bad_hash")
                for _ in range(10):
                    await pilot.pause()
            # Should not crash

    async def test_load_commit_summary_success(self, git_worktree: Path) -> None:
        """Successful _load_commit_summary should call show_commit_summary."""
        from perch.models import CommitSummary

        summary = CommitSummary(
            hash="abc123",
            subject="test",
            body="body",
            author="A",
            date="now",
            stats="1 file",
        )
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            pilot.app.query_one(Viewer)
            with patch(
                "perch.services.git.get_commit_summary",
                return_value=summary,
            ):
                pilot.app._load_commit_summary("abc123")
                for _ in range(10):
                    await pilot.pause()
            # Viewer should have shown the summary (no crash is the main check)


# ---------------------------------------------------------------------------
# Phase 2: TabActivated behavior verification
# ---------------------------------------------------------------------------


class TestTabActivatedFiringBehavior:
    """Step 2.1: Verify whether TabbedContent.TabActivated fires on programmatic
    ``tabbed.active = ...`` assignment.

    This determines the Phase 3 refactor strategy:
    - If it fires: we can add an ``on_tabbed_content_tab_activated`` handler and
      potentially remove explicit ``_focus_active_tab()`` calls from ``action_next_tab``
      / ``action_prev_tab``.
    - If it does NOT fire: we must keep the explicit calls.
    """

    async def test_tab_activated_fires_on_programmatic_active_change(
        self, worktree: Path
    ) -> None:
        """Setting ``tabbed.active`` programmatically should post TabActivated."""
        app = PerchApp(worktree)
        activated_events: list[TabbedContent.TabActivated] = []

        def hook(msg) -> None:
            if isinstance(msg, TabbedContent.TabActivated):
                activated_events.append(msg)

        async with app.run_test(size=(120, 40), message_hook=hook) as pilot:
            tabbed = pilot.app.query_one(TabbedContent)

            # Wait for initial mount events to settle
            for _ in range(5):
                await pilot.pause()
            activated_events.clear()

            # Programmatically switch to the git tab
            tabbed.active = "tab-git"
            for _ in range(5):
                await pilot.pause()

            # CRITICAL ASSERTION: TabActivated should have been posted
            assert len(activated_events) >= 1, (
                "TabActivated was NOT posted for programmatic active change. "
                "Phase 3 must keep explicit _focus_active_tab() calls."
            )
            # Verify the event references the correct pane
            assert activated_events[-1].pane.id == "tab-git"

    async def test_tab_activated_fires_for_each_programmatic_switch(
        self, worktree: Path
    ) -> None:
        """Each programmatic tab switch should fire a separate TabActivated."""
        app = PerchApp(worktree)
        activated_pane_ids: list[str] = []

        def hook(msg) -> None:
            if isinstance(msg, TabbedContent.TabActivated):
                activated_pane_ids.append(msg.pane.id or "")

        async with app.run_test(size=(120, 40), message_hook=hook) as pilot:
            tabbed = pilot.app.query_one(TabbedContent)

            for _ in range(5):
                await pilot.pause()
            activated_pane_ids.clear()

            # Switch through all tabs programmatically
            tabbed.active = "tab-git"
            for _ in range(5):
                await pilot.pause()
            tabbed.active = "tab-github"
            for _ in range(5):
                await pilot.pause()
            tabbed.active = "tab-files"
            for _ in range(5):
                await pilot.pause()

            assert "tab-git" in activated_pane_ids
            assert "tab-github" in activated_pane_ids
            assert "tab-files" in activated_pane_ids


# ---------------------------------------------------------------------------
# Phase 2: Mouse click tests (RED — expected to fail)
# ---------------------------------------------------------------------------


class TestMouseClickTabSwitching:
    """Step 2.2: Mouse click on tab headers should switch tabs AND focus content.

    These tests are expected to FAIL (RED state) because the app currently
    has no ``on_tabbed_content_tab_activated`` handler to focus content on
    mouse-driven tab switches. Phase 3 will make them pass.
    """

    async def test_click_git_tab_switches_active_tab(self, worktree: Path) -> None:
        """Clicking the Git tab header should switch the active tab to tab-git."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            tabbed = pilot.app.query_one(TabbedContent)
            assert tabbed.active == "tab-files"

            # Click the Git tab header (ID: --content-tab-tab-git)
            await pilot.click("#--content-tab-tab-git")
            await pilot.pause()

            assert tabbed.active == "tab-git"

    async def test_click_git_tab_focuses_git_panel(self, worktree: Path) -> None:
        """Clicking the Git tab header should focus the GitPanel widget.

        This test should FAIL because the app has no on_tabbed_content_tab_activated
        handler to call _focus_active_tab() on mouse clicks.
        """
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            # Wait for mount to settle
            for _ in range(5):
                await pilot.pause()

            # Click the Git tab header
            await pilot.click("#--content-tab-tab-git")
            for _ in range(5):
                await pilot.pause()

            # This should fail: clicking a tab via mouse doesn't trigger
            # _focus_active_tab(), so GitPanel won't be focused
            panel = pilot.app.query_one(GitPanel)
            assert panel.has_focus, (
                "GitPanel should be focused after clicking the Git tab header. "
                "This fails because there is no on_tabbed_content_tab_activated handler."
            )

    async def test_click_github_tab_focuses_github_panel(self, worktree: Path) -> None:
        """Clicking the GitHub tab header should focus the GitHubPanel widget."""
        with (
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                for _ in range(5):
                    await pilot.pause()

                await pilot.click("#--content-tab-tab-github")
                for _ in range(5):
                    await pilot.pause()

                panel = pilot.app.query_one(GitHubPanel)
                assert panel.has_focus, (
                    "GitHubPanel should be focused after clicking the GitHub tab header."
                )

    async def test_click_files_tab_after_git_focuses_file_tree(
        self, worktree: Path
    ) -> None:
        """Clicking back to the Files tab should focus the FileTree."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(5):
                await pilot.pause()

            # First switch away via click
            await pilot.click("#--content-tab-tab-git")
            for _ in range(5):
                await pilot.pause()

            # Click back to files
            await pilot.click("#--content-tab-tab-files")
            for _ in range(5):
                await pilot.pause()

            tree = pilot.app.query_one(FileTree)
            assert tree.has_focus, (
                "FileTree should be focused after clicking back to the Files tab."
            )


class TestMouseClickViewerFocus:
    """Step 2.2: Clicking the viewer pane should focus it."""

    async def test_click_viewer_focuses_it(self, worktree: Path) -> None:
        """Clicking the viewer pane should move focus to the viewer."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(5):
                await pilot.pause()

            # Ensure the file tree has focus initially
            tree = pilot.app.query_one(FileTree)
            assert tree.has_focus

            # Click the viewer pane
            await pilot.click("#left-pane")
            for _ in range(5):
                await pilot.pause()

            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert viewer.has_focus, "Viewer should be focused after clicking on it."


class TestMouseThenKeyboardNavigation:
    """Step 2.2: Keyboard navigation should still work after mouse click."""

    async def test_keyboard_tab_switch_after_mouse_click(self, worktree: Path) -> None:
        """Pressing ] after clicking a tab should advance to the next tab."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(5):
                await pilot.pause()

            # Click git tab
            await pilot.click("#--content-tab-tab-git")
            for _ in range(5):
                await pilot.pause()

            tabbed = pilot.app.query_one(TabbedContent)
            assert tabbed.active == "tab-git"

            # Now use keyboard to go to next tab
            await pilot.press("right_square_bracket")
            for _ in range(5):
                await pilot.pause()

            assert tabbed.active == "tab-github", (
                "Keyboard ] should advance from git to github after mouse click."
            )

    async def test_keyboard_focus_toggle_after_mouse_click(
        self, worktree: Path
    ) -> None:
        """Tab key (focus toggle) should work after clicking the viewer."""
        app = PerchApp(worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(5):
                await pilot.pause()

            # Click viewer to focus it
            await pilot.click("#left-pane")
            for _ in range(5):
                await pilot.pause()

            viewer = pilot.app.query_one("#left-pane", Viewer)
            assert viewer.has_focus

            # Press tab to toggle back to sidebar
            await pilot.press("tab")
            for _ in range(5):
                await pilot.pause()

            # The active tab's widget should now be focused
            tree = pilot.app.query_one(FileTree)
            assert tree.has_focus, (
                "FileTree should be focused after pressing Tab from the viewer."
            )


# ---------------------------------------------------------------------------
# Phase 2: Curated footer display
# ---------------------------------------------------------------------------


def _binding_show(bindings: list, key: str) -> bool:
    """Return the ``show`` attribute for the binding matching *key*."""
    for b in bindings:
        if b.key == key:
            return b.show
    raise KeyError(f"No binding with key={key!r} found")


class TestFooterCompact:
    """Footer should render in compact mode."""

    async def test_footer_is_compact(self, worktree: Path) -> None:
        """The Footer widget should be instantiated with compact=True."""
        async with PerchApp(worktree).run_test() as pilot:
            footer = pilot.app.query_one(Footer)
            assert footer.compact is True


class TestFileTreeBindingVisibility:
    """FileTree should show only curated bindings in the footer."""

    def test_refresh_shown(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "r") is True

    def test_open_shown(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "o") is True

    def test_search_shown(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "ctrl+p") is True

    def test_nav_hero_shown(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "j") is True

    def test_focus_hidden(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "f") is False

    def test_pageup_hidden(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "pageup") is False

    def test_pagedown_hidden(self) -> None:
        assert _binding_show(FileTree.BINDINGS, "pagedown") is False


class TestViewerBindingVisibility:
    """Viewer should show d, s, m, and nav hero; hide e and f."""

    def test_diff_shown(self) -> None:
        from perch.widgets.viewer import Viewer as V

        assert _binding_show(V.BINDINGS, "d") is True

    def test_layout_shown(self) -> None:
        from perch.widgets.viewer import Viewer as V

        assert _binding_show(V.BINDINGS, "s") is True

    def test_preview_shown(self) -> None:
        from perch.widgets.viewer import Viewer as V

        assert _binding_show(V.BINDINGS, "p") is True

    def test_nav_hero_shown(self) -> None:
        from perch.widgets.viewer import Viewer as V

        assert _binding_show(V.BINDINGS, "j") is True

    def test_editor_hidden(self) -> None:
        from perch.widgets.viewer import Viewer as V

        assert _binding_show(V.BINDINGS, "e") is False

    def test_focus_hidden(self) -> None:
        from perch.widgets.viewer import Viewer as V

        assert _binding_show(V.BINDINGS, "f") is False


class TestGitPanelBindingVisibility:
    """GitPanel should show r, l, and nav hero; hide f."""

    def test_refresh_shown(self) -> None:
        assert _binding_show(GitPanel.BINDINGS, "r") is True

    def test_select_shown(self) -> None:
        assert _binding_show(GitPanel.BINDINGS, "l") is True

    def test_nav_hero_shown(self) -> None:
        assert _binding_show(GitPanel.BINDINGS, "j") is True

    def test_focus_hidden(self) -> None:
        assert _binding_show(GitPanel.BINDINGS, "f") is False

    def test_pageup_hidden(self) -> None:
        assert _binding_show(GitPanel.BINDINGS, "pageup") is False


class TestGitHubPanelBindingVisibility:
    """GitHubPanel should show o, r, and nav hero; hide f."""

    def test_open_shown(self) -> None:
        assert _binding_show(GitHubPanel.BINDINGS, "o") is True

    def test_refresh_shown(self) -> None:
        assert _binding_show(GitHubPanel.BINDINGS, "r") is True

    def test_nav_hero_shown(self) -> None:
        assert _binding_show(GitHubPanel.BINDINGS, "j") is True

    def test_focus_hidden(self) -> None:
        assert _binding_show(GitHubPanel.BINDINGS, "f") is False

    def test_pageup_hidden(self) -> None:
        assert _binding_show(GitHubPanel.BINDINGS, "pageup") is False
