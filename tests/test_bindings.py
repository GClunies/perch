"""Tests for shared binding constants and factory functions."""

from textual.binding import Binding


# ---------------------------------------------------------------------------
# Step 1.1 — tests for make_nav_bindings() and shared constants
# ---------------------------------------------------------------------------


class TestMakeNavBindingsDefaults:
    """make_nav_bindings() with default cursor_down/cursor_up actions."""

    def test_returns_tuple(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert isinstance(result, tuple)

    def test_default_returns_two_bindings(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert len(result) == 2

    def test_default_keys_are_j_k(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert result[0].key == "j"
        assert result[1].key == "k"

    def test_default_actions_are_cursor(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert result[0].action == "cursor_down"
        assert result[1].action == "cursor_up"

    def test_first_binding_has_hero_key_display(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert result[0].key_display == "hjkl/\u2190\u2193\u2191\u2192"

    def test_first_binding_is_shown(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert result[0].show is True

    def test_second_binding_is_hidden(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings()
        assert result[1].show is False

    def test_all_are_binding_instances(self):
        from perch._bindings import make_nav_bindings

        for b in make_nav_bindings():
            assert isinstance(b, Binding)


class TestMakeNavBindingsScroll:
    """make_nav_bindings() with 4 scroll actions."""

    def test_scroll_returns_four_bindings(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings(
            "scroll_down", "scroll_up", "scroll_left", "scroll_right"
        )
        assert len(result) == 4

    def test_scroll_keys(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings(
            "scroll_down", "scroll_up", "scroll_left", "scroll_right"
        )
        assert result[0].key == "j"
        assert result[1].key == "k"
        assert result[2].key == "h"
        assert result[3].key == "l"

    def test_scroll_actions(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings(
            "scroll_down", "scroll_up", "scroll_left", "scroll_right"
        )
        assert result[0].action == "scroll_down"
        assert result[1].action == "scroll_up"
        assert result[2].action == "scroll_left"
        assert result[3].action == "scroll_right"

    def test_only_first_binding_shown(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings(
            "scroll_down", "scroll_up", "scroll_left", "scroll_right"
        )
        assert result[0].show is True
        assert all(b.show is False for b in result[1:])

    def test_first_binding_has_hero_key_display(self):
        from perch._bindings import make_nav_bindings

        result = make_nav_bindings(
            "scroll_down", "scroll_up", "scroll_left", "scroll_right"
        )
        assert result[0].key_display == "hjkl/\u2190\u2193\u2191\u2192"


class TestSharedConstants:
    """Tests for FOCUS_BINDING, REFRESH_BINDING, PAGE_BINDINGS."""

    def test_focus_binding_key(self):
        from perch._bindings import FOCUS_BINDING

        assert FOCUS_BINDING.key == "f"

    def test_focus_binding_action(self):
        from perch._bindings import FOCUS_BINDING

        assert FOCUS_BINDING.action == "app.toggle_focus_mode"

    def test_focus_binding_description(self):
        from perch._bindings import FOCUS_BINDING

        assert FOCUS_BINDING.description == "Focus"

    def test_focus_binding_no_group(self):
        from perch._bindings import FOCUS_BINDING

        assert FOCUS_BINDING.group is None

    def test_focus_binding_is_binding(self):
        from perch._bindings import FOCUS_BINDING

        assert isinstance(FOCUS_BINDING, Binding)

    def test_refresh_binding_key(self):
        from perch._bindings import REFRESH_BINDING

        assert REFRESH_BINDING.key == "r"

    def test_refresh_binding_action(self):
        from perch._bindings import REFRESH_BINDING

        assert REFRESH_BINDING.action == "refresh"

    def test_refresh_binding_description(self):
        from perch._bindings import REFRESH_BINDING

        assert REFRESH_BINDING.description == "Refresh"

    def test_refresh_binding_no_group(self):
        from perch._bindings import REFRESH_BINDING

        assert REFRESH_BINDING.group is None

    def test_refresh_binding_is_binding(self):
        from perch._bindings import REFRESH_BINDING

        assert isinstance(REFRESH_BINDING, Binding)

    def test_page_bindings_is_tuple(self):
        from perch._bindings import PAGE_BINDINGS

        assert isinstance(PAGE_BINDINGS, tuple)

    def test_page_bindings_has_two(self):
        from perch._bindings import PAGE_BINDINGS

        assert len(PAGE_BINDINGS) == 2

    def test_page_bindings_keys(self):
        from perch._bindings import PAGE_BINDINGS

        keys = {b.key for b in PAGE_BINDINGS}
        assert "pageup" in keys
        assert "pagedown" in keys

    def test_page_bindings_hidden(self):
        from perch._bindings import PAGE_BINDINGS

        for b in PAGE_BINDINGS:
            assert b.show is False

    def test_page_bindings_are_binding_instances(self):
        from perch._bindings import PAGE_BINDINGS

        for b in PAGE_BINDINGS:
            assert isinstance(b, Binding)


# ---------------------------------------------------------------------------
# Step 1.3 — tests for widget binding substitutions
# ---------------------------------------------------------------------------


class TestFileTreeUsesSharedBindings:
    """FileTree.BINDINGS should include the shared binding objects."""

    def test_contains_nav_bindings(self):
        from perch._bindings import make_nav_bindings
        from perch.widgets.file_tree import FileTree

        nav = make_nav_bindings()
        for b in nav:
            assert b in FileTree.BINDINGS

    def test_contains_focus_binding(self):
        from perch._bindings import FOCUS_BINDING
        from perch.widgets.file_tree import FileTree

        assert FOCUS_BINDING in FileTree.BINDINGS

    def test_contains_refresh_binding(self):
        from perch._bindings import REFRESH_BINDING
        from perch.widgets.file_tree import FileTree

        assert REFRESH_BINDING in FileTree.BINDINGS

    def test_contains_page_bindings(self):
        from perch._bindings import PAGE_BINDINGS
        from perch.widgets.file_tree import FileTree

        for b in PAGE_BINDINGS:
            assert b in FileTree.BINDINGS

    def test_all_bindings_are_binding_instances(self):
        from perch.widgets.file_tree import FileTree

        for b in FileTree.BINDINGS:
            assert isinstance(b, Binding)


class TestViewerUsesSharedBindings:
    """Viewer.BINDINGS should use make_nav_bindings with scroll actions."""

    def test_contains_scroll_nav_bindings(self):
        from perch._bindings import make_nav_bindings
        from perch.widgets.viewer import Viewer

        nav = make_nav_bindings(
            "scroll_down", "scroll_up", "scroll_left", "scroll_right"
        )
        for b in nav:
            assert b in Viewer.BINDINGS

    def test_contains_focus_binding(self):
        from perch._bindings import FOCUS_BINDING
        from perch.widgets.viewer import Viewer

        assert FOCUS_BINDING in Viewer.BINDINGS

    def test_all_bindings_are_binding_instances(self):
        from perch.widgets.viewer import Viewer

        for b in Viewer.BINDINGS:
            assert isinstance(b, Binding)


class TestGitPanelUsesSharedBindings:
    """GitPanel.BINDINGS should include the shared binding objects."""

    def test_contains_nav_bindings(self):
        from perch._bindings import make_nav_bindings
        from perch.widgets.git_status import GitPanel

        nav = make_nav_bindings()
        for b in nav:
            assert b in GitPanel.BINDINGS

    def test_contains_focus_binding(self):
        from perch._bindings import FOCUS_BINDING
        from perch.widgets.git_status import GitPanel

        assert FOCUS_BINDING in GitPanel.BINDINGS

    def test_contains_refresh_binding(self):
        from perch._bindings import REFRESH_BINDING
        from perch.widgets.git_status import GitPanel

        assert REFRESH_BINDING in GitPanel.BINDINGS

    def test_contains_page_bindings(self):
        from perch._bindings import PAGE_BINDINGS
        from perch.widgets.git_status import GitPanel

        for b in PAGE_BINDINGS:
            assert b in GitPanel.BINDINGS

    def test_all_bindings_are_binding_instances(self):
        from perch.widgets.git_status import GitPanel

        for b in GitPanel.BINDINGS:
            assert isinstance(b, Binding)


class TestGitHubPanelUsesSharedBindings:
    """GitHubPanel.BINDINGS should include the shared binding objects."""

    def test_contains_nav_bindings(self):
        from perch._bindings import make_nav_bindings
        from perch.widgets.github_panel import GitHubPanel

        nav = make_nav_bindings()
        for b in nav:
            assert b in GitHubPanel.BINDINGS

    def test_contains_focus_binding(self):
        from perch._bindings import FOCUS_BINDING
        from perch.widgets.github_panel import GitHubPanel

        assert FOCUS_BINDING in GitHubPanel.BINDINGS

    def test_contains_refresh_binding(self):
        from perch._bindings import REFRESH_BINDING
        from perch.widgets.github_panel import GitHubPanel

        assert REFRESH_BINDING in GitHubPanel.BINDINGS

    def test_contains_page_bindings(self):
        from perch._bindings import PAGE_BINDINGS
        from perch.widgets.github_panel import GitHubPanel

        for b in PAGE_BINDINGS:
            assert b in GitHubPanel.BINDINGS

    def test_all_bindings_are_binding_instances(self):
        from perch.widgets.github_panel import GitHubPanel

        for b in GitHubPanel.BINDINGS:
            assert isinstance(b, Binding)
