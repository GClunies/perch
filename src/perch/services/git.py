from __future__ import annotations

import subprocess
from pathlib import Path

from perch.models import Commit, GitFile, GitStatusData

# Porcelain v1 status codes and their human-readable labels
_STATUS_LABELS: dict[str, str] = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "U": "unmerged",
    "T": "type-changed",
}


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def get_worktree_root(path: Path) -> Path:
    """Return the git worktree root for *path*, or raise if not in a repo."""
    result = _run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode != 0:
        raise RuntimeError(f"Not a git repository: {path}")
    return Path(result.stdout.strip())


def get_current_branch(root: Path) -> str:
    """Return the current branch name, or 'HEAD' if detached."""
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get branch: {result.stderr.strip()}")
    return result.stdout.strip()


def get_status(root: Path) -> GitStatusData:
    """Parse ``git status --porcelain=v1`` into categorized file lists."""
    result = _run_git(["status", "--porcelain=v1"], cwd=root)
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip()}")
    return parse_status(result.stdout)


def parse_status(raw: str) -> GitStatusData:
    """Parse raw porcelain v1 output into a ``GitStatusData``."""
    staged: list[GitFile] = []
    unstaged: list[GitFile] = []
    untracked: list[GitFile] = []

    for line in raw.splitlines():
        if len(line) < 4:  # minimum: "XY path"
            continue

        index_code = line[0]
        worktree_code = line[1]
        filepath = line[3:]

        # Untracked
        if index_code == "?" and worktree_code == "?":
            untracked.append(GitFile(path=filepath, status="untracked", staged=False))
            continue

        # Staged changes (index column is not ' ' or '?')
        if index_code not in (" ", "?"):
            label = _STATUS_LABELS.get(index_code, index_code)
            staged.append(GitFile(path=filepath, status=label, staged=True))

        # Unstaged changes (worktree column is not ' ' or '?')
        if worktree_code not in (" ", "?"):
            label = _STATUS_LABELS.get(worktree_code, worktree_code)
            unstaged.append(GitFile(path=filepath, status=label, staged=False))

    return GitStatusData(unstaged=unstaged, staged=staged, untracked=untracked)


_LOG_SEP = "\x1f"  # unit separator — unlikely in commit data
_LOG_FORMAT = f"%h{_LOG_SEP}%s{_LOG_SEP}%an{_LOG_SEP}%cr"


def get_log(root: Path, n: int = 15) -> list[Commit]:
    """Return the last *n* commits for the repo at *root*."""
    result = _run_git(
        ["log", f"--format={_LOG_FORMAT}", f"-{n}"],
        cwd=root,
    )
    if result.returncode != 0:
        # Empty repo (no commits yet) is not an error — just return []
        return []
    return parse_log(result.stdout)


def parse_log(raw: str) -> list[Commit]:
    """Parse raw ``git log`` output (unit-separator delimited) into commits."""
    commits: list[Commit] = []
    for line in raw.strip().splitlines():
        parts = line.split(_LOG_SEP)
        if len(parts) != 4:
            continue
        commits.append(
            Commit(
                hash=parts[0],
                message=parts[1],
                author=parts[2],
                relative_time=parts[3],
            )
        )
    return commits
