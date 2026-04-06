"""Tests for the Viewer widget's helper functions."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.text import Text

from perch.app import PerchApp
from perch.models import CommitSummary
from perch.widgets.viewer import (
    BINARY_CHECK_SIZE,
    MAX_LINES,
    Viewer,
    SyncedDiffView,
    is_binary,
    parse_diff_sides,
    read_file_content,
    render_diff,
)


class TestIsBinary:
    def test_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        assert is_binary(f) is False

    def test_binary_file(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        assert is_binary(f) is True

    def test_null_byte_at_start(self, tmp_path: Path) -> None:
        f = tmp_path / "null.bin"
        f.write_bytes(b"\x00rest of file")
        assert is_binary(f) is True

    def test_null_byte_near_end_of_check_window(self, tmp_path: Path) -> None:
        f = tmp_path / "late_null.bin"
        f.write_bytes(b"A" * (BINARY_CHECK_SIZE - 1) + b"\x00")
        assert is_binary(f) is True

    def test_null_byte_beyond_check_window(self, tmp_path: Path) -> None:
        f = tmp_path / "far_null.bin"
        f.write_bytes(b"A" * BINARY_CHECK_SIZE + b"\x00")
        assert is_binary(f) is False

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert is_binary(f) is False

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nope.txt"
        assert is_binary(f) is False


class TestReadFileContent:
    def test_short_file(self, tmp_path: Path) -> None:
        f = tmp_path / "short.py"
        f.write_text("print('hi')\n")
        content, truncated = read_file_content(f)
        assert content == "print('hi')\n"
        assert truncated is False

    def test_exactly_max_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "exact.txt"
        lines = "line\n" * MAX_LINES
        f.write_text(lines)
        content, truncated = read_file_content(f)
        assert truncated is False
        assert content.count("\n") == MAX_LINES

    def test_over_max_lines_is_truncated(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        lines = "line\n" * (MAX_LINES + 100)
        f.write_text(lines)
        content, truncated = read_file_content(f)
        assert truncated is True
        assert content.count("\n") == MAX_LINES

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        content, truncated = read_file_content(f)
        assert content == ""
        assert truncated is False


class TestParseDiffSides:
    def test_context_lines_appear_on_both_sides(self) -> None:
        diff = " context line"
        left, right = parse_diff_sides(diff)
        assert left.plain == " context line"
        assert right.plain == " context line"

    def test_removed_lines_go_to_left_only(self) -> None:
        diff = "-removed line"
        left, right = parse_diff_sides(diff)
        assert left.plain == "-removed line"
        assert right.plain == ""

    def test_added_lines_go_to_right_only(self) -> None:
        diff = "+added line"
        left, right = parse_diff_sides(diff)
        assert left.plain == ""
        assert right.plain == "+added line"

    def test_file_headers_split_correctly(self) -> None:
        diff = "--- a/foo.py\n+++ b/foo.py"
        left, right = parse_diff_sides(diff)
        assert left.plain == "--- a/foo.py\n"
        assert right.plain == "\n+++ b/foo.py"

    def test_hunk_headers_appear_on_both_sides(self) -> None:
        diff = "@@ -1,3 +1,4 @@"
        left, right = parse_diff_sides(diff)
        assert left.plain == "@@ -1,3 +1,4 @@"
        assert right.plain == "@@ -1,3 +1,4 @@"

    def test_full_diff_alignment(self) -> None:
        """Left and right should have the same number of lines."""
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-old line\n"
            "+new line\n"
            " line3"
        )
        left, right = parse_diff_sides(diff)
        assert left.plain.count("\n") == right.plain.count("\n")

    def test_empty_diff(self) -> None:
        left, right = parse_diff_sides("")
        assert left.plain == ""
        assert right.plain == ""

    def test_multiple_removals_and_additions(self) -> None:
        diff = "-a\n-b\n+x\n+y\n+z"
        left, right = parse_diff_sides(diff)
        left_lines = left.plain.split("\n")
        right_lines = right.plain.split("\n")
        assert len(left_lines) == len(right_lines)
        assert left_lines[0] == "-a"
        assert left_lines[1] == "-b"
        assert right_lines[2] == "+x"
        assert right_lines[3] == "+y"
        assert right_lines[4] == "+z"


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    (tmp_path / "hello.py").write_text("print('hello')\n")
    return tmp_path


class TestViewerTheme:
    """Verify the file viewer background matches the active Textual theme."""

    async def test_background_color_matches_theme_surface(self, worktree: Path) -> None:
        """_get_background_color should return the current theme's surface color."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            surface = app.current_theme.surface
            assert viewer._get_background_color() == surface

    async def test_background_color_updates_on_theme_change(
        self, worktree: Path
    ) -> None:
        """Switching themes should change the background color returned."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)

            app.theme = "textual-dark"
            bg_dark = viewer._get_background_color()

            app.theme = "textual-light"
            bg_light = viewer._get_background_color()

            assert bg_dark != bg_light


# ---------------------------------------------------------------------------
# render_diff — lines 42-73
# ---------------------------------------------------------------------------
class TestRenderDiff:
    """Covers render_diff() for both dark and light themes."""

    SAMPLE_DIFF = (
        "--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,3 @@\n context\n-old line\n+new line"
    )

    def test_dark_mode_styles(self) -> None:
        result = render_diff(self.SAMPLE_DIFF, dark=True)
        assert isinstance(result, Text)
        assert "--- a/foo.py" in result.plain
        assert "+new line" in result.plain

    def test_light_mode_styles(self) -> None:
        result = render_diff(self.SAMPLE_DIFF, dark=False)
        assert isinstance(result, Text)
        assert "-old line" in result.plain

    def test_meta_lines_styled_bold(self) -> None:
        result = render_diff("--- a/f.py\n+++ b/f.py", dark=True)
        # Both meta lines present
        assert "--- a/f.py" in result.plain
        assert "+++ b/f.py" in result.plain

    def test_added_removed_hunk_context(self) -> None:
        diff = "@@ -1 +1 @@\n context\n-removed\n+added"
        result = render_diff(diff, dark=True)
        assert "context" in result.plain
        assert "-removed" in result.plain
        assert "+added" in result.plain

    def test_empty_diff(self) -> None:
        result = render_diff("", dark=True)
        assert result.plain == ""

    def test_light_mode_context_unstyled(self) -> None:
        result = render_diff(" plain context", dark=False)
        assert result.plain == " plain context"


# ---------------------------------------------------------------------------
# parse_diff_sides — light mode (lines 88-91)
# ---------------------------------------------------------------------------
class TestParseDiffSidesLightMode:
    """Covers the dark=False branch of parse_diff_sides."""

    def test_light_mode_produces_text(self) -> None:
        diff = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n ctx"
        left, right = parse_diff_sides(diff, dark=False)
        assert isinstance(left, Text)
        assert isinstance(right, Text)
        assert "-old" in left.plain
        assert "+new" in right.plain
        assert "ctx" in left.plain
        assert "ctx" in right.plain


# ---------------------------------------------------------------------------
# SyncedDiffView — lines 118-186
# ---------------------------------------------------------------------------
class TestSyncedDiffView:
    """Covers the SyncedDiffView compose and scroll actions."""

    async def test_compose_creates_panels(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            sdv = viewer.query_one(SyncedDiffView)
            # The two panels and their content statics exist
            assert sdv.query_one("#diff-left-content")
            assert sdv.query_one("#diff-right-content")

    async def test_scroll_actions_do_not_raise(self, worktree: Path) -> None:
        """All 8 scroll actions should execute without error."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            sdv = viewer.query_one(SyncedDiffView)
            # Make the diff container visible so scrolls have a target
            sdv.display = True
            sdv.action_scroll_up()
            sdv.action_scroll_down()
            sdv.action_scroll_left()
            sdv.action_scroll_right()
            sdv.action_scroll_home()
            sdv.action_scroll_end()
            sdv.action_page_up()
            sdv.action_page_down()


# ---------------------------------------------------------------------------
# Viewer scroll action overrides (animate=False)
# ---------------------------------------------------------------------------
class TestViewerScrollActions:
    async def test_scroll_actions_do_not_raise(self, worktree: Path) -> None:
        """Viewer scroll overrides should execute without error."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.action_scroll_up()
            viewer.action_scroll_down()
            viewer.action_scroll_left()
            viewer.action_scroll_right()


# ---------------------------------------------------------------------------
# Viewer._get_syntax_theme / _is_dark_theme (lines 211-237)
# ---------------------------------------------------------------------------
class TestViewerHelpers:
    async def test_get_syntax_theme_dark(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            app.theme = "textual-dark"
            viewer = app.query_one(Viewer)
            assert viewer._get_syntax_theme() == "monokai"

    async def test_get_syntax_theme_light(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            app.theme = "textual-light"
            viewer = app.query_one(Viewer)
            assert viewer._get_syntax_theme() == "default"

    async def test_is_dark_theme_dark(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            app.theme = "textual-dark"
            viewer = app.query_one(Viewer)
            assert viewer._is_dark_theme() is True

    async def test_is_dark_theme_light(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            app.theme = "textual-light"
            viewer = app.query_one(Viewer)
            assert viewer._is_dark_theme() is False


# ---------------------------------------------------------------------------
# Viewer.load_file — lines 273-313
# ---------------------------------------------------------------------------
class TestViewerLoadFile:
    async def test_load_normal_file(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            hello = worktree / "hello.py"
            viewer.load_file(hello)
            assert viewer._current_path == hello
            assert viewer._diff_mode is False

    async def test_load_nonexistent_path(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_file(worktree / "nope.py")
            # _content should say "Not a file"
            assert viewer._current_path == worktree / "nope.py"

    async def test_load_binary_file(self, worktree: Path) -> None:
        binary = worktree / "image.png"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_file(binary)
            assert viewer._current_path == binary

    async def test_load_directory_shows_not_a_file(self, worktree: Path) -> None:
        subdir = worktree / "subdir"
        subdir.mkdir()
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_file(subdir)
            assert viewer._current_path == subdir

    async def test_load_truncated_file(self, worktree: Path) -> None:
        big = worktree / "big.txt"
        big.write_text("line\n" * (MAX_LINES + 100))
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_file(big)
            assert viewer._current_path == big

    async def test_load_file_resets_diff_mode(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._diff_mode = True
            viewer._diff_layout = "side-by-side"
            viewer.load_file(worktree / "hello.py")
            assert viewer._diff_mode is False
            assert viewer._diff_layout == "unified"


# ---------------------------------------------------------------------------
# Viewer._load_diff — lines 317-347
# ---------------------------------------------------------------------------
class TestViewerLoadDiff:
    async def test_load_diff_no_file_selected(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = None
            viewer.worktree_root = worktree
            viewer._load_diff()
            # Should show "No file selected"

    async def test_load_diff_no_worktree_root(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = None
            viewer._load_diff()

    async def test_load_diff_file_not_in_worktree(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = Path("/some/other/place.py")
            viewer.worktree_root = worktree
            viewer._load_diff()

    async def test_load_diff_no_changes(self, worktree: Path) -> None:
        """When get_diff returns empty, show 'No changes'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            with patch("perch.services.git.get_diff", return_value=""):
                viewer._load_diff()

    async def test_load_diff_unified(self, worktree: Path) -> None:
        """When get_diff returns text and layout is unified, render_diff is used."""
        diff_text = "--- a/hello.py\n+++ b/hello.py\n@@ -1 +1 @@\n-old\n+new"
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            viewer._diff_layout = "unified"
            with patch("perch.services.git.get_diff", return_value=diff_text):
                viewer._load_diff()

    async def test_load_diff_side_by_side(self, worktree: Path) -> None:
        """Side-by-side layout uses _show_side_by_side_view."""
        diff_text = "--- a/hello.py\n+++ b/hello.py\n@@ -1 +1 @@\n-old\n+new"
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            viewer._diff_layout = "side-by-side"
            with patch("perch.services.git.get_diff", return_value=diff_text):
                viewer._load_diff()

    async def test_load_diff_runtime_error(self, worktree: Path) -> None:
        """RuntimeError from get_diff is caught and displayed."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            with patch(
                "perch.services.git.get_diff",
                side_effect=RuntimeError("git failed"),
            ):
                viewer._load_diff()


# ---------------------------------------------------------------------------
# Viewer.action_toggle_diff / action_toggle_diff_layout — lines 351-366
# ---------------------------------------------------------------------------
class TestViewerToggleDiff:
    async def test_toggle_diff_no_file(self, worktree: Path) -> None:
        """Toggle diff with no file should be a no-op."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = None
            viewer.action_toggle_diff()
            assert viewer._diff_mode is False

    async def test_toggle_diff_on_and_off(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            with patch("perch.services.git.get_diff", return_value=""):
                viewer.action_toggle_diff()
                assert viewer._diff_mode is True
                viewer.action_toggle_diff()
                assert viewer._diff_mode is False

    async def test_toggle_diff_layout_not_in_diff_mode(self, worktree: Path) -> None:
        """Toggle layout when not in diff mode is a no-op."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._diff_mode = False
            viewer.action_toggle_diff_layout()
            assert viewer._diff_layout == "unified"

    async def test_toggle_diff_layout_unified_to_side(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            viewer._diff_mode = True
            viewer._diff_layout = "unified"
            with patch("perch.services.git.get_diff", return_value=""):
                viewer.action_toggle_diff_layout()
                assert viewer._diff_layout == "side-by-side"

    async def test_toggle_diff_layout_side_to_unified(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._current_path = worktree / "hello.py"
            viewer.worktree_root = worktree
            viewer._diff_mode = True
            viewer._diff_layout = "side-by-side"
            with patch("perch.services.git.get_diff", return_value=""):
                viewer.action_toggle_diff_layout()
                assert viewer._diff_layout == "unified"


# ---------------------------------------------------------------------------
# Viewer._show_content_view / _show_side_by_side_view — lines 244-269
# ---------------------------------------------------------------------------
class TestViewerViewSwitching:
    async def test_show_content_view(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._show_content_view()
            assert viewer._content.display is True

    async def test_show_side_by_side_view(self, worktree: Path) -> None:
        diff_text = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new"
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._show_side_by_side_view(diff_text)
            assert viewer._content.display is False
            sdv = viewer.query_one("#diff-container", SyncedDiffView)
            assert sdv.display is True


# ---------------------------------------------------------------------------
# Edge cases for exception fallbacks and OSError — remaining uncovered lines
# ---------------------------------------------------------------------------
class TestViewerExceptionFallbacks:
    """Cover the except branches in _get_syntax_theme, _get_background_color,
    _is_dark_theme, and the OSError branch in load_file."""

    async def test_get_syntax_theme_exception_returns_monokai(
        self, worktree: Path
    ) -> None:
        """If app.current_theme raises, fall back to 'monokai'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            with patch.object(
                type(app),
                "current_theme",
                new_callable=lambda: property(
                    lambda self: (_ for _ in ()).throw(AttributeError("no theme"))
                ),
            ):
                assert viewer._get_syntax_theme() == "monokai"

    async def test_get_background_color_exception_returns_none(
        self, worktree: Path
    ) -> None:
        """If app.current_theme raises, fall back to None."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            with patch.object(
                type(app),
                "current_theme",
                new_callable=lambda: property(
                    lambda self: (_ for _ in ()).throw(AttributeError("no theme"))
                ),
            ):
                assert viewer._get_background_color() is None

    async def test_is_dark_theme_exception_returns_true(self, worktree: Path) -> None:
        """If app.current_theme raises, fall back to True (dark)."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            with patch.object(
                type(app),
                "current_theme",
                new_callable=lambda: property(
                    lambda self: (_ for _ in ()).throw(AttributeError("no theme"))
                ),
            ):
                assert viewer._is_dark_theme() is True

    async def test_load_file_oserror(self, worktree: Path) -> None:
        """OSError during read_file_content is caught and displayed."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            target = worktree / "hello.py"
            with patch(
                "perch.widgets.viewer.read_file_content",
                side_effect=OSError("permission denied"),
            ):
                viewer.load_file(target)
            assert viewer._current_path == target


class TestRenderImageHalfblocks:
    """Tests for render_image_halfblocks."""

    def test_renders_small_image(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_image_halfblocks
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (4, 4), color=(255, 0, 0))
        path = tmp_path / "red.png"
        img.save(path)
        result = render_image_halfblocks(path, max_width=10)
        assert result is not None
        assert "▀" in result.plain

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_image_halfblocks

        result = render_image_halfblocks(tmp_path / "nope.png")
        assert result is None

    def test_scales_wide_image(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_image_halfblocks
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (200, 100), color=(0, 128, 255))
        path = tmp_path / "wide.png"
        img.save(path)
        result = render_image_halfblocks(path, max_width=20)
        assert result is not None
        lines = result.plain.split("\n")
        assert all(len(line) <= 20 for line in lines)

    def test_odd_height_padded(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_image_halfblocks
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (4, 3), color=(0, 255, 0))
        path = tmp_path / "odd.png"
        img.save(path)
        result = render_image_halfblocks(path, max_width=10)
        assert result is not None


class TestRenderMarkdownWithImages:
    """Tests for render_markdown_with_images."""

    def test_plain_markdown_no_images(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_markdown_with_images

        parts = render_markdown_with_images("# Hello\nWorld", tmp_path)
        assert len(parts) == 1  # just one Markdown renderable

    def test_markdown_image_syntax(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_markdown_with_images
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (4, 4), color=(255, 0, 0))
        img.save(tmp_path / "pic.png")

        text = "Before\n\n![alt](pic.png)\n\nAfter"
        parts = render_markdown_with_images(text, tmp_path)
        assert len(parts) > 1  # markdown + image + markdown

    def test_html_img_tag(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_markdown_with_images
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (4, 4), color=(0, 0, 255))
        img.save(tmp_path / "logo.png")

        text = '<p><img src="logo.png" width="200"></p>\n\n# Title'
        parts = render_markdown_with_images(text, tmp_path)
        assert len(parts) > 1

    def test_missing_image_shows_placeholder(self, tmp_path: Path) -> None:
        from perch.widgets.viewer import render_markdown_with_images

        text = "![my image](missing.png)\n\nSome text"
        parts = render_markdown_with_images(text, tmp_path)
        # Should have a placeholder for the missing image
        has_placeholder = any("image:" in str(p) for p in parts)
        assert has_placeholder


class TestCheckActions:
    """Tests for dynamic footer binding visibility."""

    async def test_toggle_diff_requires_file(self, tmp_path: Path) -> None:
        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            assert viewer.check_action("toggle_diff", ()) is False
            viewer._current_path = tmp_path / "hello.py"
            assert viewer.check_action("toggle_diff", ()) is True

    async def test_diff_layout_requires_diff_mode(self, tmp_path: Path) -> None:
        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            assert viewer.check_action("toggle_diff_layout", ()) is False
            viewer._diff_mode = True
            assert viewer.check_action("toggle_diff_layout", ()) is True

    async def test_markdown_preview_requires_md_file(self, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("# hi\n")
        py = tmp_path / "test.py"
        py.write_text("x = 1\n")
        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            assert viewer.check_action("toggle_markdown_preview", ()) is False
            viewer._current_path = py
            assert viewer.check_action("toggle_markdown_preview", ()) is False
            viewer._current_path = md
            assert viewer.check_action("toggle_markdown_preview", ()) is True
            viewer._diff_mode = True
            assert viewer.check_action("toggle_markdown_preview", ()) is False


class TestMarkdownPreview:
    """Tests for the markdown preview toggle."""

    async def test_toggle_renders_markdown(self, tmp_path: Path) -> None:
        """Toggling markdown preview on a .md file should render it."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nSome **bold** text.\n")

        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            viewer = pilot.app.query_one(Viewer)
            viewer.load_file(md_file)
            await pilot.pause()
            await pilot.pause()

            # Default: raw syntax-highlighted view
            assert viewer._markdown_preview is False

            # Toggle to preview
            viewer.action_toggle_markdown_preview()
            await pilot.pause()
            assert viewer._markdown_preview is True

    async def test_toggle_back_to_raw(self, tmp_path: Path) -> None:
        """Toggling again should return to raw view."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n")

        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer.load_file(md_file)
            await pilot.pause()

            viewer.action_toggle_markdown_preview()
            viewer.action_toggle_markdown_preview()
            await pilot.pause()
            assert viewer._markdown_preview is False

    async def test_noop_on_non_markdown(self, tmp_path: Path) -> None:
        """Toggle should do nothing for non-markdown files."""
        py_file = tmp_path / "hello.py"
        py_file.write_text("print('hello')\n")

        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer.load_file(py_file)
            await pilot.pause()

            viewer.action_toggle_markdown_preview()
            await pilot.pause()
            assert viewer._markdown_preview is False

    async def test_noop_in_diff_mode(self, tmp_path: Path) -> None:
        """Toggle should do nothing when in diff mode."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n")

        app = PerchApp(tmp_path)
        async with app.run_test() as pilot:
            viewer = pilot.app.query_one(Viewer)
            viewer.load_file(md_file)
            viewer._diff_mode = True
            await pilot.pause()

            viewer.action_toggle_markdown_preview()
            await pilot.pause()
            assert viewer._markdown_preview is False

    def test_is_markdown_extensions(self) -> None:
        """All common markdown extensions should be recognized."""
        assert Viewer._is_markdown(Path("README.md"))
        assert Viewer._is_markdown(Path("notes.markdown"))
        assert Viewer._is_markdown(Path("doc.mdown"))
        assert Viewer._is_markdown(Path("file.mkd"))
        assert Viewer._is_markdown(Path("UPPER.MD"))
        assert not Viewer._is_markdown(Path("app.py"))
        assert not Viewer._is_markdown(Path("style.css"))


# ---------------------------------------------------------------------------
# Viewer.show_ci_log — CI log annotation parsing (lines 671-713)
# ---------------------------------------------------------------------------
class TestShowCiLog:
    """Covers annotation parsing in show_ci_log."""

    async def test_group_annotation(self, worktree: Path) -> None:
        """##[group]Name should render as bold cyan group header."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("##[group]Run tests\n##[endgroup]")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Run tests" in text.plain

    async def test_endgroup_annotation(self, worktree: Path) -> None:
        """##[endgroup] lines should be skipped (not rendered)."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("##[endgroup]")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "endgroup" not in text.plain

    async def test_error_annotation(self, worktree: Path) -> None:
        """##[error]msg should render the error message."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("##[error]Something broke")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Something broke" in text.plain

    async def test_warning_annotation(self, worktree: Path) -> None:
        """##[warning]msg should render the warning message."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("##[warning]Deprecation notice")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Deprecation notice" in text.plain

    async def test_ansi_stripping(self, worktree: Path) -> None:
        """ANSI escape codes should be stripped from log lines."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("\x1b[32mGreen text\x1b[0m")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Green text" in text.plain
            assert "\x1b[" not in text.plain

    async def test_timestamp_stripping(self, worktree: Path) -> None:
        """ISO timestamp prefixes should be stripped."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("2026-03-17T01:26:13.1234567Z Hello world")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Hello world" in text.plain
            assert "2026-03-17" not in text.plain

    async def test_tab_delimited_prefix_stripping(self, worktree: Path) -> None:
        """Tab-delimited job/step/timestamp prefixes should be stripped."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("myjob\tstep1\t2026-03-17T01:26:13.1234567Z Actual msg")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Actual msg" in text.plain
            assert "myjob" not in text.plain

    async def test_empty_log(self, worktree: Path) -> None:
        """Empty or whitespace-only log shows 'No log output available'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log("   ")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "No log output" in text.plain

    async def test_mixed_annotations(self, worktree: Path) -> None:
        """A log with mixed annotations and regular lines is parsed correctly."""
        log = (
            "##[group]Setup\n"
            "    Installing deps\n"
            "##[endgroup]\n"
            "##[warning]Something looks odd\n"
            "##[error]Fatal failure\n"
            "Normal line"
        )
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_ci_log(log)
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Setup" in text.plain
            assert "Installing deps" in text.plain
            assert "Something looks odd" in text.plain
            assert "Fatal failure" in text.plain
            assert "Normal line" in text.plain
            # endgroup should not appear
            assert "endgroup" not in text.plain


# ---------------------------------------------------------------------------
# Coverage: fetch_ci_log early return when worktree is None (line 727)
# ---------------------------------------------------------------------------
class TestFetchCiLogNoWorktree:
    async def test_fetch_ci_log_no_worktree_returns_early(self, worktree: Path) -> None:
        """fetch_ci_log with worktree_root=None should return immediately."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = None
            viewer.fetch_ci_log("https://example.com/log")
            # Should not crash, and should be a no-op


# ---------------------------------------------------------------------------
# Viewer.show_pr_body — empty body (lines 628-629)
# ---------------------------------------------------------------------------
class TestShowPrBody:
    async def test_empty_body_shows_no_description(self, worktree: Path) -> None:
        """show_pr_body('') should display 'No PR description'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_pr_body("")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "No PR description" in text.plain

    async def test_whitespace_body_shows_no_description(self, worktree: Path) -> None:
        """show_pr_body with only whitespace should also show 'No PR description'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_pr_body("   \n  ")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "No PR description" in text.plain

    async def test_nonempty_body_renders_markdown(self, worktree: Path) -> None:
        """show_pr_body with actual content should render markdown."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_pr_body("# Hello\n\nSome text", title="PR #42")
            await app._animator.wait_for_idle()
            # Should not show the "no description" message
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = str(content._Static__content)
            assert "No PR description" not in text


# ---------------------------------------------------------------------------
# Viewer.show_review — empty body (line 667)
# ---------------------------------------------------------------------------
class TestShowReview:
    async def test_empty_body_shows_no_review(self, worktree: Path) -> None:
        """show_review('') should display 'No review body'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_review("")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "No review body" in text.plain

    async def test_whitespace_body_shows_no_review(self, worktree: Path) -> None:
        """show_review with only whitespace should also show 'No review body'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_review("  \n  ")
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "No review body" in text.plain


# ---------------------------------------------------------------------------
# Viewer.show_empty_directory — lines 735-743
# ---------------------------------------------------------------------------
class TestShowEmptyDirectory:
    async def test_shows_no_files_message(self, worktree: Path) -> None:
        """show_empty_directory should display 'No files in this directory'."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.show_empty_directory()
            await app._animator.wait_for_idle()
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "No files in this directory" in text.plain


# ---------------------------------------------------------------------------
# Viewer._path_label — fallback when path not relative to worktree (lines 463-465)
# ---------------------------------------------------------------------------
class TestPathLabel:
    async def test_path_not_relative_to_worktree(self, worktree: Path) -> None:
        """When path is outside worktree_root, _path_label returns str(path)."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            outside_path = Path("/some/other/place/file.py")
            label = viewer._path_label(outside_path)
            assert label == str(outside_path)

    async def test_path_relative_to_worktree(self, worktree: Path) -> None:
        """When path is inside worktree_root, _path_label returns relative path."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            inside_path = worktree / "src" / "main.py"
            label = viewer._path_label(inside_path)
            assert label == "src/main.py"

    async def test_path_label_no_worktree_root(self, worktree: Path) -> None:
        """When worktree_root is None, _path_label returns str(path)."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = None
            some_path = Path("/any/file.py")
            label = viewer._path_label(some_path)
            assert label == str(some_path)


# ---------------------------------------------------------------------------
# Viewer.show_commit_summary — Task 6
# ---------------------------------------------------------------------------
class TestCommitSummaryViewer:
    async def test_show_commit_summary_sets_state(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc1234",
                subject="fix login",
                body="Detailed fix",
                author="Alice",
                date="2026-03-20T10:00:00+00:00",
                stats=" 1 file changed, 5 insertions(+)",
            )
            viewer.show_commit_summary(summary)
            assert viewer._diff_mode is False
            assert viewer._current_path is None
            assert viewer._commit_file_context is None
            assert viewer._current_summary is summary


# ---------------------------------------------------------------------------
# Viewer.load_commit_file_diff — Task 6
# ---------------------------------------------------------------------------
class TestCommitFileDiffViewer:
    async def test_load_commit_file_diff_sets_state(self, git_worktree: Path) -> None:
        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "change"], cwd=git_worktree, check=True)
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        app = PerchApp(git_worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_commit_file_diff(head, "hello.py")
            assert viewer._diff_mode is True
            assert viewer._current_path is None
            assert viewer._commit_file_context == (head, "hello.py")
            assert viewer._current_summary is None


# ---------------------------------------------------------------------------
# Viewer commit-file context integration — Task 7
# ---------------------------------------------------------------------------
class TestCommitFileDiffIntegration:
    async def test_check_action_toggle_diff_with_commit_context(
        self, git_worktree: Path
    ) -> None:
        app = PerchApp(git_worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._commit_file_context = ("abc123", "file.py")
            assert viewer.check_action("toggle_diff", ()) is True

    async def test_toggle_diff_off_shows_summary(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc",
                subject="s",
                body="",
                author="a",
                date="d",
                stats="stats",
            )
            viewer._commit_file_context = ("abc", "file.py")
            viewer._current_summary = summary
            viewer._diff_mode = True
            viewer.action_toggle_diff()
            assert viewer._diff_mode is False
            assert viewer._commit_file_context is None

    async def test_refresh_content_with_summary(self, worktree: Path) -> None:
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc",
                subject="s",
                body="",
                author="a",
                date="d",
                stats="stats",
            )
            viewer.show_commit_summary(summary)
            viewer.refresh_content()  # should not crash


# ---------------------------------------------------------------------------
# Coverage: load_commit_file_diff error paths (lines 661-664, 667-668, 670)
# ---------------------------------------------------------------------------
class TestCommitFileDiffEdgeCases:
    async def test_load_commit_file_diff_runtime_error(self, worktree: Path) -> None:
        """RuntimeError from get_commit_file_diff is caught and displayed."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            with patch(
                "perch.services.git.get_commit_file_diff",
                side_effect=RuntimeError("git failed"),
            ):
                viewer.load_commit_file_diff("abc123", "file.py")
            assert viewer._diff_mode is True
            assert viewer._commit_file_context == ("abc123", "file.py")

    async def test_load_commit_file_diff_empty(self, worktree: Path) -> None:
        """Empty diff text shows 'No changes' message."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            with patch(
                "perch.services.git.get_commit_file_diff",
                return_value="",
            ):
                viewer.load_commit_file_diff("abc123", "file.py")

    async def test_load_commit_file_diff_side_by_side(self, worktree: Path) -> None:
        """Side-by-side layout for commit file diff."""
        diff_text = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new"
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            viewer._diff_layout = "side-by-side"
            with patch(
                "perch.services.git.get_commit_file_diff",
                return_value=diff_text,
            ):
                viewer.load_commit_file_diff("abc123", "file.py")

    async def test_load_commit_file_diff_no_worktree(self, worktree: Path) -> None:
        """load_commit_file_diff returns early when worktree_root is None."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = None
            viewer.load_commit_file_diff("abc123", "file.py")
            # Should be a no-op (no state change)
            assert viewer._commit_file_context is None


# ---------------------------------------------------------------------------
# Coverage: _load_diff with commit-file context (lines 832-835)
# ---------------------------------------------------------------------------
class TestLoadDiffCommitFileContext:
    async def test_load_diff_delegates_to_commit_file_diff(
        self, worktree: Path
    ) -> None:
        """_load_diff with _commit_file_context delegates to load_commit_file_diff."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            viewer._commit_file_context = ("abc123", "file.py")
            with patch(
                "perch.services.git.get_commit_file_diff",
                return_value="--- a/f.py\n+++ b/f.py\n",
            ):
                viewer._load_diff()
            assert viewer._diff_mode is True


# ---------------------------------------------------------------------------
# Coverage: refresh_content with commit-file context (lines 816-817)
# ---------------------------------------------------------------------------
class TestRefreshContentCommitFile:
    async def test_refresh_content_with_commit_file_context(
        self, worktree: Path
    ) -> None:
        """refresh_content re-loads commit file diff when context is set."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            viewer._commit_file_context = ("abc123", "file.py")
            with patch(
                "perch.services.git.get_commit_file_diff",
                return_value="--- a/f.py\n+++ b/f.py\n",
            ):
                viewer.refresh_content()
            assert viewer._diff_mode is True

    async def test_refresh_content_with_diff_mode(self, worktree: Path) -> None:
        """refresh_content re-loads diff when in diff mode."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.worktree_root = worktree
            viewer._current_path = worktree / "hello.py"
            viewer._diff_mode = True
            with patch("perch.services.git.get_diff", return_value=""):
                viewer.refresh_content()


# ---------------------------------------------------------------------------
# Coverage: _refresh_footer exception path (lines 447-448)
# ---------------------------------------------------------------------------
class TestRefreshFooterException:
    async def test_refresh_footer_swallows_exception(self, worktree: Path) -> None:
        """_refresh_footer catches exceptions from screen.refresh_bindings."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            with patch.object(
                viewer.screen,
                "refresh_bindings",
                side_effect=AttributeError("no screen"),
            ):
                viewer._refresh_footer()  # should not raise


# ---------------------------------------------------------------------------
# Coverage: _extract_diff_filename fallback (line 204)
# ---------------------------------------------------------------------------
class TestExtractDiffFilenameFallback:
    def test_no_b_slash_returns_whole_line(self) -> None:
        """When no ' b/' is found, _extract_diff_filename returns the line."""
        from perch.widgets.viewer import _extract_diff_filename

        line = "diff --git some/weird/format"
        assert _extract_diff_filename(line) == line


# ---------------------------------------------------------------------------
# Coverage: render_diff with multiple files (line 237 — file_index > 0)
# ---------------------------------------------------------------------------
class TestRenderDiffMultipleFiles:
    def test_multiple_file_boundaries(self) -> None:
        """render_diff adds extra newline between multiple files."""
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/bar.py b/bar.py\n"
            "--- a/bar.py\n"
            "+++ b/bar.py\n"
            "@@ -1 +1 @@\n"
            "-old2\n"
            "+new2"
        )
        result = render_diff(diff, dark=True)
        assert "foo.py" in result.plain
        assert "bar.py" in result.plain


# ---------------------------------------------------------------------------
# Coverage: _strip_html_for_markdown heading replacement (lines 96-98)
# ---------------------------------------------------------------------------
class TestStripHtmlHeadings:
    def test_html_heading_to_markdown(self) -> None:
        """<h1>...</h1> through <h6>...</h6> should be converted."""
        from perch.widgets.viewer import _strip_html_for_markdown

        assert _strip_html_for_markdown("<h1>Title</h1>") == "# Title"
        assert _strip_html_for_markdown("<h2>Sub</h2>") == "## Sub"
        assert _strip_html_for_markdown("<h3>Deep</h3>") == "### Deep"


# ---------------------------------------------------------------------------
# Coverage: markdown preview with multiple parts (line 568)
# ---------------------------------------------------------------------------
class TestMarkdownPreviewMultipleParts:
    async def test_markdown_with_image_renders_group(self, tmp_path: Path) -> None:
        """Markdown with an image reference should render as Group."""
        from PIL import Image as PILImage

        md_file = tmp_path / "test.md"
        img = PILImage.new("RGB", (4, 4), color=(255, 0, 0))
        img.save(tmp_path / "pic.png")
        md_file.write_text("Before\n\n![alt](pic.png)\n\nAfter")

        app = PerchApp(tmp_path)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._markdown_preview = True
            viewer.load_file(md_file)


# ---------------------------------------------------------------------------
# Coverage: CI log group with pre-existing content (line 757)
# ---------------------------------------------------------------------------
class TestCiLogGroupNewline:
    async def test_group_after_content_adds_newline(self, worktree: Path) -> None:
        """A ##[group] that comes after earlier output should add a leading newline."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            log = "Normal line\n##[group]Setup"
            viewer.show_ci_log(log)
            from textual.widgets import Static

            content = viewer.query_one("#file-content", Static)
            text = content._Static__content
            assert "Setup" in text.plain
            assert "Normal line" in text.plain
