"""Tests for the FileViewer widget's helper functions."""

from pathlib import Path

from perch.widgets.file_viewer import (
    BINARY_CHECK_SIZE,
    MAX_LINES,
    is_binary,
    parse_diff_sides,
    read_file_content,
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
        assert left == " context line"
        assert right == " context line"

    def test_removed_lines_go_to_left_only(self) -> None:
        diff = "-removed line"
        left, right = parse_diff_sides(diff)
        assert left == "-removed line"
        assert right == ""

    def test_added_lines_go_to_right_only(self) -> None:
        diff = "+added line"
        left, right = parse_diff_sides(diff)
        assert left == ""
        assert right == "+added line"

    def test_file_headers_split_correctly(self) -> None:
        diff = "--- a/foo.py\n+++ b/foo.py"
        left, right = parse_diff_sides(diff)
        assert left == "--- a/foo.py\n"
        assert right == "\n+++ b/foo.py"

    def test_hunk_headers_appear_on_both_sides(self) -> None:
        diff = "@@ -1,3 +1,4 @@"
        left, right = parse_diff_sides(diff)
        assert left == "@@ -1,3 +1,4 @@"
        assert right == "@@ -1,3 +1,4 @@"

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
        assert left.count("\n") == right.count("\n")

    def test_empty_diff(self) -> None:
        left, right = parse_diff_sides("")
        assert left == ""
        assert right == ""

    def test_multiple_removals_and_additions(self) -> None:
        diff = "-a\n-b\n+x\n+y\n+z"
        left, right = parse_diff_sides(diff)
        left_lines = left.split("\n")
        right_lines = right.split("\n")
        assert len(left_lines) == len(right_lines)
        assert left_lines[0] == "-a"
        assert left_lines[1] == "-b"
        assert right_lines[2] == "+x"
        assert right_lines[3] == "+y"
        assert right_lines[4] == "+z"
