"""Tests for the CLI entry point."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )


class TestCLIEntryPoint:
    """Tests for the main() CLI function."""

    def test_default_path_is_current_dir(self) -> None:
        """With no arguments, path should default to '.' resolved."""
        with patch("sys.argv", ["perch"]), patch("perch.app.PerchApp") as MockApp:
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance

            from perch.cli import main

            main()

            MockApp.assert_called_once_with(
                worktree_path=Path(".").resolve(), editor=None
            )
            mock_instance.run.assert_called_once()

    def test_explicit_path(self, tmp_path: Path) -> None:
        """An explicit path argument should be resolved and passed to PerchApp."""
        _init_git_repo(tmp_path)
        with (
            patch("sys.argv", ["perch", str(tmp_path)]),
            patch("perch.app.PerchApp") as MockApp,
        ):
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance

            from perch.cli import main

            main()

            MockApp.assert_called_once_with(
                worktree_path=tmp_path.resolve(), editor=None
            )
            mock_instance.run.assert_called_once()

    def test_editor_option(self, tmp_path: Path) -> None:
        """--editor should be passed to PerchApp."""
        _init_git_repo(tmp_path)
        with (
            patch("sys.argv", ["perch", str(tmp_path), "--editor", "vim"]),
            patch("perch.app.PerchApp") as MockApp,
        ):
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance

            from perch.cli import main

            main()

            MockApp.assert_called_once_with(
                worktree_path=tmp_path.resolve(), editor="vim"
            )
            mock_instance.run.assert_called_once()

    def test_editor_defaults_to_none(self) -> None:
        """Without --editor, editor should be None."""
        with patch("sys.argv", ["perch"]), patch("perch.app.PerchApp") as MockApp:
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance

            from perch.cli import main

            main()

            call_kwargs = MockApp.call_args
            assert call_kwargs.kwargs["editor"] is None

    def test_non_git_repo_exits(self, tmp_path: Path) -> None:
        """Running perch in a non-git directory should exit with an error."""
        with patch("sys.argv", ["perch", str(tmp_path)]):
            from perch.cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--version should print the version and exit cleanly."""
        from perch import __version__
        from perch.cli import main

        with patch("sys.argv", ["perch", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_main_module_entry_point(self) -> None:
        """__main__.py should call main()."""
        with patch("perch.cli.main") as mock_main:
            import importlib

            import perch.__main__  # noqa: F401

            importlib.reload(importlib.import_module("perch.__main__"))
            mock_main.assert_called()
