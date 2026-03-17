"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


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
