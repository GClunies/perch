import subprocess
from pathlib import Path

from perch.widgets.file_tree import ALWAYS_EXCLUDED, FileTree


def _init_git_repo_with_commit(path: Path) -> None:
    """Create a git repo with an initial commit so PerchApp can resolve a branch."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(path),
        },
    )


def _init_git_repo(path: Path, gitignore: str = "") -> None:
    """Create a git repo with an optional .gitignore."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    if gitignore:
        (path / ".gitignore").write_text(gitignore)


class TestFilterPaths:
    """Tests for FileTree.filter_paths()."""

    def test_always_excludes_git_directory(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / ".git", tmp_path / "src"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert ".git" in ALWAYS_EXCLUDED
        assert ".git" not in result
        assert "src" in result

    def test_shows_gitignored_files(self, tmp_path: Path) -> None:
        """Gitignored files should appear but be tracked as ignored."""
        _init_git_repo(tmp_path, gitignore="__pycache__/\n.venv/\n")
        tree = FileTree(str(tmp_path))
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
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / "src", tmp_path / "tests", tmp_path / "pyproject.toml"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert result == ["src", "tests", "pyproject.toml"]

    def test_empty_input(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert list(tree.filter_paths([])) == []

    def test_graceful_without_git_repo(self, tmp_path: Path) -> None:
        """Without a git repo, all files except .git are shown."""
        tree = FileTree(str(tmp_path))
        paths = [tmp_path / ".git", tmp_path / "src", tmp_path / "__pycache__"]
        result = [p.name for p in tree.filter_paths(paths)]
        assert ".git" not in result
        assert "src" in result
        assert "__pycache__" in result


class TestIsDimmed:
    """Tests for _is_dimmed() — dotfiles and gitignored paths."""

    def test_dotfile_is_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / ".env") is True

    def test_dotdir_is_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / ".venv") is True

    def test_normal_file_not_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        assert tree._is_dimmed(tmp_path / "main.py") is False

    def test_ignored_path_is_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        tree._ignored_paths.add(tmp_path / "node_modules")
        assert tree._is_dimmed(tmp_path / "node_modules") is True

    def test_non_ignored_path_not_dimmed(self, tmp_path: Path) -> None:
        tree = FileTree(str(tmp_path))
        tree._ignored_paths.add(tmp_path / "dist")
        assert tree._is_dimmed(tmp_path / "src") is False


class TestRootNodeProtection:
    """The root node must never be collapsible."""

    async def test_action_collapse_node_does_not_collapse_root(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp

        _init_git_repo_with_commit(tmp_path)
        with (
            patch("perch.services.git.get_status", return_value=__import__("perch.models", fromlist=["GitStatusData"]).GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                await pilot.pause()
                # Ensure root is expanded
                assert tree.root.is_expanded
                # Position cursor on root
                tree.cursor_line = 0
                tree.action_collapse_node()
                await pilot.pause()
                assert tree.root.is_expanded, "Root should never be collapsed"

    async def test_on_tree_node_collapsed_reexpands_root(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import patch

        from perch.app import PerchApp

        _init_git_repo_with_commit(tmp_path)
        with (
            patch("perch.services.git.get_status", return_value=__import__("perch.models", fromlist=["GitStatusData"]).GitStatusData()),
            patch("perch.services.git.get_log", return_value=[]),
            patch("perch.services.github.get_pr_context", return_value=None),
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                tree = pilot.app.query_one(FileTree)
                await pilot.pause()
                assert tree.root.is_expanded
                # Force-collapse root directly (simulates a click on the toggle)
                tree.root.collapse()
                await pilot.pause()
                assert tree.root.is_expanded, "Root should be re-expanded automatically"
