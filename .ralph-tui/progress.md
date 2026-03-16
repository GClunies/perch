# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Package layout**: `src/perch/` with `widgets/` and `services/` subpackages
- **Build**: hatchling backend, `uv sync` to install, `uv run` to execute
- **App architecture**: `PerchApp(App)` in `app.py`, CSS in `app.tcss`, CLI entry in `cli.py`
- **CLI pattern**: argparse in `cli.py`, lazy import of `PerchApp` inside `main()` to avoid import overhead
- **Quality gates**: `uv run pytest`, `uv run ruff check`, `uv run ty check`
- **Service layer**: Pure Python in `services/`, no Textual deps; expose `parse_*` functions for unit-testable parsing separate from subprocess calls
- **Models**: Plain dataclasses in `models.py`, no framework deps
- **Async tests**: Use `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`; Textual's `run_test()` provides `pilot` for simulating key presses and querying widgets

---

## 2026-03-16 - perch-14u.1
- Implemented full project scaffolding for US-001
- Files created:
  - `pyproject.toml` — hatchling build, deps, dev deps, entry point
  - `src/perch/__init__.py` — exports `__version__`
  - `src/perch/__main__.py` — `python -m perch` support
  - `src/perch/cli.py` — argparse with `path` and `--editor`
  - `src/perch/app.py` — `PerchApp(App)` with two `Static` placeholders
  - `src/perch/app.tcss` — left 60%, right 1fr with borders
  - `src/perch/widgets/__init__.py`, `src/perch/services/__init__.py` — subpackage stubs
  - `tests/__init__.py`, `tests/test_cli.py` — basic version test
- **Learnings:**
  - Textual CSS uses `1fr` for flex units, same as CSS grid
  - `uv sync` automatically creates `.venv` and installs the package in editable mode
  - Lazy import of `PerchApp` in `cli.py` keeps `--help` fast
---

## 2026-03-16 - perch-14u.6
- Implemented data models and git service layer for US-006
- Files created:
  - `src/perch/models.py` — dataclasses: `GitFile`, `GitStatusData`, `Commit`
  - `src/perch/services/git.py` — `get_worktree_root`, `get_status`, `get_log`, `get_current_branch` + internal `parse_status`/`parse_log`
  - `tests/test_git_service.py` — 14 tests covering porcelain v1 parsing and log parsing
- **Learnings:**
  - Separating `parse_status`/`parse_log` from their `get_*` wrappers makes unit testing trivial without mocking subprocess
  - Porcelain v1 format: index char at pos 0, worktree char at pos 1, space at pos 2, path from pos 3
  - Using `\x1f` (unit separator) as git log field delimiter avoids collisions with commit message content
---

## 2026-03-16 - perch-14u.3
- Implemented WorktreeFileTree widget for US-003
- Files created:
  - `src/perch/widgets/file_tree.py` — `WorktreeFileTree(DirectoryTree)` with `filter_paths()` excluding noise dirs
  - `tests/test_file_tree.py` — 10 tests covering filtering logic
- **Learnings:**
  - Textual's `DirectoryTree.filter_paths()` receives `Iterable[Path]` and returns `Iterable[Path]` — straightforward override
  - For glob-like patterns (e.g. `*.egg-info`), use `str.endswith()` in the filter rather than putting glob patterns in the exclusion set
  - Constructing `WorktreeFileTree("/tmp")` in tests triggers an unawaited coroutine warning from `watch_path` — harmless in sync test context
---

## 2026-03-16 - perch-14u.2
- Implemented FileViewer widget with syntax highlighting for US-002
- Files created:
  - `src/perch/widgets/file_viewer.py` — `FileViewer(VerticalScroll)` with `load_file()`, binary detection, 10K line cap, `Syntax` highlighting
  - `tests/test_file_viewer.py` — 11 tests covering `is_binary()` and `read_file_content()` helpers
- Files modified:
  - `src/perch/app.py` — replaced left-pane `Static` placeholder with `FileViewer`
- **Learnings:**
  - Extract pure helper functions (`is_binary`, `read_file_content`) from the widget for easy unit testing — same pattern as service layer
  - `ty` requires explicit `__init__` signatures matching the parent class — `**kwargs: object` fails type checking against typed parent params
  - `Syntax.guess_lexer(str(path))` detects language from file extension; `Syntax(code, lexer, line_numbers=True)` renders with line numbers
  - `rich.console.Group` composes multiple renderables (e.g., Syntax + truncation warning) into one
---

## 2026-03-16 - perch-14u.4
- Implemented tabbed right pane with tree-to-viewer wiring for US-004
- Files modified:
  - `src/perch/app.py` — replaced right-pane `Static` with `TabbedContent` (Files/Git/PR tabs), added `on_tree_node_highlighted` handler, tab switching via `action_show_tab`, and pane focus cycling
  - `src/perch/app.tcss` — removed right-pane border (TabbedContent has own styling), added `.placeholder` style
  - `pyproject.toml` — added `pytest-asyncio` dev dependency, `asyncio_mode = "auto"` config
- Files created:
  - `tests/test_app.py` — 10 async tests covering layout composition, tab switching, and quit binding
- **Learnings:**
  - `TabbedContent` tab switching: set `active` reactive to the `TabPane` id (e.g., `"tab-files"`)
  - `on_tree_node_highlighted` fires on cursor movement in `DirectoryTree` — node data has `.path` attribute via `DirEntry`
  - Async Textual tests require `pytest-asyncio`; use `async with App().run_test() as pilot` pattern
  - Override default `tab`/`shift+tab` bindings at App level to customize focus cycling between panes
  - `Static` widget in Textual 1.x doesn't expose `.renderable` — test for widget existence rather than content strings
---

## 2026-03-16 - perch-14u.10
- Implemented fuzzy file search modal for US-010
- Files created:
  - `src/perch/widgets/file_search.py` — `FileSearchScreen(ModalScreen)` with `collect_files()`, `fuzzy_score()`, `Input` + `ListView` live filtering
  - `tests/test_file_search.py` — 19 tests covering file collection exclusions and fuzzy scoring algorithm
- Files modified:
  - `src/perch/app.py` — added `Ctrl+P` binding, `action_file_search()`, `_on_file_selected()` callback to load file in viewer
- **Learnings:**
  - `ModalScreen[T]` is generic over the dismiss result type — `ModalScreen[str | None]` for returning a file path or None
  - `push_screen(screen, callback)` takes an optional callback for handling dismiss results — cleaner than message passing
  - Extract `collect_files()` and `fuzzy_score()` as pure functions outside the widget for easy unit testing (same pattern as service layer)
  - `ListItem(Label(path), name=path)` stores the path in `.name` for retrieval on selection
  - `ListView.highlighted_child` gives the currently highlighted item for Enter key handling
---

## 2026-03-16 - perch-14u.9
- Implemented GitHub service layer and PR context panel widget for US-009
- Files created:
  - `src/perch/services/github.py` — `get_pr_context`, `get_checks` + `parse_pr_view`/`parse_checks` for unit-testable parsing
  - `src/perch/widgets/pr_context.py` — `PRContextPanel(VerticalScroll)` with collapsible Reviews/Comments/CI Checks sections, auto-refresh every 30s, Enter to open check links
  - `tests/test_github_service.py` — 14 tests covering PR view and checks JSON parsing
- Files modified:
  - `src/perch/models.py` — added `PRReview`, `PRComment`, `CICheck`, `PRContext` dataclasses
  - `src/perch/app.py` — replaced PR tab placeholder with `PRContextPanel`
  - `tests/test_app.py` — updated PR tab test to check for `PRContextPanel` instead of placeholder
- **Learnings:**
  - `textual.work` import is `from textual import work`, not `from textual.work import work`
  - `gh pr view --json` returns `reviewDecision` as `null` (not empty string) when no reviews — need `or ""` fallback
  - `gh pr checks --json` workflow field can be either a dict `{"name": "..."}` or a plain string depending on check type
  - Same service layer pattern works well: `parse_*` functions for pure JSON parsing, `get_*` wrappers for subprocess calls
---

## 2026-03-16 - perch-14u.8
- Implemented editor integration for US-008
- Files created:
  - `src/perch/services/editor.py` — `resolve_editor(cli_editor)` with priority chain (CLI → $EDITOR → "cursor"), `open_file(editor, file_path, worktree_root)` using `subprocess.Popen` non-blocking
  - `tests/test_editor_service.py` — 7 tests covering resolution priority and Popen invocation
- Files modified:
  - `src/perch/app.py` — added `e` keybinding mapped to `action_open_editor`, which reads `FileViewer._current_path` and calls `open_file`
- **Learnings:**
  - `subprocess.Popen` with `start_new_session=True` detaches the editor process from the TUI so it doesn't block
  - The `FileViewer._current_path` attribute already tracks the currently displayed file — no need for separate state tracking in the app
  - Editor commands like `cursor` and `code` accept `(folder, file)` args to open the project with the file selected
---

## 2026-03-16 - perch-14u.7
- Implemented GitStatusPanel widget for US-007
- Files created:
  - `src/perch/widgets/git_status.py` — `GitStatusPanel(VerticalScroll)` with collapsible Unstaged/Staged/Untracked sections, DataTable for commits, 5s auto-refresh, `r` key manual refresh
  - `tests/test_git_status.py` — 6 tests covering `_render_file_list` helper
- Files modified:
  - `src/perch/app.py` — replaced Git tab placeholder with `GitStatusPanel`, removed unused `Static` import
  - `tests/test_app.py` — updated Git tab test to check for `GitStatusPanel` instead of placeholder
- **Learnings:**
  - Same pattern as `PRContextPanel` works well: `@work(thread=True)` for background refresh, `call_from_thread` for UI updates
  - Extract `_render_file_list` as a pure helper for unit testing styled file lists without needing a running app
  - Lazy imports of service functions inside `@work` methods keeps the widget module free of subprocess concerns at import time
---

