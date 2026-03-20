# Expandable Commit Review

## Problem

Selecting a commit in the git panel dumps the entire multi-file diff into the viewer as one monolithic blob. Users navigate between files with `n`/`p` keybindings, which is hidden and unintuitive. There is no way to see which files changed at a glance or jump to a specific file.

## Design

Treat commits like expandable folders in the sidebar. Each commit can be expanded to reveal its changed files as child items. Selecting a child shows that file's diff in the viewer.

## Sidebar Behavior

### Collapsed Commit
Displays: `▸ abc1234 fix login bug` (chevron + hash + message, existing styling plus expand indicator). Highlighting shows a **summary card** in the viewer.

### Expanding (Enter/l)
- Chevron flips to `▾`
- Indented child items appear below — one per changed file, styled with status color + path (matching existing file item styling)
- **Accordion**: any previously expanded commit auto-collapses
- Viewer updates to show the summary card for the expanded commit

### Collapsing (Enter/l on expanded commit)
- Children removed, chevron flips back to `▸`
- If the viewer was showing a child file's diff (`_commit_file_context` set), reset to the commit's summary card. This prevents stale state where the viewer references a sidebar item that no longer exists.

### Selecting a Child File (highlight)
- Viewer shows that file's diff within the commit (what that commit introduced, not the working-tree diff)

### Item Naming Convention
- Regular file items: `name=<path>` (unchanged)
- Commit items: `name="commit:<hash>"` (unchanged)
- Commit-child file items: `name="commit-file:<hash>:<path>"` (new)

## Refresh Model

### File Sections (unstaged/staged/untracked)
- Keep the existing 5-second auto-refresh
- Split `_do_refresh()` into `_refresh_file_status()` (auto, 5s timer) and `_refresh_commits()` (triggered)
- `_refresh_file_status()` rebuilds only the file sections (unstaged/staged/untracked) without touching commit items. The "Recent Commits" header item is given `name="section-commits"` so it can be located by name (not label text). `_refresh_file_status()` finds this item's index and replaces only items before it; commit items and any expanded children below it are left intact.

### Commits Section
- **Ref watcher** (primary): on mount, resolve the current branch via `get_current_branch()`. Poll the mtime of `.git/refs/heads/<branch>` every 2-3 seconds. If the ref file does not exist (packed refs after `git gc`, or detached HEAD), fall back to polling both `.git/HEAD` and `.git/packed-refs` mtimes. A change in either triggers a commit refresh. When the branch changes mid-session (detected via `.git/HEAD` mtime change), re-resolve the branch and update the watched path.
- When a ref change is detected, call `_refresh_commits()` which rebuilds commit items in place
- `_refresh_commits()` preserves expanded state: after rebuilding, if `_expanded_commit` hash still exists in the new commit list, re-expand it (re-fetch `get_commit_files` and re-insert children). If the hash is gone, set `_expanded_commit = None`.

### Manual Refresh (`r`)
- The existing `r` keybinding on GitPanel becomes a force-refresh of the entire panel: both file sections and commits. This serves as an escape hatch if the ref watcher or auto-refresh miss something.
- `r` means "refresh the current panel" — GitPanel refreshes files + commits, GitHubPanel refreshes PR data (unchanged).

## Commit History Pagination

### Initial Load
- Load first 50 commits on mount

### Lazy Loading
- A selectable sentinel item `── more history ──` (styled dim, `name="load-more-commits"`) appears at the bottom when more commits exist
- The sentinel is **selectable** (not disabled) so the cursor can land on it. When highlighted (`on_list_view_highlighted` sees `name="load-more-commits"`), trigger `_load_more_commits()` automatically
- `_load_more_commits()` calls `get_log(root, n=50, skip=_commits_loaded)`, removes the sentinel, appends new commit items, updates `_commits_loaded`, and appends a fresh sentinel if more history remains
- If `get_log` returns fewer than 50 results, all history is loaded — no sentinel appended

### Implementation
- `get_log(root, n, skip=0)` gains a `skip` parameter mapping to `git log --skip=N`
- GitPanel tracks `_commit_page_size = 50` and `_commits_loaded: int`

## Git Service Changes

### New Functions

**`get_commit_files(root, commit_hash) → list[CommitFile]`**
- Uses `git diff-tree --no-commit-id -r --name-status <hash>`
- Parses single-character status codes from git output (`M` → `"modified"`, `A` → `"added"`, `D` → `"deleted"`, `R{score}` → `"renamed"`, `C{score}` → `"copied"`). For renamed/copied files, the output has two paths (old and new); use the new path as `CommitFile.path` and store the old path in `CommitFile.old_path` (optional field, `None` for non-renames).

**`get_commit_file_diff(root, commit_hash, path) → str`**
- Uses `git show --no-color --format= <hash> -- <path>` (empty `--format=` to suppress commit metadata header, `--no-color` for clean output)
- Returns the raw unified diff for a single file within a commit

**`get_commit_summary(root, commit_hash) → CommitSummary`**
- Two separate git calls for clean parsing:
  1. `git show --no-color --format="%H\x1f%s\x1f%an\x1f%aI\x1f%b" -s <hash>` (`-s` suppresses diff output; `\x1f` unit separator between fields, matching the pattern used by `get_log`)
  2. `git show --no-color --stat --format= <hash>` (empty format, stat-only output)
- First call parsed by splitting on `\x1f` with `maxsplit=4` (the body field `%b` is last and may contain arbitrary text including `\x1f`); second call captured verbatim as `CommitSummary.stats`

### New Models

```python
@dataclass
class CommitFile:
    path: str               # e.g., "src/app.py" (new path for renames)
    status: str             # "added", "modified", "deleted", "renamed", "copied"
    old_path: str | None    # previous path for renames/copies, None otherwise

@dataclass
class CommitSummary:
    hash: str
    subject: str
    body: str
    author: str
    date: str               # ISO 8601 format
    stats: str              # raw --stat output for display
```

### Modified Functions

- `get_log(root, n, skip=0)` — add `skip` parameter for pagination

## Viewer Changes

### New Content Modes (Git Tab)

**Commit summary** — shown when a commit (collapsed or expanded) is highlighted:
- Commit hash, author, date, full message (subject + body)
- File stats block (raw `--stat` output rendered as Rich Text)
- Rendered with Rich styling

**Commit file diff** — shown when a commit-child file is highlighted:
- Single-file diff via existing `render_diff()` pipeline
- Border title: `<hash>:<filepath>`
- Side-by-side layout toggle (`s`) works — see note on `_load_diff` below

### New Methods

- `show_commit_summary(summary: CommitSummary)` — renders the summary card. Sets `_diff_mode = False`, `_current_path = None`, `_commit_file_context = None`. Stores `_current_summary = summary` for theme refresh.
- `load_commit_file_diff(commit_hash, path)` — fetches diff via `get_commit_file_diff()`, renders with `render_diff()`. Sets `_diff_mode = True`, `_current_path = None`, `_current_summary = None`. Stores `_commit_file_context = (commit_hash, path)` for layout toggle support.

### Layout Toggle Support

The existing `action_toggle_diff_layout` calls `_load_diff()`, which currently reads `_current_path` and calls `get_diff()`. This must be updated: when `_commit_file_context` is set (i.e., viewing a commit-file diff), `_load_diff()` should call `get_commit_file_diff(hash, path)` instead of `get_diff(path)`. When `_commit_file_context` is `None`, existing behavior is unchanged.

### Theme Refresh

`refresh_content()` (called by `watch_theme`) must handle the new modes. When `_commit_file_context` is set, re-call `load_commit_file_diff()`. When showing a commit summary, re-call `show_commit_summary()` — store the current `CommitSummary` in `_current_summary` so it can be re-rendered without re-fetching.

### check_action Updates

`check_action("toggle_diff")` currently returns `self._current_path is not None`. Since `load_commit_file_diff` sets `_current_path = None`, this must be updated to also return `True` when `_commit_file_context is not None`.

### action_toggle_diff Update

The existing `action_toggle_diff` calls `self.load_file(self._current_path)` in the "off" branch (toggling back to file view). When `_commit_file_context` is set, `_current_path` is `None` — there is no file view to return to. Fix: when `_commit_file_context` is set, pressing `d` should show the commit summary card instead of calling `load_file`. Specifically: if `_commit_file_context` is set and toggling off, call `show_commit_summary(_current_summary)` (the summary is cached). If `_commit_file_context` is `None`, existing behavior is unchanged.

### Removed

- `load_commit_diff()` method
- `_diff_file_offsets`, `_diff_file_index`, `_scroll_to_diff_file()`
- `action_next_diff_file()`, `action_prev_diff_file()`
- `n`/`p` bindings
- `_current_commit` state variable

## App Wiring

### Event Handling (`app.py`)

**`on_list_view_highlighted()`** — when on git tab:
- Commit item → `viewer.show_commit_summary()`
- Commit-child file → `viewer.load_commit_file_diff()`
- Sentinel (`load-more-commits`) → trigger `git_panel._load_more_commits()`
- Regular file item → existing behavior (unchanged)

**`on_list_view_selected()`** (Enter/l):
- Commit item → `git_panel.toggle_commit(hash)` (expand/collapse)
- Commit-child file → focus viewer
- Regular file → focus viewer (unchanged)

**`_show_current_git_item()`** — updated to handle three item types (file, commit, commit-child)

### GitPanel Message Cleanup

Remove `CommitSelected` message and `on_list_view_selected` handling for commits inside GitPanel. Commit toggle is now driven by `app.py` calling `git_panel.toggle_commit()`. The existing `GitPanel.on_list_view_selected` handler for file items (posting `FileSelected`) remains unchanged.

### New GitPanel API

- `toggle_commit(commit_hash)` — expands or collapses, manages accordion. On expand: calls `get_commit_files()`, inserts child items after the commit item. On collapse: removes child items.
- `_expanded_commit: str | None` — tracks currently expanded commit hash
- `_load_more_commits()` — pagination loader, appends next page of commits. Uses `@work(thread=True)` for the `get_log` call (consistent with all other git calls in the codebase). Guarded by `_loading_more: bool` flag — set `True` synchronously in the calling (main) thread before dispatching the worker, set `False` after items are inserted in the `call_from_thread` callback. This prevents the highlight event from re-triggering before the worker completes.

## FileTree Refresh

Add `r` keybinding to FileTree for consistency — "refresh the current panel" works on all three tabs. `r` triggers `reload()` on the underlying DirectoryTree to re-scan the filesystem. Preserves the current cursor position and expanded directories where possible.

## What Stays the Same

- Unstaged/staged/untracked file sections — display, behavior, auto-refresh
- File selection from those sections — `viewer.load_file()`, `viewer.show_deleted_file_diff()`
- Diff rendering — `render_diff()`, `parse_diff_sides()`, side-by-side toggle
- Tab switching — `_focus_active_tab()` restores state
- Viewer bindings — `d` (diff), `s` (layout), `e` (editor), `f` (focus), `hjkl` (scroll)
- GitHubPanel — untouched
