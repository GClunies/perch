# `perch` — A Vantage Point for Agentic Workflows

## Context

A custom Python TUI for terminal-centric agentic workflows (cmux + worktrunk + ralph-tui). No existing tool provides the exact layout needed: file viewer on the left, tabbed file tree + git context + PR context on the right, with a mouse-draggable boundary. Building from scratch with Textual.

**Name**: `perch` (alias: `pc`)
**Location**: `~/repos/perch` (new standalone repo, pip-installable)

---

## Layout

```
┌──────────────────────────────┐│┌─[Files]──[Git]──[PR]────────┐
│                              │││                              │
│  File Viewer                 │││  (active tab content)        │
│  (syntax highlighted)        │││                              │
│                              │││  File Tree / Git Status /    │
│                              │││  PR Context                  │
│                              │││                              │
│  60% width (resizable)       │││  40% width (resizable)       │
└──────────────────────────────┘│└──────────────────────────────┘
                                ↑
                         draggable splitter
```

- **Left pane**: File viewer with syntax highlighting
- **Right pane**: 3 tabs:
  1. **Files** — Directory tree. Navigating highlights update the viewer. Hotkey opens file in editor.
  2. **Git** — Unstaged/Staged/Untracked files, recent commits (stacked vertically)
  3. **PR** — Review status, comments, CI checks (clicking a check opens browser to CI run)
- **Splitter**: 1-col wide, mouse-draggable. Also resizable with `[`/`]` keys.

---

## Project Structure

```
~/repos/perch/
├── pyproject.toml
├── src/
│   └── perch/
│       ├── __init__.py              # __version__
│       ├── __main__.py              # python -m perch
│       ├── cli.py                   # argparse: perch [path] [--editor] [--ref]
│       ├── app.py                   # PerchApp(App) — compose, bindings, handlers
│       ├── app.tcss                 # Textual CSS layout
│       ├── models.py                # Dataclasses: GitFile, Commit, PRContext, CICheck
│       ├── widgets/
│       │   ├── __init__.py
│       │   ├── file_viewer.py       # Left pane: syntax-highlighted file display
│       │   ├── splitter.py          # Draggable vertical splitter (mouse capture)
│       │   ├── file_tree.py         # DirectoryTree subclass
│       │   ├── git_status.py        # Git tab: staged/unstaged/untracked + commits
│       │   ├── pr_context.py        # PR tab: reviews, comments, CI checks
│       │   └── file_search.py      # Ctrl+P fuzzy file search modal (~70 lines)
│       └── services/
│           ├── __init__.py
│           ├── git.py               # subprocess wrapper for git CLI
│           ├── github.py            # subprocess wrapper for gh CLI
│           └── editor.py            # subprocess.Popen to launch editor
```

**~1,500 lines total** (Python + CSS).

---

## Module Architecture

### `models.py` (~50 lines)
Dataclasses shared across modules:
- `GitFile(path, status, staged)` — single file's git status
- `GitStatusData(unstaged, staged, untracked)` — grouped file lists
- `Commit(hash, message, author, relative_time)`
- `PRContext(title, number, url, review_decision, reviews, comments, checks)`
- `PRReview(author, state, body, submitted_at)`
- `PRComment(author, body, created_at)`
- `CICheck(name, state, bucket, link, workflow)`

### `services/git.py` (~120 lines)
All git subprocess calls. No Textual dependency.
- `get_worktree_root(path) → Path`
- `get_status(root) → GitStatusData` — parses `git status --porcelain=v1`
- `get_log(root, n=15) → list[Commit]` — parses `git log --format="%h|%s|%an|%ar"`
- `get_current_branch(root) → str`

### `services/github.py` (~100 lines)
All gh CLI calls. Returns `None` if no PR exists.
- `get_pr_context(root) → PRContext | None` — parses `gh pr view --json title,number,url,state,reviewDecision,reviews,comments,statusCheckRollup`
- `get_checks(root) → list[CICheck]` — parses `gh pr checks --json name,state,bucket,link,workflow`

### `services/editor.py` (~30 lines)
- `open_file(editor, file_path, worktree_root)` — `subprocess.Popen([editor, str(worktree_root), str(file_path)])` (non-blocking)
- Editor resolved from: `--editor` flag → `$EDITOR` env → `"cursor"` default

### `widgets/file_viewer.py` (~90 lines)
Left pane. Uses `rich.syntax.Syntax.from_path()` for auto language detection.
- `load_file(path)` — read file, render with syntax highlighting + line numbers
- Binary detection (check for null bytes in first 8KB)
- Large file cap (~10,000 lines with truncation warning)

### `widgets/splitter.py` (~80 lines)
Custom widget using Textual's mouse capture API:
- `on_mouse_down` → `capture_mouse()`, start tracking
- `on_mouse_move` → adjust left pane `styles.width` based on delta
- `on_mouse_up` → `release_mouse()`
- Renders as `│`, highlights on hover

### `widgets/file_tree.py` (~60 lines)
Subclass of `textual.widgets.DirectoryTree`:
- `filter_paths()` — exclude `.git/`, `__pycache__/`, `.DS_Store`
- App handles `on_tree_node_highlighted` (not `FileSelected`) so cursor movement instantly updates the viewer — no Enter required

### `widgets/git_status.py` (~180 lines)
Tab 2 content. Uses `Collapsible` containers stacked in `VerticalScroll`:
- 3 collapsible sections: Unstaged, Staged, Untracked (each with `ListView`)
- `DataTable` for recent commits (columns: Hash, Message, Author, When)
- Auto-refreshes every 5s via `@work(thread=True)` background worker

### `widgets/pr_context.py` (~160 lines)
Tab 3 content. Uses `Collapsible` containers:
- PR header (title, number, review decision badge)
- Reviews list (author, state, body excerpt)
- Comments list (author, body, time)
- CI Checks list — on `Enter`, opens `check.link` in browser via `webbrowser.open()`
- Auto-refreshes every 30s. Shows "No PR open for this branch" when applicable.
- Gracefully handles `gh` not installed or not authenticated.

### `widgets/file_search.py` (~70 lines)
Modal screen for fuzzy file search (`Ctrl+P`):
- Walks worktree once on open, caches file list
- `Input` widget with live filtering as you type
- `ListView` of ranked matches (fuzzy substring + char-order scoring)
- `Enter` → dismiss modal, load selected file in viewer + highlight in tree
- `Escape` → dismiss modal, no action
- Excludes `.git/`, `__pycache__/`, `node_modules/`, etc.

### `app.py` (~140 lines)
Composes the full widget tree:

```
PerchApp
├── Header (branch name | worktree path)
├── Horizontal#main
│   ├── FileViewer#file-viewer
│   ├── DraggableSplitter
│   └── TabbedContent#right-pane
│       ├── TabPane "Files" → WorktreeFileTree
│       ├── TabPane "Git"   → GitStatusPanel
│       └── TabPane "PR"    → PRContextPanel
├── Footer (contextual hotkey bar — spans full width of both panes)
└── Screens:
    └── FileSearchScreen (Ctrl+P modal overlay)
```

Also registers a custom `CommandProvider` for the command palette (`Ctrl+Shift+P`) that lists all commands with their hotkeys.

### `app.tcss` (~80 lines)
```css
#file-viewer { width: 60%; min-width: 20; }
#right-pane  { width: 1fr; min-width: 25; }
DraggableSplitter { width: 1; }
```

---

## Key Bindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `e` | Open highlighted file in external editor |
| `r` | Force refresh active tab data |
| `[` / `]` | Shrink / grow left pane by 2 cols |
| `1` / `2` / `3` | Switch to Files / Git / PR tab |
| `Tab` / `Shift+Tab` | Cycle focus between panes |
| `j` / `k` | Vim-style navigation in tree and lists |
| `Enter` | Expand/collapse dir (tree), open CI URL (checks) |
| `Ctrl+P` | Fuzzy file search (jump to any file in the worktree) |
| `Ctrl+Shift+P` | Command palette (lists all commands with their hotkeys) |

### Footer / Hotkey Bar

A persistent footer bar spans the **full width** of both panes (below the splitter). It displays contextual hotkeys for the currently focused widget/tab. Uses Textual's built-in `Footer` widget, which auto-renders `BINDINGS` from the active widget chain.

### Fuzzy File Search (`Ctrl+P`)

Opens a modal overlay with:
- An `Input` widget at the top for typing a search query
- A filtered `ListView` below showing matching file paths (fuzzy match)
- Results update as you type
- `Enter` selects the file → loads in FileViewer + highlights in tree
- `Escape` closes the search

Implementation: A custom `Screen` (modal) that walks the worktree file list, scores matches using a simple fuzzy algorithm (substring + character-order matching), and renders ranked results. No external dependency on fzf — keeps it self-contained.

### Command Palette (`Ctrl+Shift+P`)

Opens Textual's built-in `CommandPalette` with a custom `DiscoveryCommandProvider` that lists all available commands alongside their hotkeys. Each entry shows:
```
Open in Editor                    e
Refresh                           r
Fuzzy File Search             Ctrl+P
Switch to Files Tab               1
Switch to Git Tab                 2
Switch to PR Tab                  3
```

Implementation: Subclass `textual.command.Provider`, yield `DiscoveryHit` entries for each action. Textual's `CommandPalette` handles the fuzzy filtering and keyboard navigation.

---

## CLI Usage

```bash
perch                    # current dir, editor from $EDITOR or "cursor"
perch /path/to/worktree  # explicit path
perch --editor code      # override editor
perch --ref main         # diff against main instead of HEAD
```

---

## Implementation Phases

### Phase 1: Skeleton + File Viewer (~2 hrs)
- Create project structure, `pyproject.toml`, entry points
- Basic `app.py` with `Horizontal` layout, `FileViewer`, placeholder right pane
- `FileViewer` renders files with `rich.syntax.Syntax.from_path()`
- CSS for 60/40 split
- **Verify**: `uv run perch` shows two-pane layout, hardcoded file displays with highlighting

### Phase 2: File Tree + Cursor Tracking (~2 hrs)
- `WorktreeFileTree(DirectoryTree)` with `filter_paths`
- `TabbedContent` with 3 tabs (Files populated, Git/PR as placeholders)
- Wire `on_tree_node_highlighted` → update `FileViewer`
- **Verify**: navigate tree with arrows, file viewer updates in real-time

### Phase 3: Draggable Splitter (~1 hr)
- `DraggableSplitter` widget with mouse capture
- `[`/`]` keyboard resize
- **Verify**: drag boundary with mouse, resize with keyboard

### Phase 4: Git Status Tab (~2 hrs)
- `models.py` dataclasses
- `services/git.py` (status parsing, log parsing)
- `GitStatusPanel` with collapsible sections + commit table
- 5s auto-refresh via background worker
- **Verify**: Tab 2 shows real unstaged/staged/untracked files + commits

### Phase 5: Editor Integration (~30 min)
- `services/editor.py`
- Wire `e` hotkey → opens file in editor (Cursor by default)
- `--editor` CLI flag + `$EDITOR` fallback
- **Verify**: press `e`, Cursor opens with the worktree + file

### Phase 6: PR Context Tab (~2 hrs)
- `services/github.py` (gh pr view, gh pr checks)
- `PRContextPanel` with reviews, comments, CI checks
- CI check `Enter` → `webbrowser.open(link)`
- 30s auto-refresh, "No PR" fallback
- **Verify**: Tab 3 shows PR status, click CI check opens browser

### Phase 7: File Search + Command Palette (~1.5 hrs)
- `widgets/file_search.py` — fuzzy file search modal (`Ctrl+P`)
- Custom `CommandProvider` for command palette (`Ctrl+Shift+P`)
- Wire both to app bindings
- **Verify**: `Ctrl+P` opens search, type to filter, Enter loads file. `Ctrl+Shift+P` shows all commands with hotkeys.

### Phase 8: Polish + Packaging (~1 hr)
- Header: branch name + path
- Footer: contextual hotkey bar spanning full width
- Edge cases: no git, no gh, binary files, large files, empty repo
- `pip install -e .` → `perch` available as CLI
- **Verify**: end-to-end in a real worktree

**Total: ~12-14 hrs across ~18 sessions**

---

## Verification (end-to-end)

1. `cd` into a worktree with uncommitted changes
2. `perch` — two panes appear, splitter in the middle
3. Drag splitter with mouse — panes resize
4. **Files tab**: navigate tree → file viewer updates with syntax highlighting
5. Press `e` → Cursor opens with the file
6. **Git tab**: unstaged/staged/untracked files visible in collapsible sections, commits in table
7. **PR tab**: if PR exists, shows reviews + comments + CI checks
8. Click a CI check → browser opens to the run URL
9. Press `r` → data refreshes
10. `perch --ref main` → git status compares against main
