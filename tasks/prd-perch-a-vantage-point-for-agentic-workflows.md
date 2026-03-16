# PRD: Perch — A Vantage Point for Agentic Workflows

## Overview
Perch is a Python TUI built with Textual for terminal-centric agentic workflows. It provides a two-pane layout: a syntax-highlighted file viewer on the left and a tabbed panel (Files / Git / PR) on the right, separated by a mouse-draggable splitter. It targets developers using worktree-heavy workflows with tools like cmux, worktrunk, and ralph-tui, giving them a quick read-only vantage point on their repo state without leaving the terminal.

## Goals
- Provide a fast, read-only TUI for browsing files with syntax highlighting
- Show git status (unstaged/staged/untracked) and recent commits in a dedicated tab
- Show PR context (reviews, comments, CI checks) via `gh` CLI in a dedicated tab
- Support mouse-draggable and keyboard-resizable pane splitting
- Open files in an external editor with a single keypress
- Offer fuzzy file search (`Ctrl+P`) and a command palette (`Ctrl+Shift+P`)
- Be pip-installable as a standalone CLI tool (`perch` / `pc`)

## Quality Gates

These commands must pass for every user story:
- `uv run pytest` — Unit tests
- `uv run ruff check` — Linting
- `uv run ty` — Type checking

For UI stories, also include:
- Run `uv run perch` in a real git worktree and visually verify the described behavior

## User Stories

### US-001: Project Scaffolding and Basic App Shell
As a developer, I want a properly structured Python package with entry points so that `perch` can be installed and launched from the CLI.

**Acceptance Criteria:**
- [ ] `pyproject.toml` configured with hatchling build backend, Python >=3.12, `textual` and `rich` as dependencies, `pytest`, `ruff`, and `ty` as dev dependencies
- [ ] `src/perch/__init__.py` exports `__version__`
- [ ] `src/perch/__main__.py` allows `python -m perch`
- [ ] `src/perch/cli.py` uses `argparse` with positional `path` argument (defaults to `.`) and `--editor` flag
- [ ] `src/perch/app.py` defines `PerchApp(App)` with a basic `Horizontal` layout containing a left placeholder and a right placeholder
- [ ] `src/perch/app.tcss` sets left pane to 60% width and right pane to `1fr`
- [ ] Console script entry point `perch` is registered in `pyproject.toml`
- [ ] `uv run perch` launches the TUI and shows two empty panes side by side

### US-002: File Viewer with Syntax Highlighting
As a developer, I want a file viewer pane that renders files with syntax highlighting and line numbers so that I can read code comfortably.

**Acceptance Criteria:**
- [ ] `src/perch/widgets/file_viewer.py` implements `FileViewer` widget
- [ ] Uses `rich.syntax.Syntax.from_path()` for automatic language detection and highlighting
- [ ] Displays line numbers alongside file content
- [ ] Detects binary files (checks for null bytes in first 8KB) and shows a "Binary file" message instead of content
- [ ] Caps display at ~10,000 lines with a truncation warning for large files
- [ ] Scrollable via keyboard and mouse
- [ ] `load_file(path: Path)` method updates the displayed file
- [ ] Integrated into the left pane of `PerchApp`

### US-003: File Tree with Directory Filtering
As a developer, I want a directory tree in the right pane that filters out noise directories so that I can quickly navigate project files.

**Acceptance Criteria:**
- [ ] `src/perch/widgets/file_tree.py` implements `WorktreeFileTree` as a subclass of `textual.widgets.DirectoryTree`
- [ ] `filter_paths()` excludes `.git/`, `__pycache__/`, `.DS_Store`, `node_modules/`, `.ruff_cache/`, and similar noise directories
- [ ] Tree root is set to the worktree path provided via CLI
- [ ] Tree is navigable with arrow keys and mouse
- [ ] `Enter` expands/collapses directories

### US-004: Tabbed Right Pane with Tree-to-Viewer Wiring
As a developer, I want a tabbed right pane where navigating the file tree immediately updates the file viewer so that browsing is seamless.

**Acceptance Criteria:**
- [ ] Right pane uses `TabbedContent` with three tabs: "Files", "Git", "PR"
- [ ] "Files" tab contains the `WorktreeFileTree` from US-003
- [ ] "Git" and "PR" tabs contain placeholder content (e.g., "Coming soon")
- [ ] Handling `on_tree_node_highlighted` (not `FileSelected`) updates the `FileViewer` — cursor movement alone triggers preview, no Enter required
- [ ] Number keys `1`, `2`, `3` switch between tabs
- [ ] `q` quits the app
- [ ] `Tab` / `Shift+Tab` cycles focus between left and right panes

### US-005: Draggable Splitter
As a developer, I want to resize the panes by dragging a vertical splitter with the mouse or using keyboard shortcuts so that I can adjust the layout to my preference.

**Acceptance Criteria:**
- [ ] `src/perch/widgets/splitter.py` implements `DraggableSplitter` widget
- [ ] Splitter renders as a 1-column-wide `│` character
- [ ] Mouse drag: `on_mouse_down` captures mouse, `on_mouse_move` adjusts left pane width, `on_mouse_up` releases
- [ ] Splitter highlights on hover to indicate interactivity
- [ ] `[` key shrinks left pane by 2 columns, `]` key grows it by 2 columns
- [ ] Minimum width enforced on both panes (left: 20 cols, right: 25 cols) to prevent collapse
- [ ] Splitter is positioned between `FileViewer` and `TabbedContent` in the `Horizontal` layout

### US-006: Data Models and Git Service Layer
As a developer, I want clean data models and a git service that parses CLI output so that the TUI widgets have structured data to display.

**Acceptance Criteria:**
- [ ] `src/perch/models.py` defines dataclasses: `GitFile(path, status, staged)`, `GitStatusData(unstaged, staged, untracked)`, `Commit(hash, message, author, relative_time)`
- [ ] `src/perch/services/git.py` implements `get_worktree_root(path) → Path` using `git rev-parse --show-toplevel`
- [ ] `get_status(root) → GitStatusData` parses `git status --porcelain=v1` output into categorized file lists
- [ ] `get_log(root, n=15) → list[Commit]` parses `git log --format=...` output
- [ ] `get_current_branch(root) → str` returns the current branch name
- [ ] All functions use `subprocess.run` with proper error handling (e.g., not in a git repo)
- [ ] No Textual dependency in models or services — pure Python, easily testable
- [ ] Unit tests cover parsing of `git status --porcelain=v1` and `git log` output formats

### US-007: Git Status Panel Widget
As a developer, I want the Git tab to show unstaged, staged, and untracked files plus recent commits so that I can see repo state at a glance.

**Acceptance Criteria:**
- [ ] `src/perch/widgets/git_status.py` implements `GitStatusPanel` widget
- [ ] Three collapsible sections: "Unstaged Changes", "Staged Changes", "Untracked Files" — each containing a list of file paths with status indicators
- [ ] `DataTable` below the collapsible sections shows recent commits with columns: Hash, Message, Author, When
- [ ] All sections are inside a `VerticalScroll` container
- [ ] Auto-refreshes every 5 seconds via a `@work(thread=True)` background worker
- [ ] `r` key triggers an immediate manual refresh
- [ ] Replaces the "Git" tab placeholder from US-004
- [ ] Gracefully handles "not a git repository" (shows informative message)

### US-008: Editor Integration
As a developer, I want to press `e` to open the currently highlighted file in my preferred editor so that I can quickly start editing.

**Acceptance Criteria:**
- [ ] `src/perch/services/editor.py` implements `open_file(editor, file_path, worktree_root)`
- [ ] Uses `subprocess.Popen` (non-blocking) to launch the editor with the worktree root and file path as arguments
- [ ] Editor resolution order: `--editor` CLI flag → `$EDITOR` environment variable → `"cursor"` default
- [ ] `e` keybinding in the app opens the currently highlighted file in the resolved editor
- [ ] Works when focus is on file tree or file viewer

### US-009: GitHub Service and PR Context Panel
As a developer, I want the PR tab to show review status, comments, and CI checks for the current branch's PR so that I can track PR progress without leaving the terminal.

**Acceptance Criteria:**
- [ ] `src/perch/models.py` extended with: `PRContext(title, number, url, review_decision, reviews, comments, checks)`, `PRReview(author, state, body, submitted_at)`, `PRComment(author, body, created_at)`, `CICheck(name, state, bucket, link, workflow)`
- [ ] `src/perch/services/github.py` implements `get_pr_context(root) → PRContext | None` parsing `gh pr view --json ...`
- [ ] `get_checks(root) → list[CICheck]` parses `gh pr checks --json ...`
- [ ] Returns `None` when no PR exists for the current branch
- [ ] `src/perch/widgets/pr_context.py` implements `PRContextPanel` with collapsible sections: PR header (title, number, review decision badge), Reviews, Comments, CI Checks
- [ ] Pressing `Enter` on a CI check opens `check.link` in the browser via `webbrowser.open()`
- [ ] Auto-refreshes every 30 seconds
- [ ] Shows "No PR open for this branch" when no PR exists
- [ ] Gracefully handles `gh` not installed or not authenticated (shows informative message)
- [ ] Replaces the "PR" tab placeholder from US-004

### US-010: Fuzzy File Search Modal
As a developer, I want to press `Ctrl+P` to open a fuzzy file search and jump to any file in the worktree so that I can navigate large projects quickly.

**Acceptance Criteria:**
- [ ] `src/perch/widgets/file_search.py` implements `FileSearchScreen` as a modal `Screen`
- [ ] On open, walks the worktree once and caches the file list (excludes `.git/`, `__pycache__/`, `node_modules/`, etc.)
- [ ] `Input` widget at the top for typing search queries
- [ ] `ListView` below shows ranked matches, updating live as the user types
- [ ] Matching uses fuzzy substring + character-order scoring (no external fzf dependency)
- [ ] `Enter` dismisses modal, loads selected file in `FileViewer`, and highlights it in the file tree
- [ ] `Escape` dismisses modal with no action
- [ ] `Ctrl+P` keybinding registered in `PerchApp`

### US-011: Command Palette
As a developer, I want a command palette (`Ctrl+Shift+P`) that lists all available commands with their hotkeys so that I can discover and execute actions.

**Acceptance Criteria:**
- [ ] Custom `DiscoveryCommandProvider` subclassing `textual.command.Provider`
- [ ] Yields entries for all app commands with their hotkey displayed alongside (e.g., "Open in Editor — e", "Fuzzy File Search — Ctrl+P")
- [ ] Registered as a `COMMAND_PROVIDERS` entry in `PerchApp`
- [ ] `Ctrl+Shift+P` opens the Textual `CommandPalette` with the custom provider
- [ ] Selecting a command executes the corresponding action

### US-012: Polish — Header, Footer, Edge Cases, and Packaging
As a developer, I want a polished TUI with an informative header, contextual footer, and graceful edge case handling so that the tool feels complete and robust.

**Acceptance Criteria:**
- [ ] Header displays: current branch name and worktree path
- [ ] Footer displays contextual hotkeys for the currently focused widget/tab (uses Textual's built-in `Footer` widget, spans full width below both panes)
- [ ] Edge case: launching outside a git repo shows a meaningful error or falls back to file-only mode (no git tab data, no PR tab data)
- [ ] Edge case: empty repository (no files) displays gracefully
- [ ] Edge case: `gh` CLI not installed shows informative message in PR tab only, rest of app works
- [ ] `pip install -e .` makes `perch` available as a CLI command
- [ ] End-to-end verification: launch `perch` in a real worktree with uncommitted changes and a PR, confirm all tabs work

## Functional Requirements
- FR-1: The application must launch via `perch [path]` where `path` defaults to the current directory
- FR-2: The file viewer must render any text file with syntax highlighting using Rich
- FR-3: The file tree must reflect the directory structure of the target worktree, excluding noise directories
- FR-4: Cursor movement in the file tree must immediately update the file viewer (no Enter required)
- FR-5: The splitter must be resizable via mouse drag and `[`/`]` keyboard shortcuts
- FR-6: The Git tab must show categorized file changes and recent commit history
- FR-7: The PR tab must show review status, comments, and CI check results from `gh` CLI
- FR-8: Pressing `e` must open the highlighted file in the user's preferred editor (non-blocking)
- FR-9: `Ctrl+P` must open a fuzzy file search that filters results as the user types
- FR-10: `Ctrl+Shift+P` must open a command palette listing all available commands
- FR-11: Git status must auto-refresh every 5 seconds; PR context every 30 seconds
- FR-12: The application must handle missing `git` or `gh` CLIs gracefully without crashing

## Non-Goals (Out of Scope)
- `--ref` flag for diffing against a specific branch (follow-up feature)
- File editing within the TUI (it's read-only; editing is delegated to the external editor)
- Custom color themes or theme switching
- Multi-repo or multi-worktree views in a single instance
- Integration with non-GitHub forges (GitLab, Bitbucket, etc.)
- Writing or staging git changes from within the TUI
- Plugin or extension system

## Technical Considerations
- **Framework**: Textual (Python TUI framework) with Rich for syntax highlighting
- **Python**: 3.12+ only
- **Build**: hatchling backend, managed with `uv`
- **External CLIs**: `git` (required for git features), `gh` (optional, for PR features)
- **No external fuzzy matching deps**: file search uses a simple built-in scoring algorithm
- **Background workers**: Textual's `@work(thread=True)` for auto-refresh to avoid blocking the UI event loop
- **Subprocess calls**: All git/gh interactions via `subprocess.run` / `subprocess.Popen`, isolated in `services/` modules with no Textual dependency for testability

## Success Metrics
- All TUI components render correctly in a standard terminal (256-color)
- Navigation between tree and viewer is instantaneous (no perceptible lag)
- Git status and PR context refresh reliably on their respective intervals
- `perch` launches in under 1 second on a typical project
- All quality gate commands pass: `uv run pytest && uv run ruff check && uv run ty`

## Open Questions
- Should `perch` support a config file (e.g., `~/.config/perch/config.toml`) for persisting preferences like default editor and excluded directories?
- Should vim-style `j`/`k` navigation be supported in all list widgets, or only in the file tree?