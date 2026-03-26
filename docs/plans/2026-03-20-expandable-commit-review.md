# Expandable Commit Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor commit review from a monolithic diff blob to an expandable sidebar pattern where commits behave like folders with individually selectable file diffs.

**Architecture:** Commits in the GitPanel ListView become expandable items. Enter/l toggles expand/collapse, inserting/removing child file items (accordion — one expanded at a time). The Viewer gains two new modes: commit summary card and single-file commit diff. The git service gets three new functions for commit-level queries. Pagination loads history in pages of 50. A ref watcher detects new commits automatically.

**Tech Stack:** Python 3.12, Textual 8.1.1, Rich (text styling), git CLI

**Spec:** `docs/specs/2026-03-20-expandable-commit-review-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `tests/conftest.py` | Create | Shared `git_worktree` fixture for all test files |
| `src/perch/models.py` | Modify | Add `CommitFile` and `CommitSummary` dataclasses |
| `src/perch/services/git.py` | Modify | Add `get_commit_files`, `get_commit_file_diff`, `get_commit_summary`; modify `get_log` for pagination |
| `src/perch/widgets/git_status.py` | Modify | Expand/collapse commits, split refresh, ref watcher, pagination |
| `src/perch/widgets/viewer.py` | Modify | New `show_commit_summary` and `load_commit_file_diff`; remove old commit diff code |
| `src/perch/app.py` | Modify | Update event handlers for new item types |
| `src/perch/widgets/file_tree.py` | Modify | Add `r` refresh keybinding |
| `tests/test_git_service.py` | Modify | Tests for new git service functions |
| `tests/test_git_status.py` | Modify | Tests for expand/collapse, pagination, refresh split |
| `tests/test_viewer.py` | Modify | Tests for new viewer modes, removal of old code |
| `tests/test_app.py` | Modify | Tests for updated event wiring |
| `tests/test_file_tree.py` | Modify | Test for `r` refresh binding |

---

### Task 0: Create Shared Test Fixture

**Files:**
- Create: `tests/conftest.py`

The `git_worktree` fixture currently exists independently in multiple test files. Create a shared `conftest.py` so all test files can use it. Check each test file for its `git_worktree` fixture and consolidate into `conftest.py`.

- [ ] **Step 1: Create `tests/conftest.py`**

```python
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
```

- [ ] **Step 2: Remove duplicate `git_worktree` fixtures from individual test files**

Check and remove from: `tests/test_app.py`, `tests/test_git_service.py`, `tests/test_git_status.py`, `tests/test_viewer.py`, and any others that define their own `git_worktree`.

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `uv run pytest tests/ -x -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_app.py tests/test_git_service.py tests/test_git_status.py tests/test_viewer.py
git commit -m "refactor: consolidate git_worktree fixture into conftest.py"
```

---

### Task 1: Add New Data Models

**Files:**
- Modify: `src/perch/models.py`
- Test: `tests/test_git_service.py`

- [ ] **Step 1: Write tests for new models**

```python
# In tests/test_git_service.py — add at the top of the file

from perch.models import CommitFile, CommitSummary


class TestCommitFileModel:
    def test_basic_fields(self) -> None:
        cf = CommitFile(path="src/app.py", status="modified", old_path=None)
        assert cf.path == "src/app.py"
        assert cf.status == "modified"
        assert cf.old_path is None

    def test_renamed_file(self) -> None:
        cf = CommitFile(path="new.py", status="renamed", old_path="old.py")
        assert cf.old_path == "old.py"


class TestCommitSummaryModel:
    def test_basic_fields(self) -> None:
        cs = CommitSummary(
            hash="abc1234",
            subject="fix login",
            body="Detailed description",
            author="Alice",
            date="2026-03-20T10:00:00+00:00",
            stats=" 2 files changed, 10 insertions(+), 3 deletions(-)",
        )
        assert cs.hash == "abc1234"
        assert cs.subject == "fix login"
        assert cs.body == "Detailed description"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_service.py::TestCommitFileModel -v`
Expected: FAIL — `ImportError: cannot import name 'CommitFile'`

- [ ] **Step 3: Implement the models**

Add to `src/perch/models.py`:

```python
@dataclass
class CommitFile:
    path: str
    status: str
    old_path: str | None = None


@dataclass
class CommitSummary:
    hash: str
    subject: str
    body: str
    author: str
    date: str
    stats: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_service.py::TestCommitFileModel tests/test_git_service.py::TestCommitSummaryModel -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/models.py tests/test_git_service.py
git commit -m "feat: add CommitFile and CommitSummary models"
```

---

### Task 2: Add `get_log` Pagination (`skip` Parameter)

**Files:**
- Modify: `src/perch/services/git.py:170-179`
- Test: `tests/test_git_service.py`

- [ ] **Step 1: Write test for skip parameter**

```python
# In tests/test_git_service.py

class TestGetLogPagination:
    def test_skip_parameter(self, git_worktree: Path) -> None:
        """get_log with skip should return commits after the skipped ones."""
        from perch.services.git import get_log

        # Create 3 commits
        for i in range(3):
            (git_worktree / f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"commit {i}"],
                cwd=git_worktree,
                check=True,
            )

        all_commits = get_log(git_worktree, n=10)
        skipped = get_log(git_worktree, n=10, skip=1)

        assert len(all_commits) == 3
        assert len(skipped) == 2
        assert skipped[0].hash == all_commits[1].hash

    def test_skip_past_end(self, git_worktree: Path) -> None:
        """Skipping past all commits returns empty list."""
        from perch.services.git import get_log

        result = get_log(git_worktree, n=10, skip=999)
        assert result == []
```

Note: the `git_worktree` fixture is now in `tests/conftest.py` (created in Task 0).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_service.py::TestGetLogPagination -v`
Expected: FAIL — `TypeError: get_log() got an unexpected keyword argument 'skip'`

- [ ] **Step 3: Implement skip parameter**

In `src/perch/services/git.py`, modify `get_log`:

```python
def get_log(root: Path, n: int = 15, skip: int = 0) -> list[Commit]:
    """Return *n* commits for the repo at *root*, skipping the first *skip*."""
    args = ["log", f"--format={_LOG_FORMAT}", f"-{n}"]
    if skip > 0:
        args.append(f"--skip={skip}")
    result = _run_git(args, cwd=root)
    if result.returncode != 0:
        return []
    return parse_log(result.stdout)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_service.py::TestGetLogPagination -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/services/git.py tests/test_git_service.py
git commit -m "feat: add skip parameter to get_log for pagination"
```

---

### Task 3: Add `get_commit_files`

**Files:**
- Modify: `src/perch/services/git.py`
- Test: `tests/test_git_service.py`

- [ ] **Step 1: Write tests**

```python
# In tests/test_git_service.py

class TestGetCommitFiles:
    def test_returns_modified_files(self, git_worktree: Path) -> None:
        """Should list files changed in a commit with correct status."""
        from perch.services.git import get_commit_files

        # Modify a file and commit
        (git_worktree / "hello.py").write_text("modified content\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "modify hello"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        files = get_commit_files(git_worktree, head)
        assert len(files) == 1
        assert files[0].path == "hello.py"
        assert files[0].status == "modified"
        assert files[0].old_path is None

    def test_added_file(self, git_worktree: Path) -> None:
        """New files should have status 'added'."""
        from perch.services.git import get_commit_files

        (git_worktree / "new.py").write_text("new file\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add new"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        files = get_commit_files(git_worktree, head)
        assert any(f.path == "new.py" and f.status == "added" for f in files)

    def test_deleted_file(self, git_worktree: Path) -> None:
        """Deleted files should have status 'deleted'."""
        from perch.services.git import get_commit_files

        subprocess.run(
            ["git", "rm", "hello.py"], cwd=git_worktree, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "delete hello"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        files = get_commit_files(git_worktree, head)
        assert any(f.path == "hello.py" and f.status == "deleted" for f in files)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_service.py::TestGetCommitFiles -v`
Expected: FAIL — `ImportError: cannot import name 'get_commit_files'`

- [ ] **Step 3: Implement**

Add to `src/perch/services/git.py`:

```python
from perch.models import Commit, CommitFile, GitFile, GitStatusData

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
```

Update the import at the top of `git.py` to include `CommitFile`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_service.py::TestGetCommitFiles -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/services/git.py tests/test_git_service.py
git commit -m "feat: add get_commit_files to git service"
```

---

### Task 4: Add `get_commit_file_diff`

**Files:**
- Modify: `src/perch/services/git.py`
- Test: `tests/test_git_service.py`

- [ ] **Step 1: Write tests**

```python
class TestGetCommitFileDiff:
    def test_returns_diff_for_file(self, git_worktree: Path) -> None:
        """Should return a unified diff for one file in a commit."""
        from perch.services.git import get_commit_file_diff

        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "modify hello"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        diff = get_commit_file_diff(git_worktree, head, "hello.py")
        assert "diff --git" in diff
        assert "hello.py" in diff

    def test_no_commit_metadata_in_output(self, git_worktree: Path) -> None:
        """Output should not contain commit message or author lines."""
        from perch.services.git import get_commit_file_diff

        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "test commit message"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        diff = get_commit_file_diff(git_worktree, head, "hello.py")
        assert "test commit message" not in diff
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_service.py::TestGetCommitFileDiff -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement**

Add to `src/perch/services/git.py`:

```python
def get_commit_file_diff(root: Path, commit_hash: str, path: str) -> str:
    """Return the diff for a single file within a commit."""
    result = _run_git(
        ["show", "--no-color", "--format=", commit_hash, "--", path],
        cwd=root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show failed: {result.stderr.strip()}")
    return result.stdout
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_service.py::TestGetCommitFileDiff -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/services/git.py tests/test_git_service.py
git commit -m "feat: add get_commit_file_diff to git service"
```

---

### Task 5: Add `get_commit_summary`

**Files:**
- Modify: `src/perch/services/git.py`
- Test: `tests/test_git_service.py`

- [ ] **Step 1: Write tests**

```python
class TestGetCommitSummary:
    def test_returns_summary(self, git_worktree: Path) -> None:
        """Should return structured commit summary."""
        from perch.services.git import get_commit_summary

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        summary = get_commit_summary(git_worktree, head)
        assert summary.hash == head
        assert summary.author == "test"  # from git_worktree fixture config
        assert summary.subject  # non-empty
        assert summary.date  # non-empty ISO date

    def test_stats_contain_file_info(self, git_worktree: Path) -> None:
        """Stats should contain file change information."""
        from perch.services.git import get_commit_summary

        (git_worktree / "stats_test.py").write_text("content\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add stats_test"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        summary = get_commit_summary(git_worktree, head)
        assert "stats_test.py" in summary.stats

    def test_body_with_unit_separator(self, git_worktree: Path) -> None:
        """Commit body containing \\x1f should be parsed correctly."""
        from perch.services.git import get_commit_summary

        (git_worktree / "sep.txt").write_text("x\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "subject\n\nbody with \x1f separator"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        summary = get_commit_summary(git_worktree, head)
        assert "\x1f" in summary.body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_service.py::TestGetCommitSummary -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement**

Add to `src/perch/services/git.py`:

```python
from perch.models import Commit, CommitFile, CommitSummary, GitFile, GitStatusData

_SUMMARY_FORMAT = f"%H{_LOG_SEP}%s{_LOG_SEP}%an{_LOG_SEP}%aI{_LOG_SEP}%b"


def get_commit_summary(root: Path, commit_hash: str) -> CommitSummary:
    """Return structured metadata and stats for a commit."""
    # Call 1: structured fields
    meta_result = _run_git(
        ["show", "--no-color", f"--format={_SUMMARY_FORMAT}", "-s", commit_hash],
        cwd=root,
    )
    if meta_result.returncode != 0:
        raise RuntimeError(f"git show failed: {meta_result.stderr.strip()}")

    parts = meta_result.stdout.strip().split(_LOG_SEP, maxsplit=4)
    if len(parts) < 5:
        raise RuntimeError(f"Unexpected git show output: {meta_result.stdout!r}")

    # Call 2: stat output only
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
        body=parts[4].strip(),
        stats=stats,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_service.py::TestGetCommitSummary -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/services/git.py tests/test_git_service.py
git commit -m "feat: add get_commit_summary to git service"
```

---

### Task 6: Viewer — Add `show_commit_summary` and `load_commit_file_diff`

**Files:**
- Modify: `src/perch/widgets/viewer.py`
- Test: `tests/test_viewer.py`

- [ ] **Step 1: Write tests for `show_commit_summary`**

```python
# In tests/test_viewer.py — add new test class

from perch.models import CommitSummary


class TestCommitSummary:
    async def test_show_commit_summary_sets_state(self, worktree: Path) -> None:
        """show_commit_summary should set viewer state correctly."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc1234",
                subject="fix login",
                body="Detailed fix",
                author="Alice",
                date="2026-03-20T10:00:00+00:00",
                stats=" 1 file changed, 5 insertions(+)",
            )
            viewer.show_commit_summary(summary)
            assert viewer._diff_mode is False
            assert viewer._current_path is None
            assert viewer._commit_file_context is None
            assert viewer._current_summary is summary

    async def test_show_commit_summary_displays_content(self, worktree: Path) -> None:
        """Summary card should contain commit info."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc1234",
                subject="fix login",
                body="",
                author="Alice",
                date="2026-03-20T10:00:00+00:00",
                stats=" 1 file changed",
            )
            viewer.show_commit_summary(summary)
            content = viewer._content._renderable
            rendered = str(content)
            assert "abc1234" in rendered
            assert "Alice" in rendered
```

- [ ] **Step 2: Write tests for `load_commit_file_diff`**

```python
class TestCommitFileDiff:
    async def test_load_commit_file_diff_sets_state(
        self, git_worktree: Path
    ) -> None:
        """load_commit_file_diff should set viewer state for commit-file mode."""
        # Modify file and commit
        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "change"],
            cwd=git_worktree,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        app = PerchApp(git_worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_commit_file_diff(head, "hello.py")
            assert viewer._diff_mode is True
            assert viewer._current_path is None
            assert viewer._commit_file_context == (head, "hello.py")
            assert viewer._current_summary is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_viewer.py::TestCommitSummary tests/test_viewer.py::TestCommitFileDiff -v`
Expected: FAIL — `AttributeError`

- [ ] **Step 4: Implement new viewer methods**

In `src/perch/widgets/viewer.py`, add new state variables to `__init__`:

```python
self._commit_file_context: tuple[str, str] | None = None  # (hash, path)
self._current_summary: CommitSummary | None = None
```

Add new methods after `load_commit_diff`:

```python
def show_commit_summary(self, summary: CommitSummary) -> None:
    """Show a commit summary card in the viewer."""
    from rich.text import Text
    from rich.console import Group

    self._current_path = None
    self._diff_mode = False
    self._commit_file_context = None
    self._current_summary = summary
    self._show_content_view()
    self._update_border_title(f"commit {summary.hash[:8]}")

    header = Text()
    header.append(f"commit {summary.hash}\n", style="bold cyan")
    header.append(f"Author: {summary.author}\n", style="")
    header.append(f"Date:   {summary.date}\n\n", style="dim")
    header.append(f"    {summary.subject}\n", style="bold")
    if summary.body:
        header.append(f"\n    {summary.body}\n", style="")
    header.append(f"\n{summary.stats}\n", style="")

    self._content.update(header)
    self.scroll_home(animate=False)
    self._refresh_footer()

def load_commit_file_diff(self, commit_hash: str, path: str) -> None:
    """Load and display a single file's diff within a commit."""
    from perch.services.git import get_commit_file_diff

    if self.worktree_root is None:
        return

    self._current_path = None
    self._diff_mode = True
    self._current_summary = None
    self._commit_file_context = (commit_hash, path)
    self._update_border_title(f"{commit_hash[:8]}:{path}")

    try:
        diff_text = get_commit_file_diff(self.worktree_root, commit_hash, path)
    except RuntimeError as e:
        self._show_content_view()
        self._content.update(f"Error getting diff: {e}")
        return

    if not diff_text:
        self._show_content_view()
        self._content.update(Text("No changes", style="dim italic"))
    elif self._diff_layout == "side-by-side":
        self._show_side_by_side_view(diff_text)
    else:
        self._show_content_view()
        styled = render_diff(diff_text, dark=self._is_dark_theme())
        self._content.update(styled)
    self.scroll_home(animate=False)
    self._refresh_footer()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_viewer.py::TestCommitSummary tests/test_viewer.py::TestCommitFileDiff -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/perch/widgets/viewer.py tests/test_viewer.py
git commit -m "feat: add show_commit_summary and load_commit_file_diff to Viewer"
```

---

### Task 7: Viewer — Update Existing Methods for Commit-File Context

**Files:**
- Modify: `src/perch/widgets/viewer.py`
- Test: `tests/test_viewer.py`

- [ ] **Step 1: Write tests for updated behaviors**

```python
class TestCommitFileDiffIntegration:
    async def test_check_action_toggle_diff_with_commit_context(
        self, git_worktree: Path
    ) -> None:
        """toggle_diff should be enabled when _commit_file_context is set."""
        app = PerchApp(git_worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._commit_file_context = ("abc123", "file.py")
            assert viewer.check_action("toggle_diff", ()) is True

    async def test_toggle_diff_off_shows_summary(self, worktree: Path) -> None:
        """Pressing d while viewing commit-file diff should show summary."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc", subject="s", body="", author="a",
                date="d", stats="stats",
            )
            viewer._commit_file_context = ("abc", "file.py")
            viewer._current_summary = summary
            viewer._diff_mode = True
            viewer.action_toggle_diff()
            assert viewer._diff_mode is False
            assert viewer._commit_file_context is None

    async def test_load_diff_uses_commit_file_context(
        self, git_worktree: Path
    ) -> None:
        """_load_diff should use get_commit_file_diff when context is set."""
        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "c"], cwd=git_worktree, check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        app = PerchApp(git_worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer._commit_file_context = (head, "hello.py")
            viewer._diff_mode = True
            viewer._load_diff()
            # Should not crash; content should be updated

    async def test_refresh_content_with_commit_file(
        self, git_worktree: Path
    ) -> None:
        """refresh_content should re-render commit-file diff."""
        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "c"], cwd=git_worktree, check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_worktree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        app = PerchApp(git_worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            viewer.load_commit_file_diff(head, "hello.py")
            viewer.refresh_content()  # should not crash

    async def test_refresh_content_with_summary(self, worktree: Path) -> None:
        """refresh_content should re-render commit summary."""
        app = PerchApp(worktree)
        async with app.run_test():
            viewer = app.query_one(Viewer)
            summary = CommitSummary(
                hash="abc", subject="s", body="", author="a",
                date="d", stats="stats",
            )
            viewer.show_commit_summary(summary)
            viewer.refresh_content()  # should not crash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_viewer.py::TestCommitFileDiffIntegration -v`
Expected: FAIL

- [ ] **Step 3: Update `check_action`**

```python
def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
    if action == "toggle_diff":
        return self._current_path is not None or self._commit_file_context is not None
    if action == "toggle_diff_layout":
        return self._diff_mode
    if action == "toggle_markdown_preview":
        return (
            self._current_path is not None
            and self._is_markdown(self._current_path)
            and not self._diff_mode
        )
    return True
```

Remove the `next_diff_file`/`prev_diff_file` check — those bindings are being removed.

- [ ] **Step 4: Update `action_toggle_diff`**

```python
def action_toggle_diff(self) -> None:
    """Toggle between normal file view and diff view."""
    if self._current_path is None and self._commit_file_context is None:
        return
    self._diff_mode = not self._diff_mode
    if self._diff_mode:
        self._load_diff()
    elif self._commit_file_context is not None:
        # Return to commit summary when toggling off a commit-file diff
        if self._current_summary is not None:
            self.show_commit_summary(self._current_summary)
    else:
        self.load_file(self._current_path)
    self._refresh_footer()
```

- [ ] **Step 5: Update `_load_diff`**

```python
def _load_diff(self) -> None:
    """Load and display the diff for the current file or commit-file."""
    if self._commit_file_context is not None:
        commit_hash, path = self._commit_file_context
        self.load_commit_file_diff(commit_hash, path)
        return

    if self._current_path is None or self.worktree_root is None:
        # ... existing fallback code unchanged
```

- [ ] **Step 6: Update `refresh_content`**

```python
def refresh_content(self) -> None:
    """Re-render the current content (e.g. after a theme change)."""
    if self._commit_file_context is not None:
        commit_hash, path = self._commit_file_context
        self.load_commit_file_diff(commit_hash, path)
    elif self._current_summary is not None:
        self.show_commit_summary(self._current_summary)
    elif self._current_path is not None:
        if self._diff_mode:
            self._load_diff()
        else:
            self.load_file(self._current_path)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_viewer.py::TestCommitFileDiffIntegration -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/perch/widgets/viewer.py tests/test_viewer.py
git commit -m "feat: update viewer check_action, toggle_diff, _load_diff, refresh_content for commit-file context"
```

---

### Task 8: Viewer — Remove Old Commit Diff Code

> **Note:** This task removes `_current_commit` which is referenced in `_show_content_view()`. That line (`self._current_commit = None`) must also be removed. Task 6 adds `load_commit_file_diff` which calls `_show_content_view()` — the `_current_commit = None` line is harmless until this task removes the attribute. Complete this task immediately after Task 7.

**Files:**
- Modify: `src/perch/widgets/viewer.py`
- Modify: `tests/test_viewer.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Remove from viewer**

Remove from `src/perch/widgets/viewer.py`:
- `load_commit_diff()` method (lines ~597-656)
- `_diff_file_offsets`, `_diff_file_index` from `__init__`
- `action_next_diff_file()`, `action_prev_diff_file()`, `_scroll_to_diff_file()`
- `n`/`p` bindings from `BINDINGS`
- `_current_commit` from `__init__`
- `self._current_commit = None` from `_show_content_view()`

- [ ] **Step 2: Update existing tests**

Update tests that reference removed methods:
- Remove/update any tests for `load_commit_diff`
- Remove tests for `action_next_diff_file`/`action_prev_diff_file`
- Update `test_app.py` tests that call `on_git_panel_commit_selected` or `load_commit_diff`

Search for all references:
```bash
uv run pytest tests/ -x -v 2>&1 | head -50
```

Fix each failing test to use the new API.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -x -v`
Expected: PASS (all tests adapted to new API)

- [ ] **Step 4: Commit**

```bash
git add src/perch/widgets/viewer.py tests/test_viewer.py tests/test_app.py
git commit -m "refactor: remove old commit diff code from viewer (load_commit_diff, n/p navigation)"
```

---

### Task 9: GitPanel — Expand/Collapse Commits

**Files:**
- Modify: `src/perch/widgets/git_status.py`
- Test: `tests/test_git_status.py`

- [ ] **Step 1: Write tests**

```python
# In tests/test_git_status.py

class TestCommitExpandCollapse:
    async def test_toggle_commit_expands(self, git_worktree: Path) -> None:
        """toggle_commit should insert child file items below the commit."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            # Find a commit item
            commit_item = None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commit_item = node
                    break
            assert commit_item is not None
            commit_hash = commit_item.name.removeprefix("commit:")

            panel.toggle_commit(commit_hash)
            await pilot.pause()

            assert panel._expanded_commit == commit_hash
            # Check for child items
            found_child = False
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:"):
                    found_child = True
                    break
            assert found_child

    async def test_toggle_commit_collapses(self, git_worktree: Path) -> None:
        """Toggling an already expanded commit should remove children."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            commit_item = None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commit_item = node
                    break
            assert commit_item is not None
            commit_hash = commit_item.name.removeprefix("commit:")

            panel.toggle_commit(commit_hash)
            await pilot.pause()
            panel.toggle_commit(commit_hash)
            await pilot.pause()

            assert panel._expanded_commit is None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:"):
                    pytest.fail("Child items should be removed after collapse")

    async def test_accordion_collapses_previous(self, git_worktree: Path) -> None:
        """Expanding a new commit should collapse the previously expanded one."""
        # Create a second commit
        (git_worktree / "second.txt").write_text("second\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "second commit"],
            cwd=git_worktree,
            check=True,
        )

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            # Find two commit items
            commits = []
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commits.append(node.name.removeprefix("commit:"))
            assert len(commits) >= 2

            panel.toggle_commit(commits[0])
            await pilot.pause()
            panel.toggle_commit(commits[1])
            await pilot.pause()

            assert panel._expanded_commit == commits[1]
            # Only children from commits[1] should exist
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit-file:"):
                    assert node.name.startswith(f"commit-file:{commits[1]}:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_status.py::TestCommitExpandCollapse -v`
Expected: FAIL — `AttributeError: 'GitPanel' has no attribute 'toggle_commit'`

- [ ] **Step 3: Implement `toggle_commit`**

Add to `GitPanel.__init__`:

```python
self._expanded_commit: str | None = None
```

Add the `toggle_commit` method:

```python
def toggle_commit(self, commit_hash: str) -> None:
    """Expand or collapse a commit's file list (accordion pattern)."""
    from perch.services.git import get_commit_files

    if self._expanded_commit == commit_hash:
        # Collapse
        self._collapse_commit(commit_hash)
        self._expanded_commit = None
    else:
        # Collapse previous if any
        if self._expanded_commit is not None:
            self._collapse_commit(self._expanded_commit)
        # Expand new
        self._expand_commit(commit_hash)
        self._expanded_commit = commit_hash

def _expand_commit(self, commit_hash: str) -> None:
    """Insert child file items below the commit item."""
    from perch.services.git import get_commit_files

    # Find the commit item index
    commit_idx = None
    for i, node in enumerate(self._nodes):
        if isinstance(node, ListItem) and node.name == f"commit:{commit_hash}":
            commit_idx = i
            break
    if commit_idx is None:
        return

    # Update chevron
    self._set_commit_chevron(commit_idx, expanded=True)

    # Get files and insert after the commit item
    try:
        files = get_commit_files(self._worktree_root, commit_hash)
    except RuntimeError:
        return

    for j, f in enumerate(files):
        text = Text()
        text.append("  ")  # indent
        style = _STATUS_STYLES.get(f.status, "")
        text.append(f"{f.status:<10}", style=style)
        text.append(f" {f.path}")
        child = ListItem(
            Label(text),
            name=f"commit-file:{commit_hash}:{f.path}",
        )
        self.insert(commit_idx + 1 + j, child)

def _collapse_commit(self, commit_hash: str) -> None:
    """Remove child file items for a commit."""
    prefix = f"commit-file:{commit_hash}:"
    to_remove = [
        node for node in self._nodes
        if isinstance(node, ListItem) and node.name and node.name.startswith(prefix)
    ]
    for node in to_remove:
        node.remove()

    # Update chevron
    for i, node in enumerate(self._nodes):
        if isinstance(node, ListItem) and node.name == f"commit:{commit_hash}":
            self._set_commit_chevron(i, expanded=False)
            break

def _set_commit_chevron(self, index: int, expanded: bool) -> None:
    """Update the chevron indicator on a commit item by rebuilding the text."""
    node = self._nodes[index]
    if not isinstance(node, ListItem) or not node.name:
        return
    commit_hash = node.name.removeprefix("commit:")
    # Find the matching commit data to rebuild the label
    # Use the plain text after the chevron as the content
    label = node.query_one(Label)
    text = label.renderable
    if not isinstance(text, Text):
        return
    plain = text.plain
    if not plain.startswith(("\u25b8 ", "\u25be ")):
        return
    # Strip old chevron, rebuild with new one
    content_after_chevron = plain[2:]
    chevron = "\u25be " if expanded else "\u25b8 "
    new_text = Text()
    new_text.append(chevron)
    # Re-apply styles by reconstructing from the commit hash in the name
    # The content format is: "hash message  author  time"
    # Simplest safe approach: just append unstyled content
    # (expand/collapse is transient; next refresh rebuilds with full styling)
    new_text.append(content_after_chevron)
    label.update(new_text)
```

- [ ] **Step 4: Update `_update_display` to add chevrons to commit items**

In `_update_display`, change the commit rendering:

```python
# Recent commits
self.append(_make_section_header("Recent Commits"))
for c in commits:
    text = Text()
    text.append("\u25b8 ")  # collapsed chevron
    text.append(c.hash, style="cyan")
    text.append(f" {c.message}  ")
    text.append(c.author, style="dim")
    text.append(f"  {c.relative_time}", style="dim")
    item = ListItem(Label(text), name=f"commit:{c.hash}")
    self.append(item)
```

Give the section header a name:

```python
def _make_section_header(title: str, name: str | None = None) -> ListItem:
    text = Text(f"\n{title}", style="bold")
    item = ListItem(Label(text), classes="section-header", name=name)
    item.disabled = True
    return item
```

Update the "Recent Commits" call: `self.append(_make_section_header("Recent Commits", name="section-commits"))`

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_status.py::TestCommitExpandCollapse -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/perch/widgets/git_status.py tests/test_git_status.py
git commit -m "feat: add commit expand/collapse with accordion behavior to GitPanel"
```

---

### Task 10: GitPanel — Remove `CommitSelected` Message and Update Event Flow

**Files:**
- Modify: `src/perch/widgets/git_status.py`
- Modify: `src/perch/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write tests for new event wiring**

```python
# In tests/test_app.py

class TestCommitExpandFromApp:
    async def test_select_commit_toggles_expand(self, git_worktree: Path) -> None:
        """Pressing Enter on a commit item should expand it."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = pilot.app.query_one(GitPanel)
            await pilot.pause()

            # Navigate to a commit and select it
            commit_idx = None
            for i, node in enumerate(panel._nodes):
                if isinstance(node, ListItem) and node.name and node.name.startswith("commit:"):
                    commit_idx = i
                    break
            assert commit_idx is not None
            panel.index = commit_idx
            await pilot.pause()

            # Simulate Enter
            panel.action_select_cursor()
            await pilot.pause()

            assert panel._expanded_commit is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app.py::TestCommitExpandFromApp -v`
Expected: FAIL

- [ ] **Step 3: Update `app.py` event handlers**

Update `on_list_view_selected`:

```python
def on_list_view_selected(self, event: ListView.Selected) -> None:
    """Handle selection (Enter/l) in the sidebar."""
    try:
        if self.query_one(TabbedContent).active == "tab-git":
            item = event.item
            if isinstance(item, ListItem) and item.name:
                if item.name.startswith("commit:"):
                    commit_hash = item.name.removeprefix("commit:")
                    panel = self.query_one(GitPanel)
                    panel.toggle_commit(commit_hash)
                    # The highlight handler will fire after toggle and
                    # load the summary via the background worker pattern.
                    return
                elif item.name.startswith("commit-file:"):
                    self.query_one(Viewer).focus()
                    return
            self.query_one(Viewer).focus()
    except Exception:
        pass
```

Update `on_list_view_highlighted`:

```python
def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
    """Preview the highlighted item in the viewer when navigating with j/k."""
    try:
        if self.query_one(TabbedContent).active != "tab-git":
            return
    except Exception:
        return
    item = event.item
    if not isinstance(item, ListItem) or item.name is None:
        return
    viewer = self.query_one(Viewer)
    if item.name.startswith("commit:"):
        commit_hash = item.name.removeprefix("commit:")
        viewer.worktree_root = self.worktree_path
        self._load_commit_summary(commit_hash)
    elif item.name.startswith("commit-file:"):
        parts = item.name.removeprefix("commit-file:").split(":", 1)
        if len(parts) == 2:
            viewer.worktree_root = self.worktree_path
            viewer.load_commit_file_diff(parts[0], parts[1])
    elif item.name == "load-more-commits":
        self.query_one(GitPanel)._load_more_commits()
    else:
        file_path = self.worktree_path / item.name
        staged = getattr(item, "_staged", False)
        if file_path.is_file():
            viewer.load_file(file_path)
        else:
            viewer.show_deleted_file_diff(file_path, item.name, staged=staged)
```

Remove `on_git_panel_commit_selected` handler.

Add a background worker for loading commit summaries (avoids blocking UI):

```python
@work(thread=True)
def _load_commit_summary(self, commit_hash: str) -> None:
    """Load commit summary in background and update viewer."""
    from perch.services.git import get_commit_summary
    try:
        summary = get_commit_summary(self.worktree_path, commit_hash)
    except RuntimeError:
        return
    self.app.call_from_thread(
        self.query_one(Viewer).show_commit_summary, summary
    )
```

Update `_show_current_git_item` to handle the three item types.

- [ ] **Step 4: Remove `CommitSelected` message from GitPanel**

In `git_status.py`:
- Remove `class CommitSelected(Message)`
- Remove commit handling from `on_list_view_selected` (keep only `FileSelected` posting)
- Remove commit handling from `activate_current_selection`

- [ ] **Step 5: Run tests and fix any remaining failures**

Run: `uv run pytest tests/ -x -v`

Fix any tests that reference `CommitSelected` or `on_git_panel_commit_selected`.

- [ ] **Step 6: Commit**

```bash
git add src/perch/widgets/git_status.py src/perch/app.py tests/test_app.py tests/test_git_status.py
git commit -m "feat: wire commit expand/collapse through app event handlers, remove CommitSelected message"
```

---

### Task 11: GitPanel — Split Refresh (File Status vs Commits)

**Files:**
- Modify: `src/perch/widgets/git_status.py`
- Test: `tests/test_git_status.py`

- [ ] **Step 1: Write tests**

```python
class TestSplitRefresh:
    async def test_file_status_refresh_preserves_commits(
        self, git_worktree: Path
    ) -> None:
        """_refresh_file_status should not touch commit items."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            # Count commit items before refresh
            commit_count_before = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )

            panel._refresh_file_status()
            await pilot.pause()

            commit_count_after = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )

            assert commit_count_after == commit_count_before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_status.py::TestSplitRefresh -v`
Expected: FAIL

- [ ] **Step 3: Implement split refresh**

Split `_do_refresh` into two methods:

```python
@work(thread=True)
def _refresh_file_status_worker(self) -> None:
    """Background worker to refresh file sections only."""
    from perch.services.git import get_status
    try:
        status = get_status(self._worktree_root)
    except RuntimeError:
        return
    self.app.call_from_thread(self._update_file_sections, status)

def _update_file_sections(self, status: GitStatusData) -> None:
    """Replace file sections (above section-commits header), keep commits intact."""
    # Find the boundary
    boundary = None
    for i, node in enumerate(self._nodes):
        if isinstance(node, ListItem) and node.name == "section-commits":
            boundary = i
            break

    if boundary is None:
        return  # Commits section not built yet

    saved_name = self._get_selected_name()

    # Collect and remove items before the boundary
    items_to_remove = [self._nodes[i] for i in range(boundary)]
    for item in items_to_remove:
        item.remove()

    # Build new file sections and insert before the boundary
    new_items = self._build_file_items(status)
    for j, item in enumerate(new_items):
        self.insert(j, item)

    self._restore_selection(saved_name)
    self.post_message(self.SelectionRestored())
```

Extract `_build_file_items` from `_update_display`:

```python
def _build_file_items(self, status: GitStatusData) -> list[ListItem]:
    """Build the file section ListItems (unstaged, staged, untracked)."""
    items: list[ListItem] = []

    items.append(_make_section_header("Unstaged Changes"))
    if status.unstaged:
        for f in status.unstaged:
            items.append(_make_file_item(f, staged=False))
    else:
        item = ListItem(Label(Text("  No unstaged changes", style="dim")))
        item.disabled = True
        items.append(item)

    items.append(_make_section_header("Staged Changes"))
    if status.staged:
        for f in status.staged:
            items.append(_make_file_item(f, staged=True))
    else:
        item = ListItem(Label(Text("  No staged changes", style="dim")))
        item.disabled = True
        items.append(item)

    items.append(_make_section_header("Untracked Files"))
    if status.untracked:
        for f in status.untracked:
            items.append(_make_file_item(f, staged=False))
    else:
        item = ListItem(Label(Text("  No untracked files", style="dim")))
        item.disabled = True
        items.append(item)

    return items
```

Update `on_mount` timer to use `_refresh_file_status_worker` instead of `_do_refresh`.

Keep `action_refresh` calling a full refresh (both files + commits).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_status.py::TestSplitRefresh -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -x -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/perch/widgets/git_status.py tests/test_git_status.py
git commit -m "feat: split GitPanel refresh into file-status (auto) and commits (triggered)"
```

---

### Task 12: GitPanel — Commit Pagination

**Files:**
- Modify: `src/perch/widgets/git_status.py`
- Test: `tests/test_git_status.py`

- [ ] **Step 1: Write tests**

```python
class TestCommitPagination:
    async def test_sentinel_appears_when_more_commits(
        self, git_worktree: Path
    ) -> None:
        """A 'more history' sentinel should appear when page is full."""
        # The git_worktree fixture has 1 commit; page_size is 50 so no sentinel.
        # We test with a smaller page size.
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            panel._commit_page_size = 1  # Force small page
            panel._refresh_commits_section()
            await pilot.pause()

            sentinel = None
            for node in panel._nodes:
                if isinstance(node, ListItem) and node.name == "load-more-commits":
                    sentinel = node
                    break
            # With 1 commit and page_size=1, sentinel should appear
            # (only if there are more commits beyond page 1)
            assert sentinel is not None, "Sentinel 'load-more-commits' should be present"

    async def test_load_more_commits(self, git_worktree: Path) -> None:
        """_load_more_commits should append additional commit items."""
        # Create several commits
        for i in range(3):
            (git_worktree / f"page{i}.txt").write_text(f"{i}\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"page commit {i}"],
                cwd=git_worktree,
                check=True,
            )

        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            panel._commit_page_size = 2
            panel._refresh_commits_section()
            await pilot.pause()

            initial_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )

            panel._load_more_commits()
            await pilot.pause()

            final_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )

            assert final_commits > initial_commits
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_status.py::TestCommitPagination -v`
Expected: FAIL

- [ ] **Step 3: Implement pagination**

Add to `GitPanel.__init__`:

```python
self._commit_page_size: int = 50
self._commits_loaded: int = 0
self._loading_more: bool = False
```

Add pagination methods:

```python
@work(thread=True)
def _refresh_commits_section(self) -> None:
    """Rebuild the commits section in a background thread."""
    from perch.services.git import get_log, get_commit_files

    commits = get_log(self._worktree_root, n=self._commit_page_size)
    expanded = self._expanded_commit
    expanded_files = None
    if expanded and any(c.hash == expanded for c in commits):
        try:
            expanded_files = get_commit_files(self._worktree_root, expanded)
        except RuntimeError:
            expanded = None
    else:
        expanded = None

    self.app.call_from_thread(
        self._apply_commits_update, commits, expanded, expanded_files
    )

def _apply_commits_update(
    self, commits: list, expanded: str | None, expanded_files: list | None
) -> None:
    """Apply commit section rebuild on the main thread."""
    # Remove existing commit items and sentinel
    to_remove = [
        node for node in self._nodes
        if isinstance(node, ListItem) and node.name and (
            node.name.startswith("commit:") or
            node.name.startswith("commit-file:") or
            node.name == "load-more-commits"
        )
    ]
    for node in to_remove:
        node.remove()

    self._expanded_commit = expanded
    self._commits_loaded = len(commits)

    for c in commits:
        chevron = "\u25be " if c.hash == expanded else "\u25b8 "
        text = Text()
        text.append(chevron)
        text.append(c.hash, style="cyan")
        text.append(f" {c.message}  ")
        text.append(c.author, style="dim")
        text.append(f"  {c.relative_time}", style="dim")
        self.append(ListItem(Label(text), name=f"commit:{c.hash}"))

        # Re-expand if this was the expanded commit
        if c.hash == expanded and expanded_files:
            for f in expanded_files:
                child_text = Text()
                child_text.append("  ")
                style = _STATUS_STYLES.get(f.status, "")
                child_text.append(f"{f.status:<10}", style=style)
                child_text.append(f" {f.path}")
                self.append(ListItem(
                    Label(child_text),
                    name=f"commit-file:{c.hash}:{f.path}",
                ))

    if len(commits) == self._commit_page_size:
        sentinel_text = Text("\u2500\u2500 more history \u2500\u2500", style="dim")
        self.append(ListItem(Label(sentinel_text), name="load-more-commits"))

    if not expanded:
        self._expanded_commit = None

@work(thread=True)
def _load_more_commits(self) -> None:
    """Load the next page of commits in a background thread."""
    if self._loading_more:
        return
    self._loading_more = True

    from perch.services.git import get_log

    commits = get_log(
        self._worktree_root, n=self._commit_page_size, skip=self._commits_loaded
    )
    self.app.call_from_thread(self._apply_more_commits, commits)

def _apply_more_commits(self, commits: list) -> None:
    """Apply loaded commits on the main thread."""
    # Remove sentinel
    for node in self._nodes:
        if isinstance(node, ListItem) and node.name == "load-more-commits":
            node.remove()
            break

    self._commits_loaded += len(commits)

    for c in commits:
        text = Text()
        text.append("\u25b8 ")
        text.append(c.hash, style="cyan")
        text.append(f" {c.message}  ")
        text.append(c.author, style="dim")
        text.append(f"  {c.relative_time}", style="dim")
        self.append(ListItem(Label(text), name=f"commit:{c.hash}"))

    if len(commits) == self._commit_page_size:
        sentinel_text = Text("\u2500\u2500 more history \u2500\u2500", style="dim")
        self.append(ListItem(Label(sentinel_text), name="load-more-commits"))

    self._loading_more = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_status.py::TestCommitPagination -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/widgets/git_status.py tests/test_git_status.py
git commit -m "feat: add commit history pagination with lazy loading sentinel"
```

---

### Task 13: GitPanel — Ref Watcher

**Files:**
- Modify: `src/perch/widgets/git_status.py`
- Test: `tests/test_git_status.py`

- [ ] **Step 1: Write tests**

```python
class TestRefWatcher:
    async def test_new_commit_triggers_refresh(self, git_worktree: Path) -> None:
        """Making a new commit should trigger a commits refresh."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()

            initial_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )

            # Make a new commit
            (git_worktree / "newfile.txt").write_text("new\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(
                ["git", "commit", "-m", "new commit"],
                cwd=git_worktree,
                check=True,
            )

            # Wait for ref watcher to detect (poll interval is 2-3s, use pause cycles)
            for _ in range(20):
                await pilot.pause(delay=0.2)

            final_commits = sum(
                1 for node in panel._nodes
                if isinstance(node, ListItem) and node.name
                and node.name.startswith("commit:")
            )

            assert final_commits > initial_commits
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_git_status.py::TestRefWatcher -v`
Expected: FAIL

- [ ] **Step 3: Implement ref watcher**

Add to `on_mount`:

```python
self._start_ref_watcher()
```

Add the watcher method:

```python
def _start_ref_watcher(self) -> None:
    """Start polling git refs for new commits."""
    from perch.services.git import get_current_branch

    try:
        self._watched_branch = get_current_branch(self._worktree_root)
    except RuntimeError:
        return

    self._last_ref_mtime: float | None = None
    self._last_head_mtime: float | None = None
    self._last_packed_mtime: float | None = None
    self._update_ref_mtimes()
    self.set_interval(2.5, self._check_refs)

def _get_git_dir(self) -> Path:
    """Return the .git directory for the worktree."""
    git_dir = self._worktree_root / ".git"
    if git_dir.is_file():
        # worktree: .git is a file pointing to the real git dir
        content = git_dir.read_text().strip()
        if content.startswith("gitdir: "):
            return Path(content.removeprefix("gitdir: "))
    return git_dir

def _update_ref_mtimes(self) -> None:
    """Snapshot current mtimes for watched ref files."""
    git_dir = self._get_git_dir()
    ref_file = git_dir / "refs" / "heads" / self._watched_branch
    if ref_file.exists():
        self._last_ref_mtime = ref_file.stat().st_mtime
    else:
        self._last_ref_mtime = None
        head_file = git_dir / "HEAD"
        packed_file = git_dir / "packed-refs"
        self._last_head_mtime = head_file.stat().st_mtime if head_file.exists() else None
        self._last_packed_mtime = packed_file.stat().st_mtime if packed_file.exists() else None

def _check_refs(self) -> None:
    """Poll ref mtimes and refresh commits if changed."""
    from perch.services.git import get_current_branch

    git_dir = self._get_git_dir()
    ref_file = git_dir / "refs" / "heads" / self._watched_branch
    changed = False

    if ref_file.exists():
        mtime = ref_file.stat().st_mtime
        if mtime != self._last_ref_mtime:
            changed = True
    else:
        head_file = git_dir / "HEAD"
        packed_file = git_dir / "packed-refs"
        head_mtime = head_file.stat().st_mtime if head_file.exists() else None
        packed_mtime = packed_file.stat().st_mtime if packed_file.exists() else None
        if head_mtime != self._last_head_mtime or packed_mtime != self._last_packed_mtime:
            changed = True

    if changed:
        # Re-resolve branch in case it changed
        try:
            new_branch = get_current_branch(self._worktree_root)
            if new_branch != self._watched_branch:
                self._watched_branch = new_branch
        except RuntimeError:
            pass
        self._update_ref_mtimes()
        self._refresh_commits_section()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_status.py::TestRefWatcher -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/widgets/git_status.py tests/test_git_status.py
git commit -m "feat: add ref watcher to auto-detect new commits"
```

---

### Task 14: FileTree — Add `r` Refresh Keybinding

**Files:**
- Modify: `src/perch/widgets/file_tree.py`
- Test: `tests/test_file_tree.py`

- [ ] **Step 1: Write test**

```python
# In tests/test_file_tree.py

class TestRefreshBinding:
    async def test_r_keybinding_exists(self, worktree: Path) -> None:
        """FileTree should have an 'r' refresh binding."""
        app = PerchApp(worktree)
        async with app.run_test():
            tree = app.query_one(FileTree)
            binding_keys = [b.key for b in tree.BINDINGS]
            assert "r" in binding_keys

    async def test_refresh_action_does_not_crash(self, worktree: Path) -> None:
        """action_refresh should execute without error."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(FileTree)
            tree.action_refresh()
            await pilot.pause()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_file_tree.py::TestRefreshBinding -v`
Expected: FAIL

- [ ] **Step 3: Implement**

In `src/perch/widgets/file_tree.py`, add to `BINDINGS`:

```python
("r", "refresh", "Refresh"),
```

Add the action method:

```python
def action_refresh(self) -> None:
    """Re-scan the filesystem."""
    self.reload()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_file_tree.py::TestRefreshBinding -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/widgets/file_tree.py tests/test_file_tree.py
git commit -m "feat: add r keybinding to FileTree for refresh"
```

---

### Task 15: Final Integration Test and Cleanup

**Files:**
- All modified files
- Test: `tests/`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `uv run ruff check src/ tests/`
Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `uv run ty check src/`
Expected: No errors (or pre-existing only)

- [ ] **Step 4: Verify coverage threshold**

Run: `uv run pytest tests/ --cov`
Expected: Coverage >= 95%

- [ ] **Step 5: Fix any remaining issues**

Address any failures from the above checks.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup for expandable commit review"
```
