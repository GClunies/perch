import subprocess
from pathlib import Path

from perch.widgets.file_tree import ALWAYS_EXCLUDED, WorktreeFileTree


def _init_git_repo(path: Path, gitignore: str = "") -> None:
    """Create a git repo with an optional .gitignore."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    if gitignore:
        (path / ".gitignore").write_text(gitignore)


class TestFilterPaths:
    """Tests for WorktreeFileTree.filter_paths()."""

    def test_always_excludes_git_directory(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        paths = [tmp_path / ".git", tmp_path / "src"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert ".git" in ALWAYS_EXCLUDED
        assert ".git" not in result
        assert "src" in result

    def test_shows_gitignored_files(self, tmp_path: Path) -> None:
        """Gitignored files should appear but be tracked as ignored."""
        _init_git_repo(tmp_path, gitignore="__pycache__/\n.venv/\n")
        tree = WorktreeFileTree(str(tmp_path))
        paths = [tmp_path / "__pycache__", tmp_path / ".venv", tmp_path / "src"]
        result = [p.name for p in tree.filter_paths(paths)]
        # All shown — nothing filtered out (except .git)
        assert "__pycache__" in result
        assert ".venv" in result
        assert "src" in result
        # But ignored paths are tracked
        assert tmp_path / "__pycache__" in tree._ignored_paths
        assert tmp_path / ".venv" in tree._ignored_paths
        assert tmp_path / "src" not in tree._ignored_paths

    def test_keeps_normal_files(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        tree = WorktreeFileTree(str(tmp_path))
        paths = [tmp_path / "src", tmp_path / "tests", tmp_path / "pyproject.toml"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert result == ["src", "tests", "pyproject.toml"]

    def test_empty_input(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        assert list(tree.filter_paths([])) == []

    def test_graceful_without_git_repo(self, tmp_path: Path) -> None:
        """Without a git repo, all files except .git are shown."""
        tree = WorktreeFileTree(str(tmp_path))
        paths = [tmp_path / ".git", tmp_path / "src", tmp_path / "__pycache__"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert ".git" not in result
        assert "src" in result
        assert "__pycache__" in result


class TestIsDimmed:
    """Tests for _is_dimmed() — dotfiles and gitignored paths."""

    def test_dotfile_is_dimmed(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / ".env") is True

    def test_dotdir_is_dimmed(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / ".venv") is True

    def test_normal_file_not_dimmed(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / "main.py") is False

    def test_ignored_path_is_dimmed(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        tree._ignored_paths.add(tmp_path / "node_modules")
        assert tree._is_dimmed(tmp_path / "node_modules") is True

    def test_non_ignored_path_not_dimmed(self, tmp_path: Path) -> None:
        tree = WorktreeFileTree(str(tmp_path))
        tree._ignored_paths.add(tmp_path / "dist")
        assert tree._is_dimmed(tmp_path / "src") is False
