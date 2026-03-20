"""Editor integration — resolve and launch an external editor."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_editor(cli_editor: str | None) -> str:
    """Resolve the editor command.

    Priority: CLI flag → $EDITOR env var.
    """
    if cli_editor:
        return cli_editor
    editor = os.environ.get("EDITOR")
    if not editor:
        raise RuntimeError("No editor configured. Set $EDITOR or pass --editor.")
    return editor


def open_file(editor: str | None, file_path: Path, worktree_root: Path) -> None:
    """Open *file_path* in *editor* (non-blocking).

    Launches the editor with the worktree root as the first argument and
    the file path as the second so that editors like VS Code / Cursor open
    the project folder with the file selected.
    """
    cmd = resolve_editor(editor)
    subprocess.Popen(
        [cmd, str(worktree_root), str(file_path)],
        start_new_session=True,
    )
