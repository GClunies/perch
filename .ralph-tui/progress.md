# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Package layout**: `src/perch/` with `widgets/` and `services/` subpackages
- **Build**: hatchling backend, `uv sync` to install, `uv run` to execute
- **App architecture**: `PerchApp(App)` in `app.py`, CSS in `app.tcss`, CLI entry in `cli.py`
- **CLI pattern**: argparse in `cli.py`, lazy import of `PerchApp` inside `main()` to avoid import overhead
- **Quality gates**: `uv run pytest`, `uv run ruff check`, `uv run ty check`

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

