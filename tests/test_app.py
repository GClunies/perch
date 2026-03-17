"""Tests for PerchApp tabbed layout and tree-to-viewer wiring."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Footer, Header, TabbedContent, TabPane

from perch.app import PerchApp
from perch.commands import DiscoveryCommandProvider
from perch.widgets.file_tree import WorktreeFileTree
from perch.widgets.file_viewer import FileViewer
from perch.widgets.git_status import GitStatusPanel
from perch.widgets.pr_context import PRContextPanel
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


class TestActionShowTab:
    """Tests for action_show_tab() — switching tabs and focusing content."""

    async def test_show_tab_switches_to_git(self, worktree: Path) -> None:
        """action_show_tab('tab-git') should activate the git tab."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_show_tab("tab-git")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-git"

    async def test_show_tab_switches_to_pr(self, worktree: Path) -> None:
        """action_show_tab('tab-pr') should activate the pr tab."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_show_tab("tab-pr")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-pr"

    async def test_show_tab_switches_to_files(self, worktree: Path) -> None:
        """action_show_tab('tab-files') should activate the files tab."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_show_tab("tab-git")
            await pilot.pause()
            pilot.app.action_show_tab("tab-files")
            await pilot.pause()
            assert pilot.app.query_one(TabbedContent).active == "tab-files"

    async def test_show_tab_focuses_git_panel(self, worktree: Path) -> None:
        """Switching to git tab should focus the GitStatusPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_show_tab("tab-git")
            await pilot.pause()
            panel = pilot.app.query_one(GitStatusPanel)
            assert panel.has_focus

    async def test_show_tab_focuses_pr_panel(self, worktree: Path) -> None:
        """Switching to PR tab should focus the PRContextPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_show_tab("tab-pr")
            await pilot.pause()
            panel = pilot.app.query_one(PRContextPanel)
            assert panel.has_focus

    async def test_show_tab_focuses_file_tree(self, worktree: Path) -> None:
        """Switching to files tab should focus the WorktreeFileTree."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # Switch away first
            pilot.app.action_show_tab("tab-git")
            await pilot.pause()
            pilot.app.action_show_tab("tab-files")
            await pilot.pause()
            tree = pilot.app.query_one(WorktreeFileTree)
            assert tree.has_focus


class TestFocusPaneToggle:
    """Tests for action_focus_next_pane() and action_focus_prev_pane()."""

    async def test_focus_next_pane_from_right_to_left(self, worktree: Path) -> None:
        """Tab from right pane should move focus to the file viewer."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # Start: file tree is focused (right pane)
            tree = pilot.app.query_one(WorktreeFileTree)
            tree.focus()
            await pilot.pause()
            # Press tab to toggle to left pane
            pilot.app.action_focus_next_pane()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", FileViewer)
            assert viewer.has_focus

    async def test_focus_next_pane_from_left_to_right(self, worktree: Path) -> None:
        """Tab from left pane should move focus back to the active tab."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one("#left-pane", FileViewer)
            viewer.focus()
            await pilot.pause()
            assert viewer.has_focus
            # Press tab to toggle to right pane
            pilot.app.action_focus_next_pane()
            await pilot.pause()
            # Should be on the file tree (active tab is files)
            tree = pilot.app.query_one(WorktreeFileTree)
            assert tree.has_focus



class TestFocusActiveTab:
    """Tests for _focus_active_tab() targeting each tab."""

    async def test_focus_active_tab_files_sets_cursor(self, worktree: Path) -> None:
        """_focus_active_tab on files tab should set cursor to 0 if -1."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            tree = pilot.app.query_one(WorktreeFileTree)
            tree.cursor_line = -1
            pilot.app._focus_active_tab()
            await pilot.pause()
            assert tree.cursor_line == 0

    async def test_focus_active_tab_git(self, worktree: Path) -> None:
        """_focus_active_tab on git tab should focus the GitStatusPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # Use action_show_tab to switch and focus in one step
            pilot.app.action_show_tab("tab-git")
            await pilot.pause()
            await pilot.pause()
            assert pilot.app.query_one(GitStatusPanel).has_focus

    async def test_focus_active_tab_pr(self, worktree: Path) -> None:
        """_focus_active_tab on pr tab should focus the PRContextPanel."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_show_tab("tab-pr")
            await pilot.pause()
            await pilot.pause()
            assert pilot.app.query_one(PRContextPanel).has_focus


class TestGitStatusPanelFileSelected:
    """Tests for on_git_status_panel_file_selected() handler."""

    async def test_file_selected_loads_existing_file(
        self, git_worktree: Path
    ) -> None:
        """Selecting an existing file should load it in the viewer."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            event = GitStatusPanel.FileSelected(path="hello.py", staged=False)
            pilot.app.on_git_status_panel_file_selected(event)
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
            viewer = pilot.app.query_one(FileViewer)
            event = GitStatusPanel.FileSelected(path="hello.py", staged=False)
            pilot.app.on_git_status_panel_file_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer._current_path == git_worktree / "hello.py"

    async def test_file_selected_deleted_file_no_diff(
        self, worktree: Path
    ) -> None:
        """Selecting a deleted file with no git diff available should show fallback."""
        # No git repo, so get_diff will raise RuntimeError
        # Remove file so it is not found
        deleted_name = "gone.py"
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            event = GitStatusPanel.FileSelected(path=deleted_name, staged=False)
            pilot.app.on_git_status_panel_file_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer._current_path == worktree / deleted_name


class TestGitStatusPanelCommitSelected:
    """Tests for on_git_status_panel_commit_selected() handler."""

    async def test_commit_selected_loads_commit_diff(
        self, git_worktree: Path
    ) -> None:
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
            viewer = pilot.app.query_one(FileViewer)
            event = GitStatusPanel.CommitSelected(commit_hash=commit_hash)
            pilot.app.on_git_status_panel_commit_selected(event)
            await pilot.pause()
            assert viewer._diff_mode is True
            assert viewer.worktree_root == git_worktree


class TestToggleDiff:
    """Tests for action_toggle_diff() and action_toggle_diff_layout()."""

    async def test_toggle_diff_delegates_to_viewer(self, worktree: Path) -> None:
        """action_toggle_diff should call the viewer's action_toggle_diff."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            with patch.object(viewer, "action_toggle_diff") as mock:
                pilot.app.action_toggle_diff()
                mock.assert_called_once()

    async def test_toggle_diff_layout_delegates_to_viewer(
        self, worktree: Path
    ) -> None:
        """action_toggle_diff_layout should call the viewer's method."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            with patch.object(viewer, "action_toggle_diff_layout") as mock:
                pilot.app.action_toggle_diff_layout()
                mock.assert_called_once()


class TestDiffFileNavigation:
    """Tests for action_next_diff_file() and action_prev_diff_file()."""

    async def test_next_diff_file_delegates_to_viewer(
        self, worktree: Path
    ) -> None:
        """action_next_diff_file should call the viewer's action."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            with patch.object(viewer, "action_next_diff_file") as mock:
                pilot.app.action_next_diff_file()
                mock.assert_called_once()

    async def test_prev_diff_file_delegates_to_viewer(
        self, worktree: Path
    ) -> None:
        """action_prev_diff_file should call the viewer's action."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            with patch.object(viewer, "action_prev_diff_file") as mock:
                pilot.app.action_prev_diff_file()
                mock.assert_called_once()


class TestToggleFocusMode:
    """Tests for action_toggle_focus_mode()."""

    async def test_focus_mode_hides_right_pane(self, worktree: Path) -> None:
        """Entering focus mode should hide the right pane and splitter."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            right_pane = pilot.app.query_one("#right-pane", TabbedContent)
            splitter = pilot.app.query_one(DraggableSplitter)
            assert right_pane.display is False
            assert splitter.display is False
            assert pilot.app._focus_mode is True

    async def test_focus_mode_sets_viewer_full_width(self, worktree: Path) -> None:
        """Entering focus mode should set the viewer width to 100%."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", FileViewer)
            assert viewer.styles.width is not None
            assert "100" in str(viewer.styles.width)

    async def test_focus_mode_focuses_viewer(self, worktree: Path) -> None:
        """Entering focus mode should focus the viewer."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            viewer = pilot.app.query_one("#left-pane", FileViewer)
            assert viewer.has_focus

    async def test_exit_focus_mode_restores_layout(self, worktree: Path) -> None:
        """Exiting focus mode should restore the right pane and splitter."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            # Enter focus mode
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            # Exit focus mode
            pilot.app.action_toggle_focus_mode()
            await pilot.pause()
            right_pane = pilot.app.query_one("#right-pane", TabbedContent)
            splitter = pilot.app.query_one(DraggableSplitter)
            assert right_pane.display is True
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
            viewer = pilot.app.query_one("#left-pane", FileViewer)
            assert "60" in str(viewer.styles.width)


class TestResizePanes:
    """Tests for action_shrink_left_pane() and action_grow_left_pane()."""

    async def test_shrink_left_pane_delegates(self, worktree: Path) -> None:
        """action_shrink_left_pane should call splitter.resize_left_pane(-2)."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_shrink_left_pane()
                mock.assert_called_once_with(-2)

    async def test_grow_left_pane_delegates(self, worktree: Path) -> None:
        """action_grow_left_pane should call splitter.resize_left_pane(2)."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            splitter = pilot.app.query_one(DraggableSplitter)
            with patch.object(splitter, "resize_left_pane") as mock:
                pilot.app.action_grow_left_pane()
                mock.assert_called_once_with(2)


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
            viewer = pilot.app.query_one(FileViewer)
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
            viewer = pilot.app.query_one(FileViewer)
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
            viewer = pilot.app.query_one(FileViewer)
            viewer.load_file(worktree / "hello.py")
            await pilot.pause()
            # Should not raise
            pilot.app.watch_theme()

    async def test_watch_theme_in_diff_mode(self, git_worktree: Path) -> None:
        """watch_theme in diff mode should call _load_diff."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            viewer._current_path = git_worktree / "hello.py"
            viewer._diff_mode = True
            with patch.object(viewer, "_load_diff") as mock:
                pilot.app.watch_theme()
                mock.assert_called_once()


class TestFileSearch:
    """Tests for action_file_search and _on_file_selected callback."""

    async def test_on_file_selected_none_is_noop(self, worktree: Path) -> None:
        """_on_file_selected(None) should not load any file."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            viewer._current_path = None
            pilot.app._on_file_selected(None)
            await pilot.pause()
            assert viewer._current_path is None

    async def test_on_file_selected_loads_valid_file(self, worktree: Path) -> None:
        """_on_file_selected with a valid relative path should load the file."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            pilot.app._on_file_selected("hello.py")
            await pilot.pause()
            assert viewer._current_path == worktree / "hello.py"

    async def test_on_file_selected_nonexistent_file_is_noop(
        self, worktree: Path
    ) -> None:
        """_on_file_selected with a non-existent file should not load it."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(FileViewer)
            viewer._current_path = None
            pilot.app._on_file_selected("nonexistent.py")
            await pilot.pause()
            assert viewer._current_path is None

    async def test_file_search_pushes_screen(self, worktree: Path) -> None:
        """action_file_search should push a FileSearchScreen."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            with patch.object(pilot.app, "push_screen") as mock:
                pilot.app.action_file_search()
                mock.assert_called_once()
