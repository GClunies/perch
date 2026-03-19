<p align="center">
  <img src="docs/images/perch-ai.png" alt="perch" width="200">
</p>

<h1 align="center">perch</h1>

<p align="center"><em>A vantage point to observe agents in worktrees.</em></p>

Built for (autonomous) agentic workflows, `perch` is a lightweight terminal context pane to quickly view:
- Files (syntax highlighted)
- Git (status, diffs, commits)
- Pull Requests (reviews, comments, CI status)

## Features

- **File browser** — Navigate the folfers and files in a worktree; select a file to view.
- **Viewer** — Renders content based on your selection.
- **Fuzzy file search** — `Ctrl+P` opens a fast fuzzy finder to jump to any file.
- **Git status panel** — See staged, unstaged, and untracked changes at a glance.
- **GitHub panel** — View PR descriptions, reviews, comments, and Actions status.
- **Editor integration** — Quickly open a file in your `$EDITOR`.
- **Command palette** — `?` for quick access to all commands.
- **Draggable splitter** — Resize panes with `[` / `]` or by dragging with your mouse.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [GitHub CLI (`gh`)](https://cli.github.com/) — optional, needed for the GitHub tab

## Getting Started

```bash
# Clone the repo
git clone <repo-url> && cd perch

# Install dependencies and the perch package (editable)
uv sync

# Launch perch in the current directory
uv run perch

# Or point it at a specific worktree
uv run perch /path/to/your/project

# Use a specific editor
uv run perch --editor code
```

## Keyboard Shortcuts

| Key              | Action                 |
| ---------------- | ---------------------- |
| `[` / `]`        | Previous / next sidebar tab |
| `Tab`            | Toggle focus between viewer and sidebar |
| `d`              | Toggle diff view       |
| `s`              | Toggle diff layout (unified / side-by-side) |
| `m`              | Toggle markdown preview (`.md` files) |
| `n` / `p`        | Next / previous file in multi-file diff |
| `h` / `j` / `k` / `l` | Vim-style navigation |
| `Ctrl+P`         | Fuzzy file search      |
| `?`              | Command palette        |
| `e`              | Open file in `$EDITOR` |
| `o` (GitHub tab) | Open item in browser   |
| `r` (Git / GitHub tab) | Refresh data     |
| `f`              | Focus mode (hide sidebar) |
| `q`              | Quit                   |

## Theming

Perch supports all built-in [Textual themes](https://textual.textualize.io/guide/design/#themes). Change the theme at runtime via the command palette (`?`), or persist your choice by setting the `TEXTUAL_THEME` environment variable:

```bash
# In your shell profile (~/.zshrc, ~/.bashrc, etc.)
export TEXTUAL_THEME="rose-pine-moon"
```

Some popular themes: `textual-dark`, `textual-light`, `nord`, `gruvbox`, `dracula`, `tokyo-night`, `monokai`, `catppuccin-mocha`, `rose-pine`, `rose-pine-moon`.

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Lint
uv run ruff check src tests

# Type check
uv run ty check src
```

## Project Layout

```
src/perch/
  app.py          # Main Textual application
  app.tcss        # Stylesheet
  cli.py          # CLI entry point (argparse)
  commands.py     # Command palette provider
  models.py       # Data classes (git status, PR context, CI checks)
  services/
    editor.py     # External editor integration
    git.py        # Git operations (status, log, branch)
    github.py     # GitHub CLI wrapper (PR context, checks)
  widgets/
    file_tree.py  # Worktree file tree widget
    viewer.py     # Unified viewer (files, diffs, markdown, logs)
    file_search.py# Fuzzy file search modal
    git_status.py # Git status panel
    github_panel.py # PR reviews, comments, GitHub Actions panel
    splitter.py   # Draggable pane splitter
```
