# Plan: File Viewer, File Tree, and Git Tab Enhancements

## Context

Perch is a Textual TUI for browsing git worktrees. Three areas need improvement:
- The file viewer ignores the app theme and has no diff support
- The file tree shows no git status indicators
- The git status panel is display-only with no interactivity or connection to the file viewer

---

## 1. Git Service Foundation

**File:** `src/perch/services/git.py`

Add two new functions following existing patterns (`_run_git`, return parsed data):

- **`get_diff(root, path, staged=False) -> str`** — runs `git diff [--cached] -- <path>`, returns raw unified diff text
- **`get_status_dict(root) -> dict[str, str]`** — wraps `get_status()`, returns `{relative_path: status_label}` flat dict for O(1) lookup by the file tree

Add tests in `tests/test_git_service.py` following existing `TestParseStatus`/`TestParseLog` patterns.

---

## 2. File Viewer — Theme Respect + Diff Toggle

**File:** `src/perch/widgets/file_viewer.py`

### Theme-aware syntax highlighting
- Add `_get_syntax_theme() -> str` method that checks `self.app.current_theme.dark` and returns an appropriate Pygments theme name (e.g., `"monokai"` for dark, `"default"` for light)
- Pass `theme=self._get_syntax_theme()` to `Syntax()` in `load_file()`
- Re-render when app theme changes (app calls `viewer.load_file(viewer._current_path)` from its `watch_theme` method)

### Diff view
- Add `worktree_root: Path | None = None` param to `__init__()` (app passes it in `compose()`)
- Add `_diff_mode: bool = False` and `_diff_layout: str = "stacked"` attributes
- Add bindings: `d` → toggle diff, `s` → toggle layout (stacked/side-by-side)
- **Stacked diff** (default): `Syntax(diff_text, "diff", theme=..., line_numbers=True)` — simple, one call
- **Side-by-side diff**: Parse unified diff into left/right text, render in a `Horizontal` with two `Static` widgets
- Add a hidden `Horizontal` container (`#diff-container`) for side-by-side; toggle `display` between it and `_content`

**File:** `src/perch/app.py`
- Update `compose()`: pass `worktree_root=self.worktree_path` to `FileViewer`
- Add `watch_theme()` method to re-render the file viewer on theme change

**File:** `src/perch/commands.py`
- Add `("Toggle Diff View", "d", "toggle_diff")` to `COMMANDS`

---

## 3. File Tree — Git Status Indicators

**File:** `src/perch/widgets/file_tree.py`

- Add `_git_status: dict[str, str] = {}` to store status lookup
- Add `on_mount()` with `@work(thread=True)` refresh on 5-second interval (calls `get_status_dict()`)
- Override `render_label()` to append a color-coded letter after the file name:

```
_STATUS_CODES = {"modified": "M", "added": "A", "deleted": "D", "renamed": "R", ...}
_STATUS_COLORS = {"modified": "yellow", "added": "green", "deleted": "red", ...}
```

- Compute relative path from `node.data.path`, look up in `_git_status`, append styled letter
- Colors match existing `_STATUS_STYLES` in `git_status.py`

---

## 4. Git Tab — Interactive Navigation

**File:** `src/perch/widgets/git_status.py`

### Replace Labels with ListViews
- Swap the `Label` inside each file-section `Collapsible` with a `ListView` containing `ListItem` widgets
- Each `ListItem` stores the file path in its `name` attribute and displays the styled status + path
- Commits section stays as a `DataTable` (already interactive)

### Section navigation bindings
- Add `u` → focus Unstaged list, `s` → focus Staged list, `t` → focus Untracked list
- Each action expands the parent `Collapsible` if collapsed, then focuses the `ListView`

### Custom Message → File Viewer
- Define `GitStatusPanel.FileSelected(Message)` with `path: str` and `staged: bool`
- Handle `on_list_view_selected()` inside `GitStatusPanel` — post `FileSelected` message
- Handle deleted files gracefully (file won't exist on disk; could trigger diff mode)

**File:** `src/perch/app.py`
- Add `on_git_status_panel_file_selected()` handler that calls `FileViewer.load_file(worktree_path / event.path)`

### Refresh stability
- Before clearing/repopulating ListViews on auto-refresh, save cursor index and restore after update to avoid losing the user's position

---

## 5. CSS Updates

**File:** `src/perch/app.tcss`

```css
GitStatusPanel ListView { height: auto; max-height: 15; }
GitStatusPanel ListItem { height: 1; }
#diff-container { layout: horizontal; height: 1fr; }
#diff-left, #diff-right { width: 1fr; height: 100%; }
```

---

## Implementation Order

1. `services/git.py` — add `get_diff()` + `get_status_dict()` + tests
2. `widgets/file_viewer.py` — theme-aware Syntax (no deps)
3. `widgets/file_tree.py` — git status indicators (needs `get_status_dict`)
4. `widgets/file_viewer.py` — diff view toggle (needs `get_diff`)
5. `widgets/git_status.py` — ListView + FileSelected message + navigation
6. `app.py` — wire FileViewer worktree_root, handle FileSelected, watch_theme
7. `commands.py` — add new commands
8. `app.tcss` — new styles
9. Tests for each feature

---

## Key Files

| File | Changes |
|------|---------|
| `src/perch/services/git.py` | Add `get_diff()`, `get_status_dict()` |
| `src/perch/widgets/file_viewer.py` | Theme-aware Syntax, diff mode, side-by-side layout |
| `src/perch/widgets/file_tree.py` | Override `render_label()` with status indicators |
| `src/perch/widgets/git_status.py` | ListView, FileSelected message, section nav |
| `src/perch/app.py` | Wire viewer worktree_root, handle messages, watch_theme |
| `src/perch/commands.py` | Add diff toggle + section nav commands |
| `src/perch/app.tcss` | ListView + diff container styles |

---

## Verification

1. `uv run pytest` — all existing + new tests pass
2. `uv run ruff check src tests` — no lint issues
3. `uv run perch` — launch and verify:
   - File viewer syntax colors change when switching themes via command palette
   - Files in tree show colored status letters (M, A, D, ?) next to modified/new files
   - Press `d` on a modified file to see unified diff; press `s` to toggle side-by-side
   - Switch to Git tab, press `u`/`s`/`t` to jump between sections
   - Select a file in Git tab → file viewer updates
   - Auto-refresh doesn't lose cursor position in Git tab
