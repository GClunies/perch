# Perch

**A vantage point for agentic workflows.**

Perch is a terminal UI (TUI) built with [Textual](https://textual.textualize.io/) that gives you a single-pane-of-glass view into a git worktree. Browse files, inspect git status, and monitor pull request reviews and CI checks — all without leaving your terminal.

## Features

- **File browser** — Navigate your worktree with a tree view; select a file to preview it with syntax highlighting.
- **Fuzzy file search** — `Ctrl+P` opens a fast fuzzy finder to jump to any file.
- **Git status panel** — See staged, unstaged, and untracked changes at a glance.
- **PR context panel** — View the PR title, review decision, reviewer comments, and CI check status for the current branch (requires the [GitHub CLI](https://cli.github.com/)).
- **Editor integration** — Press `e` to open the current file in your editor (defaults to `$EDITOR`, then `cursor`).
- **Command palette** — `Ctrl+Shift+P` for quick access to all commands.
- **Draggable splitter** — Resize the file viewer and sidebar panes with `[` / `]` or by dragging.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [GitHub CLI (`gh`)](https://cli.github.com/) — optional, needed for the PR tab

## Getting Started

```bash
# Clone the repo
git clone <repo-url> && cd perch

# Install dependencies and the perch package (editable)
uv sync

# Launch Perch in the current directory
uv run perch

# Or point it at a specific worktree
uv run perch /path/to/your/project

# Use a specific editor
uv run perch --editor code
```

## Keyboard Shortcuts

| Key              | Action                 |
| ---------------- | ---------------------- |
| `1` / `2` / `3`  | Switch to Files / Git / PR tab |
| `Tab`            | Toggle focus between panes |
| `Ctrl+P`         | Fuzzy file search      |
| `Ctrl+Shift+P`   | Command palette        |
| `e`              | Open file in editor    |
| `[` / `]`        | Shrink / grow left pane |
| `r` (PR tab)     | Refresh PR data        |
| `Enter` (PR tab) | Open CI check in browser |
| `q`              | Quit                   |

## Theming

Perch supports all built-in [Textual themes](https://textual.textualize.io/guide/design/#themes). Change the theme at runtime via the command palette (`Ctrl+Shift+P`), or persist your choice by setting the `TEXTUAL_THEME` environment variable:

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
  cli.py          # CLI entry point (argparse)
  commands.py     # Command palette provider
  models.py       # Data classes (git status, PR context, CI checks)
  services/
    editor.py     # External editor integration
    git.py        # Git operations (status, log, branch)
    github.py     # GitHub CLI wrapper (PR context, checks)
  widgets/
    file_tree.py  # Worktree file tree widget
    file_viewer.py# Syntax-highlighted file preview
    file_search.py# Fuzzy file search modal
    git_status.py # Git status panel
    pr_context.py # PR reviews, comments, CI checks panel
    splitter.py   # Draggable pane splitter
```