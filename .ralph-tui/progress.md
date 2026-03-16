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

