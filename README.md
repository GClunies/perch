<p align="center">
  <img src="docs/images/perch-ai.png" alt="perch" width="200">
</p>

<h1 align="center">perch</h1>

<p align="center"><em>A vantage point to observe agents in worktrees.</em></p>

Built for agentic workflows, `perch` is a lightweight terminal UI to quickly view:
- Files (syntax highlighted, markdown preview, image rendering)
- Git (status, diffs, commits)
- Pull Requests (reviews, comments, CI status)

## Features

- **File browser** — Navigate folders and files in a worktree with git status indicators.
- **Viewer** — Syntax highlighting, unified/side-by-side diffs, markdown preview, and terminal image rendering.
- **Fuzzy file search** — `Ctrl+P` opens a fast fuzzy finder.
- **Git status panel** — Staged, unstaged, and untracked changes plus recent commits. Auto-refreshes every 5s.
- **GitHub panel** — PR description, reviews, comments, and Actions CI status. Auto-refreshes every 30s.
- **Editor integration** — `o` opens the current file in your editor.
- **Command palette** — `?` for quick access to all commands and theme switching.
- **Resizable panes** — Drag the splitter or use `-` / `=` to resize. `f` for full-screen focus mode.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [GitHub CLI (`gh`)](https://cli.github.com/) — optional, needed for the GitHub tab

## Getting Started

```bash
# Clone and install
git clone <repo-url> && cd perch
uv sync

# Launch in the current directory
uv run perch

# Or point at a specific worktree
uv run perch /path/to/your/project

# Use a specific editor (defaults to $EDITOR, then cursor)
uv run perch --editor code
```

## Keyboard Shortcuts

| Key | Action |
| --- | ------ |
| `[` / `]` | Previous / next sidebar tab |
| `Tab` | Toggle focus between viewer and sidebar panes|
| `j` / `k` | Navigate down / up (vim-style) |
| `h` / `l` | Collapse / expand (file tree), scroll left / right (viewer) |
| `d` | Toggle diff view |
| `s` | Toggle diff layout (unified / side-by-side) |
| `m` | Toggle markdown preview (`.md` files) |
| `n` / `p` | Next / previous file in multi-file diff |
| `Ctrl+P` | Fuzzy file search |
| `o` | Open file in editor (file tree / viewer) or browser (GitHub tab) |
| `r` | Refresh data (Git / GitHub tabs) |
| `f` | Focus mode (hide sidebar) |
| `-` / `=` | Shrink / grow focused pane |
| `?` | Command palette |
| `q` | Quit |

## Theming

Perch supports all built-in [Textual themes](https://textual.textualize.io/guide/design/#themes). Change the theme via the command palette (`?`), or set `TEXTUAL_THEME`:

```bash
export TEXTUAL_THEME="rose-pine-moon"
```

## Development

```bash
uv sync --group dev    # Install dev dependencies
uv run pytest          # Run tests
uv run ruff check src tests  # Lint
uv run ty check src    # Type check
```

## Project Layout

```
src
└── perch
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
        ├── splitter.py     # Draggable pane splitter
        └── viewer.py       # Content viewer (files, diffs, markdown, images)
```
