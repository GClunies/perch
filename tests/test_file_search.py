"""Tests for fuzzy file search modal."""

from pathlib import Path
from unittest.mock import patch

from textual.widgets import Input, ListView

from perch.app import PerchApp
from perch.widgets.file_search import FileSearchScreen, collect_files, fuzzy_score


class TestCollectFiles:
    """Tests for file collection with exclusions."""

    def test_collects_regular_files(self, tmp_path: Path) -> None:
        (tmp_path / "foo.py").write_text("x")
        (tmp_path / "bar.txt").write_text("y")
        result = collect_files(tmp_path)
        assert sorted(result) == ["bar.txt", "foo.py"]

    def test_collects_nested_files(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x")
        result = collect_files(tmp_path)
        assert result == ["src/main.py"]

    def test_excludes_git_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x")
        (tmp_path / "ok.py").write_text("y")
        result = collect_files(tmp_path)
        assert result == ["ok.py"]

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.pyc").write_text("x")
        result = collect_files(tmp_path)
        assert result == []

    def test_excludes_node_modules(self, tmp_path: Path) -> None:
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("x")
        (tmp_path / "app.js").write_text("y")
        result = collect_files(tmp_path)
        assert result == ["app.js"]

    def test_excludes_egg_info(self, tmp_path: Path) -> None:
        (tmp_path / "mylib.egg-info").mkdir()
        (tmp_path / "mylib.egg-info" / "PKG-INFO").write_text("x")
        result = collect_files(tmp_path)
        assert result == []

    def test_excludes_nested_noise(self, tmp_path: Path) -> None:
        """Noise dirs inside regular dirs are still excluded."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__pycache__").mkdir()
        (tmp_path / "src" / "__pycache__" / "mod.pyc").write_text("x")
        (tmp_path / "src" / "real.py").write_text("y")
        result = collect_files(tmp_path)
        assert result == ["src/real.py"]

    def test_empty_dir(self, tmp_path: Path) -> None:
        result = collect_files(tmp_path)
        assert result == []

    def test_skips_directories(self, tmp_path: Path) -> None:
        """Only files are collected, not directories."""
        (tmp_path / "subdir").mkdir()
        result = collect_files(tmp_path)
        assert result == []


class TestFuzzyScore:
    """Tests for the fuzzy scoring algorithm."""

    def test_empty_query_matches_everything(self) -> None:
        assert fuzzy_score("", "anything") == 0

    def test_exact_match(self) -> None:
        score = fuzzy_score("main.py", "main.py")
        assert score is not None
        assert score > 0

    def test_no_match(self) -> None:
        assert fuzzy_score("xyz", "main.py") is None

    def test_subsequence_match(self) -> None:
        score = fuzzy_score("mp", "main.py")
        assert score is not None

    def test_case_insensitive(self) -> None:
        score = fuzzy_score("Main", "main.py")
        assert score is not None

    def test_order_matters(self) -> None:
        """Characters must appear in order."""
        assert fuzzy_score("pm", "main.py") is None

    def test_consecutive_bonus(self) -> None:
        """Consecutive matches score higher than scattered ones."""
        consecutive = fuzzy_score("main", "main.py")
        scattered = fuzzy_score("main", "m_a_i_n.py")
        assert consecutive is not None
        assert scattered is not None
        assert consecutive > scattered

    def test_shorter_candidate_preferred(self) -> None:
        """Shorter paths score higher for the same query."""
        short = fuzzy_score("m", "m.py")
        long = fuzzy_score("m", "very/long/path/to/m.py")
        assert short is not None
        assert long is not None
        assert short > long

    def test_segment_start_bonus(self) -> None:
        """Matches at path segment boundaries get a bonus."""
        at_boundary = fuzzy_score("g", "src/git.py")
        mid_word = fuzzy_score("g", "flagging.py")
        assert at_boundary is not None
        assert mid_word is not None
        assert at_boundary > mid_word

    def test_partial_query(self) -> None:
        score = fuzzy_score("fs", "file_search.py")
        assert score is not None


def _create_worktree(tmp_path: Path) -> Path:
    """Create a minimal worktree with a few files for search testing."""
    (tmp_path / "hello.py").write_text("print('hello')\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "world.txt").write_text("world\n")
    (tmp_path / "README.md").write_text("# readme\n")
    return tmp_path


def _service_patches():
    """Patch git/github services to prevent real subprocess calls."""
    return (
        patch("perch.services.git.get_status", return_value=__import__("perch.models", fromlist=["GitStatusData"]).GitStatusData()),
        patch("perch.services.git.get_log", return_value=[]),
        patch("perch.services.github.get_pr_context", return_value=None),
        patch("perch.services.github.get_checks", return_value=[]),
    )


class TestFileSearchScreen:
    """Tests for the FileSearchScreen modal."""

    async def test_compose_shows_input_and_list(self, tmp_path: Path) -> None:
        """Screen should have an Input and a ListView."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                screen = pilot.app.screen
                assert isinstance(screen, FileSearchScreen)
                search_input = screen.query_one("#search-input", Input)
                assert search_input is not None
                list_view = screen.query_one("#search-results", ListView)
                assert list_view is not None

    async def test_mount_populates_results(self, tmp_path: Path) -> None:
        """On mount, all files should appear in the results (up to 50)."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                screen = pilot.app.screen
                assert isinstance(screen, FileSearchScreen)
                list_view = screen.query_one("#search-results", ListView)
                # Should have 3 files: README.md, hello.py, sub/world.txt
                assert len(list_view.children) == 3

    async def test_typing_filters_results(self, tmp_path: Path) -> None:
        """Typing in the search input should filter results."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                screen = pilot.app.screen
                assert isinstance(screen, FileSearchScreen)
                list_view = screen.query_one("#search-results", ListView)
                assert len(list_view.children) == 3
                # Type "hello" to filter
                await pilot.press("h", "e", "l", "l", "o")
                await pilot.pause()
                await pilot.pause()
                # Only hello.py should match
                names = [child.name for child in list_view.children]
                assert len(names) >= 1
                assert "hello.py" in names

    async def test_enter_dismisses_with_selection(self, tmp_path: Path) -> None:
        """Pressing Enter should dismiss with the highlighted item's name."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                screen = pilot.app.screen
                assert isinstance(screen, FileSearchScreen)
                list_view = screen.query_one("#search-results", ListView)
                assert len(list_view.children) > 0
                # Focus the list and highlight the first item
                list_view.focus()
                list_view.index = 0
                await pilot.pause()
                highlighted = list_view.highlighted_child
                assert highlighted is not None
                expected_name = highlighted.name
                # Press Enter to dismiss
                await pilot.press("enter")
                await pilot.pause()
                await pilot.pause()
                # Screen should be dismissed; we should be back on PerchApp's main screen
                assert not isinstance(pilot.app.screen, FileSearchScreen)
                # The viewer should have loaded the selected file
                from perch.widgets.viewer import Viewer
                viewer = pilot.app.query_one(Viewer)
                assert viewer._current_path == worktree / expected_name

    async def test_escape_dismisses_with_none(self, tmp_path: Path) -> None:
        """Pressing Escape should dismiss with None."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                # Load a file first so we can verify escape doesn't change it
                from perch.widgets.viewer import Viewer
                viewer = pilot.app.query_one(Viewer)
                viewer.load_file(worktree / "hello.py")
                await pilot.pause()
                path_before = viewer._current_path
                # Open search
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                assert isinstance(pilot.app.screen, FileSearchScreen)
                # Press Escape to cancel
                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()
                # Should be back on main screen, viewer unchanged
                assert not isinstance(pilot.app.screen, FileSearchScreen)
                assert viewer._current_path == path_before

    async def test_empty_query_shows_all_files(self, tmp_path: Path) -> None:
        """Clearing the query should show all files again."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                screen = pilot.app.screen
                assert isinstance(screen, FileSearchScreen)
                list_view = screen.query_one("#search-results", ListView)
                initial_count = len(list_view.children)
                assert initial_count == 3
                # Type something to filter
                await pilot.press("h", "e", "l")
                await pilot.pause()
                await pilot.pause()
                filtered_count = len(list_view.children)
                assert filtered_count < initial_count
                # Clear the input by selecting all and deleting
                search_input = screen.query_one("#search-input", Input)
                search_input.value = ""
                await pilot.pause()
                await pilot.pause()
                # All files should be shown again
                assert len(list_view.children) == initial_count

    async def test_list_item_selected_dismisses(self, tmp_path: Path) -> None:
        """Selecting a ListView item directly should dismiss with that item's name."""
        worktree = _create_worktree(tmp_path)
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(worktree)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.action_file_search()
                await pilot.pause()
                await pilot.pause()
                screen = pilot.app.screen
                assert isinstance(screen, FileSearchScreen)
                list_view = screen.query_one("#search-results", ListView)
                assert len(list_view.children) > 0
                # Directly post a ListView.Selected message to trigger _on_selected
                target_item = list_view.children[0]
                expected_name = target_item.name
                screen._on_selected(ListView.Selected(list_view, target_item, 0))
                await pilot.pause()
                await pilot.pause()
                # Screen should be dismissed
                assert not isinstance(pilot.app.screen, FileSearchScreen)
                # The viewer should have loaded the selected file
                from perch.widgets.viewer import Viewer
                viewer = pilot.app.query_one(Viewer)
                assert viewer._current_path == worktree / expected_name
