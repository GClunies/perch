"""Tests for fuzzy file search modal."""

from pathlib import Path

from perch.widgets.file_search import collect_files, fuzzy_score


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
