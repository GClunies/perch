# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Git service pattern**: Functions in `src/perch/services/git.py` use `_run_git()` helper (subprocess wrapper), check `returncode`, raise `RuntimeError` on failure, return parsed data.
- **Test pattern**: Tests in `tests/test_git_service.py` use pytest class-based structure. Pure parsing tests need no mocking. Integration tests that need a real git repo use `tmp_path` fixture with a `_make_repo()` helper that creates a minimal repo with initial commit.

---

## 2026-03-16 - perch-54y.1
- Added `get_diff(root, path, staged=False) -> str` to git service — runs `git diff [--cached] -- <path>`
- Added `get_status_dict(root) -> dict[str, str]` to git service — wraps `get_status()` into flat `{path: status}` dict
- Files changed: `src/perch/services/git.py`, `tests/test_git_service.py`
- **Learnings:**
  - `_run_git()` uses `check=False` so callers must check `returncode` manually
  - `get_status()` returns `GitStatusData` with separate `staged`/`unstaged`/`untracked` lists; `get_status_dict()` flattens these with unstaged winning for duplicates
  - Integration tests with real git repos are simple via `tmp_path` + subprocess calls
---

## 2026-03-16 - perch-54y.2
- Added `_get_syntax_theme()` method to `FileViewer` — returns `"monokai"` for dark themes, `"default"` for light
- Updated `Syntax()` call in `load_file()` to use `theme=self._get_syntax_theme()`
- Added `watch_theme()` watcher to `PerchApp` — re-renders file viewer when theme changes
- Files changed: `src/perch/widgets/file_viewer.py`, `src/perch/app.py`
- **Learnings:**
  - Textual's `watch_<reactive>` methods auto-fire when a reactive attribute changes; `theme` is reactive on `App`
  - `self.app.current_theme.dark` is the canonical way to check light/dark mode from a widget
  - Wrapping theme check in try/except handles the case where the widget isn't yet mounted
---

## 2026-03-16 - perch-54y.3
- Added `worktree_root: Path | None = None` param to `FileViewer.__init__()`, app passes it in `compose()`
- Added `_diff_mode: bool = False` attribute and `d` key binding to toggle diff view
- Added `_load_diff()` method — gets relative path, calls `get_diff()`, renders with `Syntax("diff")` lexer
- Shows "No changes" message for clean files
- `load_file()` resets `_diff_mode` when navigating to a new file
- `watch_theme()` in app.py respects diff mode during re-render
- Files changed: `src/perch/widgets/file_viewer.py`, `src/perch/app.py`
- **Learnings:**
  - Textual `Binding("d", "action_name", "Label", show=False)` keeps binding off the footer
  - `rich.syntax.Syntax` with `"diff"` lexer handles `+`/`-` line coloring automatically (green/red)
  - Lazy import of `get_diff` inside `_load_diff()` avoids circular import issues
  - Pre-existing flaky test: `test_splitter_width_is_one` intermittently fails; `test_has_tabbed_content` fails due to `GitStatusPanel` `#git-header` query in non-git worktree
---

## 2026-03-16 - perch-54y.4
- Added `_diff_layout: str = "unified"` attribute and `s` key binding to toggle between unified and side-by-side diff
- Added `parse_diff_sides()` module-level function to split unified diff into left/right panel text with blank-line padding for alignment
- Added `#diff-container` (Horizontal) with `#diff-left` and `#diff-right` (VerticalScroll) children in `compose()`
- Added `_show_content_view()` and `_show_side_by_side_view()` helper methods to toggle display between content and diff container
- Updated `_load_diff()` to dispatch to side-by-side or unified based on `_diff_layout`
- `load_file()` resets `_diff_layout` to "unified" when navigating to a new file
- Added CSS for `#diff-container`, `#diff-left`, `#diff-right` to `app.tcss`
- Added 8 tests for `parse_diff_sides` in `test_file_viewer.py`
- Files changed: `src/perch/widgets/file_viewer.py`, `src/perch/app.tcss`, `tests/test_file_viewer.py`
- **Learnings:**
  - Textual `compose()` supports `with Container():` context manager syntax for nesting widgets
  - Side-by-side diff panels scroll independently (each is its own `VerticalScroll`), which is simpler than synced scrolling
  - `parse_diff_sides` pads with empty strings so both sides always have the same line count for visual alignment
  - `display = False` / `display = True` is the standard Textual pattern for showing/hiding widgets
---

## 2026-03-16 - perch-54y.5
- Added `_git_status: dict[str, str]` attribute to `WorktreeFileTree` for O(1) status lookup
- Overrode `render_label()` to append color-coded git status letter (M/A/D/R/C/U/T/?) after file names
- Colors match `_STATUS_STYLES` in `git_status.py`: modified=yellow, added=green, deleted=red, renamed=cyan, untracked=dim
- Added `_refresh_file_tree_status()` background worker in `app.py` to populate `_git_status` from `get_status_dict()` on mount
- Files changed: `src/perch/widgets/file_tree.py`, `src/perch/app.py`
- **Learnings:**
  - `DirectoryTree.render_label(node, base_style, style)` returns a `rich.text.Text` — call `super()` first, then `label.append()` to add indicators
  - `node._allow_expand` distinguishes directories from files; `node.data.path` gives the absolute path
  - `path.relative_to(self.path)` converts absolute node path to relative for `_git_status` dict lookup
  - `root.refresh()` triggers re-render of the entire tree after status update
---

## 2026-03-16 - perch-54y.6
- Added `watchfiles>=1.0.0` to project dependencies
- Moved git status refresh logic from `app.py` into `WorktreeFileTree` widget for self-contained lifecycle
- Added `_watch_filesystem()` background worker using `watchfiles.watch()` with `stop_event` for clean shutdown
- Initial status fetch happens in the same worker before entering the watch loop
- Watcher starts on `on_mount()`, stops on `on_unmount()` via `threading.Event`
- Removed `_refresh_file_tree_status` and `_apply_file_tree_status` from `app.py` (no longer needed)
- Files changed: `pyproject.toml`, `src/perch/widgets/file_tree.py`, `src/perch/app.py`
- **Learnings:**
  - `watchfiles.watch()` accepts a `stop_event` (threading.Event) for clean shutdown from background threads
  - `watchfiles.DefaultFilter` already excludes `.git`, `__pycache__`, `node_modules`, etc. — no custom filter needed
  - Default debounce is 1600ms which batches rapid filesystem changes nicely
  - Moving watching logic into the widget itself (vs. app) gives cleaner lifecycle management via `on_mount`/`on_unmount`
---

## 2026-03-16 - perch-54y.7
- Replaced `Collapsible` + `Label` with `Static` section headers + `ListView`/`ListItem` for Unstaged, Staged, and Untracked file sections
- Added `_make_list_item()` helper to create `ListItem` with styled status + path and `name=f.path`
- Commits section remains unchanged (`Collapsible` + `DataTable`)
- Added CSS: `GitStatusPanel ListView { height: auto; max-height: 15; }`, `GitStatusPanel ListItem { height: 1; }`, `.section-header` styling
- `_show_not_git_repo` updated to hide `ListView` widgets and section headers instead of `Collapsible`
- Files changed: `src/perch/widgets/git_status.py`, `src/perch/app.tcss`
- **Learnings:**
  - `ListView.clear()` removes all items; `ListView.append()` adds items — simpler than recreating the widget
  - `ListItem(Label(text), name=path)` stores the file path in `.name` for later retrieval when handling selection
  - `_render_file_list` is still exported for backward compat with existing tests but no longer used by the widget itself
  - Section headers as `Static` with a CSS class are simpler than `Collapsible(collapsed=False)` for always-visible sections
---

## 2026-03-16 - perch-54y.8
- Added `GitStatusPanel.FileSelected(Message)` custom message with `path: str` and `staged: bool` attributes
- Added `on_list_view_selected()` handler in `GitStatusPanel` that posts `FileSelected` message, determining `staged` from parent ListView id
- Added `on_git_status_panel_file_selected()` handler in `app.py` that opens selected file in viewer
- Deleted files show "File deleted — showing diff" header with diff content, or "no diff available" if no diff exists
- Files changed: `src/perch/widgets/git_status.py`, `src/perch/app.py`
- **Learnings:**
  - Textual auto-routes messages via `on_<widget_class>_<message_name>` naming convention — `on_git_status_panel_file_selected` in app catches `GitStatusPanel.FileSelected`
  - `ListItem.name` stores the file path set during `_make_list_item()`, so the selection handler can retrieve it without extra data structures
  - `item.parent` gives the `ListView` container, and checking its `id` distinguishes staged from unstaged/untracked sections
  - For deleted files, directly setting viewer internal state (`_diff_mode`, `_current_path`) and rendering diff inline avoids needing a separate "deleted file viewer" widget
---

## 2026-03-16 - perch-54y.9
- Added `_save_cursor_state()` and `_restore_cursor_state()` methods to `GitStatusPanel` for preserving ListView cursor position across refreshes
- Extracted `_update_list_view()` helper that wraps save/clear/repopulate/restore cycle for each section
- Cursor restoration prefers matching by file name (handles list reordering), falls back to clamped index
- Files changed: `src/perch/widgets/git_status.py`
- **Learnings:**
  - `ListView.index` is the cursor position; reading it before `clear()` and setting it after `append()` preserves position
  - `lv.children[i]` gives the `ListItem` at index `i`; `ListItem.name` stores the file path set during creation
  - Matching by name first (then falling back to clamped index) handles the case where items are reordered or removed
  - Pre-existing flaky test `test_has_tabbed_content` still fails (non-git worktree issue) — unrelated to this change
---

## 2026-03-16 - perch-54y.10
- Added "Toggle Diff View" (`d`) and "Toggle Diff Layout" (`s`) commands to `COMMANDS` list in `commands.py`
- Added `action_toggle_diff()` and `action_toggle_diff_layout()` app-level actions in `app.py` that delegate to `FileViewer`
- CSS for `#diff-container`, `#diff-left`, `#diff-right` was already in place from US-004
- Files changed: `src/perch/commands.py`, `src/perch/app.py`
- **Learnings:**
  - Command palette commands run app-level actions, so widget-level actions need thin app-level wrappers that delegate via `query_one(Widget).action_name()`
  - The `COMMANDS` list format is `(display_name, hotkey_display, action_name)` where `action_name` maps to `action_<name>` on the app
---

