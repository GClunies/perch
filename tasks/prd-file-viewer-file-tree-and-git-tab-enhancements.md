# PRD: File Viewer, File Tree, and Git Tab Enhancements

## Overview
Perch is a Textual TUI for browsing git worktrees. Three areas need improvement: the file viewer ignores the app theme and has no diff support, the file tree shows no git status indicators, and the git status panel is display-only with no interactivity or connection to the file viewer. This epic adds theme-aware syntax highlighting, inline diff viewing with toggle between unified and side-by-side layouts, git status indicators on the file tree with filesystem watching, and interactive navigation in the git tab that links file selection to the file viewer.

## Goals
- File viewer syntax highlighting respects the current app theme (light/dark)
- Users can view diffs inline in the file viewer and toggle between unified and side-by-side layouts
- File tree shows color-coded git status indicators (M, A, D, ?) next to each file
- File tree git status updates automatically via filesystem watching (no polling)
- Git tab sections (Unstaged, Staged, Untracked) are always visible and scrollable
- Selecting a file in the git tab opens it in the file viewer
- Deleted files in the git tab show a message with an option to view the diff

## Quality Gates

These commands must pass for every user story:
- `uv run pytest` — All tests pass
- `uv run ruff check src tests` — No lint issues
- `uv run ty check src tests` — Type checking passes

## User Stories

### US-001: Git Service — Diff and Status Dict Functions
As a developer, I want `get_diff()` and `get_status_dict()` functions in the git service so that other widgets can retrieve diff text and file statuses efficiently.

**Acceptance Criteria:**
- [ ] `get_diff(root, path, staged=False) -> str` runs `git diff [--cached] -- <path>` and returns raw unified diff text
- [ ] `get_status_dict(root) -> dict[str, str]` wraps existing `get_status()` and returns `{relative_path: status_label}` flat dict for O(1) lookup
- [ ] Tests added in `tests/test_git_service.py` following existing `TestParseStatus`/`TestParseLog` patterns
- [ ] Tests cover: modified file diff, staged file diff, empty diff (clean file), status dict with mixed statuses

### US-002: File Viewer — Theme-Aware Syntax Highlighting
As a user, I want the file viewer syntax colors to match my current app theme so that the viewer is readable in both light and dark modes.

**Acceptance Criteria:**
- [ ] `_get_syntax_theme() -> str` method checks `self.app.current_theme.dark` and returns appropriate Pygments theme (e.g., `"monokai"` for dark, `"default"` for light)
- [ ] `Syntax()` in `load_file()` uses `theme=self._get_syntax_theme()`
- [ ] File viewer re-renders when the app theme changes (app calls `viewer.load_file(viewer._current_path)` from `watch_theme`)
- [ ] `watch_theme()` method added to `app.py` to trigger re-render

### US-003: File Viewer — Unified Diff View
As a user, I want to press a key to toggle diff mode in the file viewer so that I can see what changed in a file without leaving the TUI.

**Acceptance Criteria:**
- [ ] `worktree_root: Path | None = None` param added to `FileViewer.__init__()`, app passes it in `compose()`
- [ ] `_diff_mode: bool = False` attribute tracks whether diff is shown
- [ ] Pressing `d` toggles between normal file view and diff view
- [ ] Diff view uses `rich.syntax.Syntax` with `"diff"` lexer and theme-aware coloring
- [ ] `+` lines render green, `-` lines render red
- [ ] Diff renders in the existing content area with line numbers
- [ ] When no diff exists (clean file), shows a message "No changes"

### US-004: File Viewer — Side-by-Side Diff Layout
As a user, I want to toggle between unified and side-by-side diff layouts so that I can choose the view that works best for me.

**Acceptance Criteria:**
- [ ] `_diff_layout: str = "unified"` attribute tracks current layout
- [ ] Pressing `s` while in diff mode toggles between unified and side-by-side
- [ ] Side-by-side layout renders old file on left, new file on right in a `Horizontal` container
- [ ] A hidden `Horizontal` container (`#diff-container`) with `#diff-left` and `#diff-right` children is added
- [ ] Toggle switches `display` between the main content area and the diff container
- [ ] Side-by-side view parses unified diff into left/right text panels
- [ ] Both panels scroll together (or independently — whichever is simpler)

### US-005: File Tree — Git Status Indicators
As a user, I want to see color-coded git status letters next to files in the file tree so that I can quickly identify modified, added, and deleted files.

**Acceptance Criteria:**
- [ ] `_git_status: dict[str, str] = {}` attribute stores current status lookup
- [ ] `render_label()` overridden to append a color-coded letter after the file name
- [ ] Status codes: `M` (modified/yellow), `A` (added/green), `D` (deleted/red), `R` (renamed/blue), `?` (untracked/dim)
- [ ] Colors match existing `_STATUS_STYLES` in `git_status.py`
- [ ] Relative path computed from `node.data.path` for lookup in `_git_status`
- [ ] Files with no git changes show no indicator

### US-006: File Tree — Filesystem Watching for Auto-Refresh
As a user, I want the file tree git status indicators to update automatically when files change so that I always see current status without manual refresh.

**Acceptance Criteria:**
- [ ] `watchfiles` library added to project dependencies
- [ ] File tree uses `watchfiles` to watch the worktree directory for changes
- [ ] When a filesystem change is detected, `get_status_dict()` is re-fetched and `_git_status` updated
- [ ] Tree labels re-render after status update
- [ ] Watching runs in a background worker thread (not blocking the UI)
- [ ] Watcher is stopped when the widget is unmounted

### US-007: Git Tab — Interactive ListView Sections
As a user, I want the git tab file sections to be scrollable lists so that I can navigate through files and select them.

**Acceptance Criteria:**
- [ ] Unstaged, Staged, and Untracked sections use `ListView` with `ListItem` widgets instead of `Label`
- [ ] Each `ListItem` stores the file path in its `name` attribute and displays styled status + path
- [ ] All three sections are always visible (no collapsible containers)
- [ ] Sections are vertically scrollable
- [ ] Commits section remains as a `DataTable` (unchanged)
- [ ] CSS styles added: `GitStatusPanel ListView { height: auto; max-height: 15; }` and `GitStatusPanel ListItem { height: 1; }`

### US-008: Git Tab — File Selection Links to File Viewer
As a user, I want to select a file in the git tab and have it open in the file viewer so that I can quickly inspect changed files.

**Acceptance Criteria:**
- [ ] `GitStatusPanel.FileSelected(Message)` custom message defined with `path: str` and `staged: bool` attributes
- [ ] `on_list_view_selected()` handler in `GitStatusPanel` posts `FileSelected` message
- [ ] `on_git_status_panel_file_selected()` handler in `app.py` calls `FileViewer.load_file(worktree_path / event.path)`
- [ ] Selecting a modified/added file opens it in the file viewer
- [ ] Selecting a deleted file shows a message "File deleted" with an option to view the diff

### US-009: Git Tab — Refresh Stability
As a user, I want the git tab to preserve my cursor position when it auto-refreshes so that I don't lose my place.

**Acceptance Criteria:**
- [ ] Before clearing/repopulating ListViews on refresh, the current cursor index is saved
- [ ] After repopulation, cursor index is restored (clamped to list bounds if items were removed)
- [ ] If the previously selected file is still in the list, it remains selected
- [ ] Refresh does not cause visible flicker or scroll jumping

### US-010: CSS and Command Palette Updates
As a user, I want diff commands available in the command palette and proper styling for new widgets.

**Acceptance Criteria:**
- [ ] "Toggle Diff View" command added to `commands.py`
- [ ] "Toggle Diff Layout" command added to `commands.py`
- [ ] CSS for `#diff-container` added: `layout: horizontal; height: 1fr;`
- [ ] CSS for `#diff-left, #diff-right` added: `width: 1fr; height: 100%;`
- [ ] All new widgets render correctly in both light and dark themes

## Functional Requirements
- FR-1: `get_diff()` must run `git diff [--cached] -- <path>` and return raw unified diff text
- FR-2: `get_status_dict()` must return a flat `{relative_path: status_label}` dict for O(1) lookup
- FR-3: File viewer must select Pygments theme based on `app.current_theme.dark`
- FR-4: File viewer must re-render when the app theme changes
- FR-5: Pressing `d` in the file viewer must toggle between normal and diff mode
- FR-6: Pressing `s` in diff mode must toggle between unified and side-by-side layout
- FR-7: Diff rendering must use `rich.syntax.Syntax` with the `"diff"` lexer (no external dependencies)
- FR-8: File tree must display color-coded status letters (M/A/D/R/?) next to file names
- FR-9: File tree status must auto-update via `watchfiles` filesystem watching
- FR-10: Git tab file sections must be scrollable `ListView` widgets, always visible (not collapsible)
- FR-11: Selecting a file in the git tab must open it in the file viewer
- FR-12: Deleted files in the git tab must show a "File deleted" message with option to view diff
- FR-13: Git tab auto-refresh must preserve cursor position

## Non-Goals (Out of Scope)
- Word-level (character-level) diff highlighting within changed lines
- Custom color scheme configuration for diffs
- Git staging/unstaging actions from the TUI (read-only for now)
- Git commit functionality from within the TUI
- System theme auto-detection
- Keybindings for jumping between git tab sections (`u`/`s`/`t`)
- Collapsible sections in the git tab

## Technical Considerations
- `watchfiles` is a well-maintained Python library wrapping OS-level filesystem events (inotify/FSEvents/ReadDirectoryChanges) — add to `pyproject.toml` dependencies
- `rich.syntax.Syntax` with `"diff"` lexer is zero-extra-deps since Textual already depends on Rich
- Side-by-side diff parsing: split unified diff on `+`/`-` line prefixes to build left/right panels
- Background workers (`@work(thread=True)`) must be used for filesystem watching and git commands to avoid blocking the UI event loop
- `FileSelected` message follows Textual's custom message pattern for widget-to-app communication

## Success Metrics
- All existing tests continue to pass
- New tests cover git service functions, diff rendering logic, and status dict generation
- File viewer renders correctly in both light and dark themes
- Diff view shows meaningful colored output for modified files
- File tree status indicators match `git status` output
- Filesystem watching triggers updates within ~1 second of file changes
- Git tab preserves cursor position across refreshes

## Open Questions
- Should the side-by-side diff panels scroll independently or in sync?
- What Pygments theme pairs work best for Perch's light and dark themes?
- Should there be a max file size limit for diff rendering to avoid performance issues?