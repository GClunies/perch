"""Tests for the FileViewer widget's helper functions."""

from pathlib import Path

from perch.widgets.file_viewer import (
    BINARY_CHECK_SIZE,
    MAX_LINES,
    is_binary,
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
