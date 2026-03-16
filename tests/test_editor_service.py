"""Tests for the editor service."""

from pathlib import Path
from unittest.mock import patch

from perch.services.editor import DEFAULT_EDITOR, open_file, resolve_editor


class TestResolveEditor:
    def test_cli_flag_takes_priority(self):
        with patch.dict("os.environ", {"EDITOR": "vim"}):
            assert resolve_editor("code") == "code"

    def test_env_var_used_when_no_cli_flag(self):
        with patch.dict("os.environ", {"EDITOR": "nvim"}):
            assert resolve_editor(None) == "nvim"

    def test_default_when_nothing_set(self):
        with patch.dict("os.environ", {}, clear=True):
            assert resolve_editor(None) == DEFAULT_EDITOR

    def test_empty_string_cli_flag_falls_through(self):
        with patch.dict("os.environ", {"EDITOR": "vim"}):
            assert resolve_editor("") == "vim"

    def test_empty_env_var_falls_to_default(self):
        with patch.dict("os.environ", {"EDITOR": ""}):
            assert resolve_editor(None) == DEFAULT_EDITOR


class TestOpenFile:
    @patch("perch.services.editor.subprocess.Popen")
    def test_opens_editor_with_root_and_file(self, mock_popen):
        root = Path("/project")
        fp = Path("/project/src/main.py")
        open_file("code", fp, root)
        mock_popen.assert_called_once_with(
            ["code", str(root), str(fp)],
            start_new_session=True,
        )

    @patch("perch.services.editor.subprocess.Popen")
    def test_resolves_editor_when_none(self, mock_popen):
        with patch.dict("os.environ", {"EDITOR": "vim"}):
            open_file(None, Path("/a/b.py"), Path("/a"))
        assert mock_popen.call_args[0][0][0] == "vim"
