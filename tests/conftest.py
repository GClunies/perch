import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_worktree(tmp_path: Path) -> Path:
    """Create a worktree that is a real git repo with a commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    (tmp_path / "hello.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    return tmp_path
