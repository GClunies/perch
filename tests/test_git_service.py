import subprocess
from pathlib import Path
from unittest.mock import patch

from perch.models import Commit, CommitFile, CommitSummary, GitFile, GitStatusData
from perch.services.git import (
    get_commit_diff,
    get_current_branch,
    get_diff,
    get_ignored_paths,
    get_log,
    get_status_dict,
    parse_log,
    parse_status,
)


class TestParseStatus:
    def test_empty(self) -> None:
        assert parse_status("") == GitStatusData()

    def test_untracked_files(self) -> None:
        raw = "?? new_file.py\n?? docs/readme.md\n"
        result = parse_status(raw)
        assert result.untracked == [
            GitFile(path="new_file.py", status="untracked", staged=False),
            GitFile(path="docs/readme.md", status="untracked", staged=False),
        ]
        assert result.staged == []
        assert result.unstaged == []

    def test_staged_modified(self) -> None:
        raw = "M  src/app.py\n"
        result = parse_status(raw)
        assert result.staged == [
            GitFile(path="src/app.py", status="modified", staged=True),
        ]
        assert result.unstaged == []

    def test_unstaged_modified(self) -> None:
        raw = " M src/app.py\n"
        result = parse_status(raw)
        assert result.unstaged == [
            GitFile(path="src/app.py", status="modified", staged=False),
        ]
        assert result.staged == []

    def test_both_staged_and_unstaged(self) -> None:
        # File is modified in index AND has further unstaged modifications
        raw = "MM src/app.py\n"
        result = parse_status(raw)
        assert result.staged == [
            GitFile(path="src/app.py", status="modified", staged=True),
        ]
        assert result.unstaged == [
            GitFile(path="src/app.py", status="modified", staged=False),
        ]

    def test_staged_added(self) -> None:
        raw = "A  new_file.py\n"
        result = parse_status(raw)
        assert result.staged == [
            GitFile(path="new_file.py", status="added", staged=True),
        ]

    def test_staged_deleted(self) -> None:
        raw = "D  old_file.py\n"
        result = parse_status(raw)
        assert result.staged == [
            GitFile(path="old_file.py", status="deleted", staged=True),
        ]

    def test_staged_renamed(self) -> None:
        raw = "R  old.py -> new.py\n"
        result = parse_status(raw)
        assert result.staged == [
            GitFile(path="old.py -> new.py", status="renamed", staged=True),
        ]

    def test_mixed_statuses(self) -> None:
        raw = (
            "M  staged.py\n"
            " M unstaged.py\n"
            "?? untracked.py\n"
            "A  added.py\n"
            "D  deleted.py\n"
        )
        result = parse_status(raw)
        assert len(result.staged) == 3  # M, A, D
        assert len(result.unstaged) == 1
        assert len(result.untracked) == 1

    def test_short_lines_ignored(self) -> None:
        raw = "X\nAB\n?? ok.py\n"
        result = parse_status(raw)
        assert len(result.untracked) == 1


class TestParseLog:
    def test_empty(self) -> None:
        assert parse_log("") == []

    def test_single_commit(self) -> None:
        raw = "abc1234\x1fFix the bug\x1fAlice\x1f2 hours ago\n"
        result = parse_log(raw)
        assert result == [
            Commit(
                hash="abc1234",
                message="Fix the bug",
                author="Alice",
                relative_time="2 hours ago",
            ),
        ]

    def test_multiple_commits(self) -> None:
        raw = (
            "abc1234\x1fFirst commit\x1fAlice\x1f3 days ago\n"
            "def5678\x1fSecond commit\x1fBob\x1f1 day ago\n"
        )
        result = parse_log(raw)
        assert len(result) == 2
        assert result[0].hash == "abc1234"
        assert result[1].author == "Bob"

    def test_malformed_lines_skipped(self) -> None:
        raw = (
            "abc1234\x1fGood commit\x1fAlice\x1f1 hour ago\n"
            "bad line with no separators\n"
            "def5678\x1fAnother good one\x1fBob\x1f2 hours ago\n"
        )
        result = parse_log(raw)
        assert len(result) == 2


class TestGetDiff:
    """Tests for get_diff() using a real temp git repo."""

    def _make_repo(self, tmp_path: Path) -> Path:
        """Create a minimal git repo and return its root."""
        import subprocess

        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        # Initial commit so HEAD exists
        (root / "README.md").write_text("initial\n")
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        return root

    def test_modified_file_diff(self, tmp_path: Path) -> None:
        root = self._make_repo(tmp_path)
        (root / "README.md").write_text("changed\n")
        result = get_diff(root, "README.md")
        assert "-initial" in result
        assert "+changed" in result

    def test_staged_file_diff(self, tmp_path: Path) -> None:
        import subprocess

        root = self._make_repo(tmp_path)
        (root / "README.md").write_text("staged change\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=root, capture_output=True, check=True
        )
        result = get_diff(root, "README.md", staged=True)
        assert "-initial" in result
        assert "+staged change" in result

    def test_empty_diff_clean_file(self, tmp_path: Path) -> None:
        root = self._make_repo(tmp_path)
        result = get_diff(root, "README.md")
        assert result == ""


class TestGetStatusDict:
    """Tests for get_status_dict() using a real temp git repo."""

    def _make_repo(self, tmp_path: Path) -> Path:
        """Create a minimal git repo and return its root."""
        import subprocess

        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        (root / "README.md").write_text("initial\n")
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        return root

    def test_mixed_statuses(self, tmp_path: Path) -> None:
        import subprocess

        root = self._make_repo(tmp_path)
        # Modified (unstaged)
        (root / "README.md").write_text("modified\n")
        # Added + staged
        (root / "new.py").write_text("new\n")
        subprocess.run(
            ["git", "add", "new.py"], cwd=root, capture_output=True, check=True
        )
        # Untracked
        (root / "untracked.txt").write_text("untracked\n")

        result = get_status_dict(root)
        assert result["README.md"] == "modified"
        assert result["new.py"] == "added"
        assert result["untracked.txt"] == "untracked"

    def test_empty_status(self, tmp_path: Path) -> None:
        root = self._make_repo(tmp_path)
        result = get_status_dict(root)
        assert result == {}


class TestGetIgnoredPaths:
    """Tests for get_ignored_paths edge cases."""

    def test_path_not_under_root_falls_back_to_str(self, tmp_path: Path) -> None:
        """When a path is not relative to root, relative_to raises ValueError
        and the code falls back to str(p). Verify no crash and result is valid."""
        root = tmp_path / "repo"
        root.mkdir()
        # Initialize a git repo so git check-ignore works
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)

        # Path completely outside root
        outside_path = Path("/some/other/location/file.txt")
        result = get_ignored_paths(root, [outside_path])
        # The outside path won't be gitignored, so result should be empty
        assert isinstance(result, set)
        assert outside_path not in result

    def test_gitignored_directory_found(self, tmp_path: Path) -> None:
        """Verify that gitignored directories are correctly identified via
        the trailing-slash key in path_map."""
        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)

        # Create .gitignore that ignores a directory
        (root / ".gitignore").write_text("build/\n")
        build_dir = root / "build"
        build_dir.mkdir()

        result = get_ignored_paths(root, [build_dir])
        assert build_dir in result

    def test_empty_paths_returns_empty_set(self) -> None:
        result = get_ignored_paths(Path("/tmp"), [])
        assert result == set()


class TestGetCurrentBranch:
    """Tests for get_current_branch error path."""

    @patch("perch.services.git._run_git")
    def test_raises_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(  # type: ignore[attr-defined]
            args=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        import pytest

        with pytest.raises(RuntimeError, match="Failed to get branch"):
            get_current_branch(Path("/tmp"))


class TestGetCommitDiff:
    """Tests for get_commit_diff error path."""

    @patch("perch.services.git._run_git")
    def test_raises_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(  # type: ignore[attr-defined]
            args=["git", "show"],
            returncode=128,
            stdout="",
            stderr="fatal: bad object abc123",
        )
        import pytest

        with pytest.raises(RuntimeError, match="git show failed"):
            get_commit_diff(Path("/tmp"), "abc123")


class TestGetLog:
    """Tests for get_log error path."""

    @patch("perch.services.git._run_git")
    def test_returns_empty_list_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(  # type: ignore[attr-defined]
            args=["git", "log"],
            returncode=128,
            stdout="",
            stderr="fatal: bad default revision 'HEAD'",
        )
        result = get_log(Path("/tmp"))
        assert result == []


class TestGetLogPagination:
    def test_skip_parameter(self, git_worktree: Path) -> None:
        from perch.services.git import get_log
        for i in range(3):
            (git_worktree / f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(["git", "commit", "-m", f"commit {i}"], cwd=git_worktree, check=True)
        all_commits = get_log(git_worktree, n=10)
        skipped = get_log(git_worktree, n=10, skip=1)
        assert len(all_commits) == 4  # 3 new + 1 initial
        assert len(skipped) == 3
        assert skipped[0].hash == all_commits[1].hash

    def test_skip_past_end(self, git_worktree: Path) -> None:
        from perch.services.git import get_log
        result = get_log(git_worktree, n=10, skip=999)
        assert result == []


class TestGetCommitFiles:
    def test_returns_modified_files(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_files
        (git_worktree / "hello.py").write_text("modified content\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify hello"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        files = get_commit_files(git_worktree, head)
        assert len(files) == 1
        assert files[0].path == "hello.py"
        assert files[0].status == "modified"
        assert files[0].old_path is None

    def test_added_file(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_files
        (git_worktree / "new.py").write_text("new file\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "add new"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        files = get_commit_files(git_worktree, head)
        assert any(f.path == "new.py" and f.status == "added" for f in files)

    def test_deleted_file(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_files
        subprocess.run(["git", "rm", "hello.py"], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "delete hello"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        files = get_commit_files(git_worktree, head)
        assert any(f.path == "hello.py" and f.status == "deleted" for f in files)


class TestGetCommitFileDiff:
    def test_returns_diff_for_file(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_file_diff
        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify hello"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        diff = get_commit_file_diff(git_worktree, head, "hello.py")
        assert "diff --git" in diff
        assert "hello.py" in diff

    def test_no_commit_metadata_in_output(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_file_diff
        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "test commit message"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        diff = get_commit_file_diff(git_worktree, head, "hello.py")
        assert "test commit message" not in diff


class TestGetCommitSummary:
    def test_returns_summary(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_summary
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        summary = get_commit_summary(git_worktree, head)
        assert summary.hash == head
        assert summary.author == "test"
        assert summary.subject
        assert summary.date

    def test_stats_contain_file_info(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_summary
        (git_worktree / "stats_test.py").write_text("content\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "add stats_test"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        summary = get_commit_summary(git_worktree, head)
        assert "stats_test.py" in summary.stats

    def test_body_with_unit_separator(self, git_worktree: Path) -> None:
        from perch.services.git import get_commit_summary
        (git_worktree / "sep.txt").write_text("x\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "subject\n\nbody with \x1f separator"], cwd=git_worktree, check=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_worktree, capture_output=True, text=True, check=True).stdout.strip()
        summary = get_commit_summary(git_worktree, head)
        assert "\x1f" in summary.body


class TestCommitFileModel:
    def test_basic_fields(self) -> None:
        cf = CommitFile(path="src/app.py", status="modified", old_path=None)
        assert cf.path == "src/app.py"
        assert cf.status == "modified"
        assert cf.old_path is None

    def test_renamed_file(self) -> None:
        cf = CommitFile(path="new.py", status="renamed", old_path="old.py")
        assert cf.old_path == "old.py"

    def test_old_path_defaults_none(self) -> None:
        cf = CommitFile(path="file.py", status="added")
        assert cf.old_path is None


class TestCommitSummaryModel:
    def test_basic_fields(self) -> None:
        cs = CommitSummary(
            hash="abc1234",
            subject="fix login",
            body="Detailed description",
            author="Alice",
            date="2026-03-20T10:00:00+00:00",
            stats=" 2 files changed, 10 insertions(+), 3 deletions(-)",
        )
        assert cs.hash == "abc1234"
        assert cs.subject == "fix login"
        assert cs.body == "Detailed description"
