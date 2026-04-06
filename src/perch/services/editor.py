"""Editor integration — resolve and launch an external editor."""

from __future__ import annotations

import os
import shlex
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


def open_file(
    editor: str | None, file_path: Path, worktree_root: Path | None = None
) -> None:
    """Open *file_path* in *editor* (non-blocking).

    When *worktree_root* is given the editor receives the repo root as its
    first argument so that editors like VS Code / Cursor open the project
    folder with the file selected.  Language servers and project-level
    configuration (e.g. ``pyproject.toml``) are then discovered correctly.
    """
    cmd = resolve_editor(editor)
    args = [*shlex.split(cmd)]
    if worktree_root is not None:
        args.append(str(worktree_root))
    args.append(str(file_path))
    subprocess.Popen(args, start_new_session=True)
