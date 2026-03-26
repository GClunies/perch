# Expandable Commit Review

## Problem

Selecting a commit in the git panel dumps the entire multi-file diff into the viewer as one monolithic blob. Users navigate between files with `n`/`p` keybindings, which is hidden and unintuitive. There is no way to see which files changed at a glance or jump to a specific file.

## Design

Treat commits like expandable folders in the sidebar using a Tree widget. Each commit can be expanded to reveal its changed files as child nodes. Selecting a child shows that file's diff in the viewer.

## Architecture: Compound GitPanel

GitPanel becomes a compound widget (`Vertical`) containing two internal widgets:

1. **File ListView** — `ListView` for unstaged/staged/untracked file sections (unchanged behavior)
2. **Commit Tree** — `Tree[str]` for commit history with native expand/collapse

The app interacts with GitPanel through delegate methods — it never touches the internal ListView or Tree directly.

### Node Data Convention (Tree[str])
- Commit nodes (root level): `"commit:<hash>"`
- File nodes (children): `"commit-file:<hash>:<path>"`
- Sentinel node: `"load-more-commits"`

### Cross-Widget Navigation
j/k auto-transfers focus between the file ListView and commit Tree at boundaries:
- Pressing j at the bottom of the file list → focus moves to the first commit in the tree
- Pressing k at the top of the commit tree → focus moves to the last file item in the list

This makes the two widgets feel like one continuous list to the user.

## Sidebar Behavior

### Collapsed Commit (Tree Node)
Native Tree chevron (`▸`) + hash + message. Highlighting shows a **summary card** in the viewer.

### Expanding (Enter/l)
- Native Tree expand — chevron flips, children appear indented
- **Accordion**: any previously expanded commit auto-collapses (via `toggle_commit()`)
- Viewer updates to show the summary card for the expanded commit

### Collapsing (Enter/l on expanded commit)
- Native Tree collapse — children hidden, chevron flips back
- If the viewer was showing a child file's diff (`_commit_file_context` set), reset to the commit's summary card

### Selecting a Child File (highlight)
- Viewer shows that file's diff within the commit (what that commit introduced, not the working-tree diff)

## GitPanel Delegate API

The app calls these methods — never the internal widgets:

- `highlighted_item_name() → str | None` — returns the name/data of the currently highlighted item (from either widget, whichever has focus)
- `toggle_commit(commit_hash)` — expand/collapse with accordion behavior
- `refresh_files()` — refresh file sections only
- `refresh_commits()` — refresh commit tree
- `refresh_all()` — force-refresh everything (bound to `r`)
- `focus_file_list()` / `focus_commit_tree()` — for tab restoration

### Messages (bubbled to app)
- `FileSelected(path, staged)` — unchanged, from the file ListView
- `CommitHighlighted(commit_hash)` — posted when a commit node is highlighted in the tree
- `CommitFileHighlighted(commit_hash, path)` — posted when a commit-file node is highlighted
- `CommitToggled(commit_hash)` — posted when Enter/l is pressed on a commit node

These replace the old event wiring where app.py had to inspect item names.

## Refresh Model

### File Sections (unstaged/staged/untracked)
- Keep the existing 5-second auto-refresh
- `refresh_files()` rebuilds only the file ListView without touching the commit tree

### Commits Section
- **Ref watcher** (primary): poll the mtime of `.git/refs/heads/<branch>` every 2-3 seconds. Fall back to `.git/HEAD` and `.git/packed-refs` for packed refs or detached HEAD. When a change is detected, call `refresh_commits()`.
- `refresh_commits()` rebuilds the commit tree. Preserves expanded state: if the expanded commit hash still exists, re-expand it with fresh children. Otherwise collapse.

### Manual Refresh (`r`)
- `r` calls `refresh_all()` — both file sections and commits.

## Commit History Pagination

### Initial Load
- Load first 50 commits as root nodes in the tree on mount

### Lazy Loading
- A leaf node `── more history ──` (data=`"load-more-commits"`) appears as the last root node when more commits exist
- When this node is highlighted, `_load_more_commits()` triggers automatically
- Loads the next page, removes the sentinel, appends new commit nodes + fresh sentinel if needed
- Guarded by `_loading_more` flag to prevent re-entrant calls

## Git Service (already implemented)

All git service functions are already implemented and tested:
- `get_commit_files(root, commit_hash) → list[CommitFile]`
- `get_commit_file_diff(root, commit_hash, path) → str`
- `get_commit_summary(root, commit_hash) → CommitSummary`
- `get_log(root, n, skip=0) → list[Commit]`

## Viewer (already implemented)

All viewer changes are already implemented and tested:
- `show_commit_summary(summary)` — renders commit summary card
- `load_commit_file_diff(commit_hash, path)` — renders single-file commit diff
- `check_action`, `action_toggle_diff`, `_load_diff`, `refresh_content` — all updated for `_commit_file_context`

## App Wiring

### Event Handling (`app.py`)

Replace the current `on_list_view_highlighted`/`on_list_view_selected` commit handling with handlers for the new GitPanel messages:

- `on_git_panel_commit_highlighted(event)` → `self._load_commit_summary(event.commit_hash)`
- `on_git_panel_commit_file_highlighted(event)` → `viewer.load_commit_file_diff(event.commit_hash, event.path)`
- `on_git_panel_commit_toggled(event)` → `panel.toggle_commit(event.commit_hash)`

The `on_list_view_highlighted`/`on_list_view_selected` handlers continue to handle file items from the file ListView only.

`_show_current_git_item()` uses `panel.highlighted_item_name()` and branches on the prefix.

## FileTree Refresh (already implemented)

`r` keybinding on FileTree — already implemented and tested.

## What Stays the Same

- Unstaged/staged/untracked file sections — display, behavior, auto-refresh
- File selection from those sections — `viewer.load_file()`, `viewer.show_deleted_file_diff()`
- Diff rendering — `render_diff()`, `parse_diff_sides()`, side-by-side toggle
- Tab switching — `_focus_active_tab()` restores state
- Viewer bindings — `d` (diff), `s` (layout), `e` (editor), `f` (focus), `hjkl` (scroll)
- GitHubPanel — untouched
- All git service functions
- All viewer methods

## What Gets Replaced

- GitPanel class hierarchy: `ListView` → `Vertical` (compound widget)
- ListView expand/collapse hacks: `toggle_commit`, `_expand_commit`, `_collapse_commit`, `_set_commit_chevron` → native Tree expand/collapse
- App event handlers for commits: name-string inspection → typed messages
