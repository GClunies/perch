<p align="center">
  <img src="docs/images/perch-ai.png" alt="perch" width="200">
</p>

<h1 align="center">perch</h1>

<p align="center"><em>A vantage point to observe agents in worktrees.</em></p>

<p align="center">
  <a href="https://github.com/GClunies/perch/actions/workflows/ci.yml"><img src="https://github.com/GClunies/perch/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://pypi.org/project/perch-ai/"><img src="https://img.shields.io/pypi/v/perch-ai" alt="PyPI"></a>
  <a href="https://pypi.org/project/perch-ai/"><img src="https://img.shields.io/pypi/pyversions/perch-ai" alt="Python"></a>
</p>

Built for agentic workflows, `perch` is a lightweight terminal UI to quickly view:
- Files (syntax highlighted, markdown preview, image rendering)
- Git (status, diffs, commits)
- Pull Requests (reviews, comments, CI status)

## Features

- **File browser** — Navigate folders and files in a worktree with git status indicators.
- **Viewer** — Syntax highlighting, unified/side-by-side diffs, markdown preview, and terminal image rendering.
- **Fuzzy file search** — `Ctrl+P` opens a fast fuzzy finder.
- **Git status panel** — Staged, unstaged, and untracked changes plus commits. Auto-refreshes every 5s.
- **GitHub panel** — PR description, reviews, comments, and Actions CI status. Auto-refreshes every 30s.
- **Editor integration** — `o` opens the current file in your editor.
- **Keybinding help** — `?` shows all keyboard shortcuts. `Ctrl+Shift+P` opens the command palette for commands and theme switching.
- **Resizable panes** — Drag the splitter or use `-` / `=` to resize. `f` for full-screen focus mode.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [GitHub CLI (`gh`)](https://cli.github.com/) — optional, needed for the GitHub tab

## Getting Started

```bash
# Install from PyPI
uv pip install perch-ai

# Launch in the current directory
perch

# Or point at a specific worktree
perch /path/to/your/project

# Use a specific editor (defaults to $EDITOR, then cursor)
perch --editor code
```

## CLI Usage

```
perch [path] [--editor EDITOR]
```

| Argument | Description |
| --- | --- |
| `path` | Directory to browse (default: current directory) |
| `--editor` | Editor command for opening files (default: `$EDITOR`, then `cursor`) |

## Keyboard Shortcuts

| Key | Action |
| --- | ------ |
| `?` | Show keybinding help |
| `Ctrl+Q` | Quit |
| `Tab` | Switch focus between sidebar and viewer |
| `[` / `]` | Previous / next sidebar tab |
| `j` / `k` | Navigate down / up (vim-style) |
| `h` / `l` | Collapse / expand (file tree), scroll left / right (viewer) |
| `d` | Toggle diff view |
| `s` | Toggle diff layout (unified / side-by-side) |
| `p` | Toggle markdown preview (`.md` files) |
| `Ctrl+P` | Fuzzy file search |
| `o` / `e` | Open in editor (file tree / viewer) or browser (GitHub tab) |
| `c` | Copy path to clipboard |
| `r` | Refresh data (Git / GitHub tabs) |
| `f` | Focus mode (hide sidebar) |
| `-` / `=` | Shrink / grow focused pane |
| `Ctrl+Shift+P` | Command palette |

## Theming

Perch supports all built-in [Textual themes](https://textual.textualize.io/guide/design/#themes). Change the theme via the command palette (`Ctrl+Shift+P`), or set `TEXTUAL_THEME`:

```bash
export TEXTUAL_THEME="rose-pine-moon"
```

## Development

```bash
# Clone and install in editable mode
git clone <repo-url> && cd perch
uv pip install -e .

# Now you can run perch directly
perch

# Run tests and linting
uv run pytest                # Run tests
uv run ruff check src tests  # Lint
uv run ty check src          # Type check
```

## Deployment

1. Update `__version__` in `src/perch/__init__.py` (e.g. `"0.2.0"`)
2. Commit and push
3. Go to GitHub → Actions → **Publish** → Run workflow

The version is read automatically from `__init__.py`. The workflow runs: tests → build → TestPyPI → PyPI → git tag → GitHub Release.

## Project Layout

```
src
└── perch
    ├── __init__.py         # Package version
    ├── __main__.py         # python -m perch entry point
    ├── _bindings.py        # Shared keybinding constants
    ├── app.py              # Main Textual application
    ├── app.tcss            # Stylesheet
    ├── cli.py              # CLI entry point (argparse)
    ├── commands.py         # Command palette provider
    ├── models.py           # Data models (git status, PR context, CI checks)
    ├── services
    │   ├── editor.py       # Open files in $EDITOR
    │   ├── git.py          # Git operations (status, log, diff, branch)
    │   └── github.py       # GitHub CLI wrapper (PRs, reviews, checks)
    └── widgets
        ├── file_search.py  # Fuzzy file search modal
        ├── file_tree.py    # Directory tree with git status indicators
        ├── git_status.py   # Git status panel (files + commits)
        ├── github_panel.py # PR reviews, comments, GitHub Actions panel
        ├── help_screen.py  # Keybinding help overlay
        ├── splitter.py     # Draggable pane splitter
        └── viewer.py       # Content viewer (files, diffs, markdown, images)
```
