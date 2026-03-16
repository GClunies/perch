# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Git service pattern**: Functions in `src/perch/services/git.py` use `_run_git()` helper (subprocess wrapper), check `returncode`, raise `RuntimeError` on failure, return parsed data.
- **Test pattern**: Tests in `tests/test_git_service.py` use pytest class-based structure. Pure parsing tests need no mocking. Integration tests that need a real git repo use `tmp_path` fixture with a `_make_repo()` helper that creates a minimal repo with initial commit.

---

## 2026-03-16 - perch-54y.1
- Added `get_diff(root, path, staged=False) -> str` to git service — runs `git diff [--cached] -- <path>`
- Added `get_status_dict(root) -> dict[str, str]` to git service — wraps `get_status()` into flat `{path: status}` dict
- Files changed: `src/perch/services/git.py`, `tests/test_git_service.py`
- **Learnings:**
  - `_run_git()` uses `check=False` so callers must check `returncode` manually
  - `get_status()` returns `GitStatusData` with separate `staged`/`unstaged`/`untracked` lists; `get_status_dict()` flattens these with unstaged winning for duplicates
  - Integration tests with real git repos are simple via `tmp_path` + subprocess calls
---

