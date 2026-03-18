<p align="center">
  <img src="docs/images/perch-ai.png" alt="perch" width="200">
</p>

<h1 align="center">perch</h1>

<p align="center"><em>A perch to view agentic changes in your worktrees.</em></p>

A lightweight companion to run alongside coding agents in worktrees. Perch isn't an editor. It's a read-only context pane to help build confidence in your autonomous agentic workflows.

Spin it up and watch the worktree update in realtime, or pop it open as needed. Files, diffs, git status, PR reviews, and CI results — all without leaving your terminal.

## Features

- **File browser** — Navigate your worktree with a tree view; select a file to preview it with syntax highlighting.
- **Fuzzy file search** — `Ctrl+P` opens a fast fuzzy finder to jump to any file.
- **Git status panel** — See staged, unstaged, and untracked changes at a glance.
- **GitHub panel** — View the PR description, reviews, comments, and GitHub Actions status for the current branch (requires the [GitHub CLI](https://cli.github.com/)).
- **Viewer** — A unified left pane that renders files, diffs, markdown, CI logs, and reviews based on what you select.
- **Editor integration** — Press `e` to open the current file in your editor (defaults to `$EDITOR`, then `cursor`).
- **Command palette** — `?` for quick access to all commands.
- **Draggable splitter** — Resize panes with `[` / `]` or by dragging.

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
| `1` / `2` / `3`  | Switch to Files / Git / GitHub tab |
| `Tab`            | Toggle focus between panes |
| `d`              | Toggle diff view       |
| `s`              | Toggle diff layout (unified / side-by-side) |
| `n` / `p`        | Next / previous file in multi-file diff |
| `Ctrl+P`         | Fuzzy file search      |
| `?`              | Command palette        |
| `e`              | Open file in editor    |
| `o` (GitHub tab) | Open item in browser   |
| `r` (GitHub tab) | Refresh GitHub data    |
| `f`              | Focus mode (hide right pane) |
| `[` / `]`        | Shrink / grow left pane |
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
