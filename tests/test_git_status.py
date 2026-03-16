"""Tests for GitStatusPanel widget and helpers."""

from perch.models import GitFile
from perch.widgets.git_status import _render_file_list


class TestRenderFileList:
    """Tests for _render_file_list helper."""

    def test_empty_list(self) -> None:
        result = _render_file_list([])
        assert result.plain == ""

    def test_single_modified_file(self) -> None:
        files = [GitFile(path="src/app.py", status="modified", staged=False)]
        result = _render_file_list(files)
        assert "modified" in result.plain
        assert "src/app.py" in result.plain

    def test_multiple_files(self) -> None:
        files = [
            GitFile(path="a.py", status="modified", staged=False),
            GitFile(path="b.py", status="deleted", staged=False),
        ]
        result = _render_file_list(files)
        assert "a.py" in result.plain
        assert "b.py" in result.plain
        assert "modified" in result.plain
        assert "deleted" in result.plain

    def test_untracked_file(self) -> None:
        files = [GitFile(path="new.txt", status="untracked", staged=False)]
        result = _render_file_list(files)
        assert "untracked" in result.plain
        assert "new.txt" in result.plain

    def test_files_separated_by_newlines(self) -> None:
        files = [
            GitFile(path="a.py", status="added", staged=True),
            GitFile(path="b.py", status="added", staged=True),
        ]
        result = _render_file_list(files)
        lines = result.plain.strip().split("\n")
        assert len(lines) == 2

    def test_all_status_types_render(self) -> None:
        statuses = ["modified", "added", "deleted", "renamed", "copied", "unmerged", "type-changed", "untracked"]
        files = [GitFile(path=f"{s}.py", status=s, staged=False) for s in statuses]
        result = _render_file_list(files)
        for s in statuses:
            assert s in result.plain
