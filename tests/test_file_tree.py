from pathlib import Path

from perch.widgets.file_tree import EXCLUDED_NAMES, WorktreeFileTree


class TestFilterPaths:
    """Tests for WorktreeFileTree.filter_paths()."""

    def _filter(self, names: list[str]) -> list[str]:
        tree = WorktreeFileTree("/tmp")
        paths = [Path(name) for name in names]
        return [p.name for p in tree.filter_paths(paths)]

    def test_excludes_git_directory(self) -> None:
        assert ".git" not in self._filter([".git", "src"])

    def test_excludes_pycache(self) -> None:
        assert "__pycache__" not in self._filter(["__pycache__", "main.py"])

    def test_excludes_ds_store(self) -> None:
        assert ".DS_Store" not in self._filter([".DS_Store", "readme.md"])

    def test_excludes_node_modules(self) -> None:
        assert "node_modules" not in self._filter(["node_modules", "src"])

    def test_excludes_ruff_cache(self) -> None:
        assert ".ruff_cache" not in self._filter([".ruff_cache", "src"])

    def test_excludes_egg_info(self) -> None:
        result = self._filter(["perch.egg-info", "src"])
        assert "perch.egg-info" not in result
        assert "src" in result

    def test_keeps_normal_files(self) -> None:
        result = self._filter(["src", "tests", "pyproject.toml", "README.md"])
        assert result == ["src", "tests", "pyproject.toml", "README.md"]

    def test_empty_input(self) -> None:
        assert self._filter([]) == []

    def test_all_excluded(self) -> None:
        result = self._filter(list(EXCLUDED_NAMES))
        assert result == []

    def test_mixed_input(self) -> None:
        names = [".git", "src", "__pycache__", "main.py", "node_modules", ".DS_Store"]
        result = self._filter(names)
        assert result == ["src", "main.py"]
