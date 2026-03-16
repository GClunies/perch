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

## 2026-03-16 - perch-54y.2
- Added `_get_syntax_theme()` method to `FileViewer` — returns `"monokai"` for dark themes, `"default"` for light
- Updated `Syntax()` call in `load_file()` to use `theme=self._get_syntax_theme()`
- Added `watch_theme()` watcher to `PerchApp` — re-renders file viewer when theme changes
- Files changed: `src/perch/widgets/file_viewer.py`, `src/perch/app.py`
- **Learnings:**
  - Textual's `watch_<reactive>` methods auto-fire when a reactive attribute changes; `theme` is reactive on `App`
  - `self.app.current_theme.dark` is the canonical way to check light/dark mode from a widget
  - Wrapping theme check in try/except handles the case where the widget isn't yet mounted
---

