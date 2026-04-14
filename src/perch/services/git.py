from __future__ import annotations

import subprocess
from pathlib import Path

from perch.models import (
    Commit,
    CommitFile,
    CommitSummary,
    GitFile,
    GitStatusData,
    Worktree,
)

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


def get_ignored_paths(root: Path, paths: list[Path]) -> set[Path]:
    """Return the subset of *paths* that are ignored by git."""
    if not paths:
        return set()
    # Send each path twice — once plain, once with trailing / — so git
    # matches both file and directory ignore patterns.
    path_map: dict[str, Path] = {}
    for p in paths:
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        path_map[rel] = p
        path_map[rel.rstrip("/") + "/"] = p

    input_text = "\n".join(path_map.keys())
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=root,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and line in path_map:
            ignored.add(path_map[line])
    return ignored


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


def get_worktrees(root: Path) -> list[Worktree]:
    """Return all worktrees for the repo at *root*."""
    result = _run_git(["worktree", "list", "--porcelain"], cwd=root)
    if result.returncode != 0:
        return []
    return parse_worktree_list(result.stdout)


def parse_worktree_list(raw: str) -> list[Worktree]:
    """Parse ``git worktree list --porcelain`` output into Worktree objects."""
    worktrees: list[Worktree] = []
    path = head = branch = None
    for line in raw.splitlines():
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("HEAD "):
            head = line.removeprefix("HEAD ")
        elif line.startswith("branch "):
            ref = line.removeprefix("branch ")
            branch = ref.removeprefix("refs/heads/")
        elif line == "detached":
            branch = None
        elif line == "" and path and head:
            worktrees.append(Worktree(path=path, head=head, branch=branch))
            path = head = branch = None
    # Handle trailing entry without final blank line
    if path and head:
        worktrees.append(Worktree(path=path, head=head, branch=branch))
    return worktrees


def get_branches(root: Path) -> list[str]:
    """Return local branch names, current branch first."""
    result = _run_git(["branch", "--format=%(refname:short)"], cwd=root)
    if result.returncode != 0:
        return []
    return [b for b in result.stdout.strip().splitlines() if b]


def switch_branch(root: Path, branch: str) -> None:
    """Switch to *branch* in the worktree at *root*."""
    result = _run_git(["switch", branch], cwd=root)
    if result.returncode != 0:
        raise RuntimeError(f"git switch failed: {result.stderr.strip()}")


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


def get_diff(root: Path, path: str, staged: bool = False) -> str:
    """Return raw unified diff text for *path* relative to *root*.

    If *staged* is True, uses ``--cached`` to show the staged diff.
    Returns an empty string when there are no changes.
    """
    args = ["diff", "--no-color"]
    if staged:
        args.append("--cached")
    args.extend(["--", path])
    result = _run_git(args, cwd=root)
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")
    return result.stdout


def get_commit_diff(root: Path, commit_hash: str) -> str:
    """Return the full diff for a commit (all files).

    Uses ``git show`` with unified diff format.
    """
    result = _run_git(
        ["show", "--no-color", "--format=", commit_hash],
        cwd=root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show failed: {result.stderr.strip()}")
    return result.stdout


def get_status_dict(root: Path) -> dict[str, str]:
    """Return a flat ``{relative_path: status_label}`` dict for O(1) lookup.

    Wraps :func:`get_status` and flattens all categories into a single dict.
    For files that appear in both staged and unstaged, the unstaged status wins
    (since it reflects the working-tree state the user sees).
    """
    status_data = get_status(root)
    result: dict[str, str] = {}
    for gf in status_data.staged:
        result[gf.path] = gf.status
    for gf in status_data.unstaged:
        result[gf.path] = gf.status
    for gf in status_data.untracked:
        result[gf.path] = gf.status
    return result


_LOG_SEP = "\x1f"  # unit separator — unlikely in commit data
_LOG_FORMAT = f"%h{_LOG_SEP}%s{_LOG_SEP}%an{_LOG_SEP}%cr"
_SUMMARY_FORMAT = f"%H{_LOG_SEP}%s{_LOG_SEP}%an{_LOG_SEP}%aI{_LOG_SEP}%b"


def get_log(root: Path, n: int = 15, skip: int = 0) -> list[Commit]:
    """Return the last *n* commits for the repo at *root*."""
    args = ["log", f"--format={_LOG_FORMAT}", f"-{n}"]
    if skip > 0:
        args.append(f"--skip={skip}")
    result = _run_git(
        args,
        cwd=root,
    )
    if result.returncode != 0:
        # Empty repo (no commits yet) is not an error — just return []
        return []
    return parse_log(result.stdout)


def get_commit_file_diff(root: Path, commit_hash: str, path: str) -> str:
    """Return the diff for a single file within a commit."""
    result = _run_git(
        ["show", "--no-color", "--format=", commit_hash, "--", path],
        cwd=root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show failed: {result.stderr.strip()}")
    return result.stdout


def get_commit_files(root: Path, commit_hash: str) -> list[CommitFile]:
    """Return files changed in *commit_hash* with their status."""
    result = _run_git(
        ["diff-tree", "--no-commit-id", "-r", "--name-status", commit_hash],
        cwd=root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff-tree failed: {result.stderr.strip()}")
    files: list[CommitFile] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        raw_status = parts[0]
        status_char = raw_status[0]
        label = _STATUS_LABELS.get(status_char, raw_status)
        if status_char in ("R", "C") and len(parts) >= 3:
            files.append(CommitFile(path=parts[2], status=label, old_path=parts[1]))
        else:
            files.append(CommitFile(path=parts[1], status=label))
    return files


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


def get_commit_summary(root: Path, commit_hash: str) -> CommitSummary:
    """Return structured metadata and stats for a commit."""
    meta_result = _run_git(
        ["show", "--no-color", f"--format={_SUMMARY_FORMAT}", "-s", commit_hash],
        cwd=root,
    )
    if meta_result.returncode != 0:
        raise RuntimeError(f"git show failed: {meta_result.stderr.strip()}")
    # Do NOT call .strip() on the whole line — \x1f (unit separator) is stripped
    # by Python's str.strip(), which would drop an empty body field.
    raw = meta_result.stdout.rstrip("\n")
    parts = raw.split(_LOG_SEP, maxsplit=4)
    if len(parts) < 4:
        raise RuntimeError(f"Unexpected git show output: {meta_result.stdout!r}")
    body = parts[4].strip() if len(parts) >= 5 else ""
    stat_result = _run_git(
        ["show", "--no-color", "--stat", "--format=", commit_hash],
        cwd=root,
    )
    stats = stat_result.stdout.strip() if stat_result.returncode == 0 else ""
    return CommitSummary(
        hash=parts[0],
        subject=parts[1],
        author=parts[2],
        date=parts[3],
        body=body,
        stats=stats,
    )
