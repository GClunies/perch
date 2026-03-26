---
plan: feat-enable-mouse-click-support.md
created: 2026-03-21
feature: "Enable mouse click support for pane and sidebar selection"
---

# Research Context: Mouse Click Support

## Key File Paths

- src/perch/cli.py:27 — `app.run(mouse=False)` root cause
- src/perch/app.py:27-43 — BINDINGS
- src/perch/app.py:80-92 — compose() layout (Viewer, DraggableSplitter, TabbedContent with 3 TabPanes)
- src/perch/app.py:284-302 — action_next_tab/action_prev_tab
- src/perch/app.py:304-311 — action_focus_next_pane
- src/perch/app.py:312-347 — _focus_active_tab() focus routing dispatch
- src/perch/app.py:442-458 — action_toggle_focus_mode
- src/perch/app.py:462-465 — _focused_pane_is_left()
- src/perch/widgets/git_status.py:53 — CommitTree.can_focus = True
- src/perch/widgets/git_status.py:65 — GitPanel.can_focus = False
- src/perch/widgets/git_status.py:141-143 — GitPanel.has_focus custom property
- src/perch/widgets/git_status.py:198-220 — boundary navigation (j/k cross-widget)
- src/perch/widgets/github_panel.py:82-85 — GitHubPanel.BINDINGS
- src/perch/widgets/file_tree.py:39-52 — FileTree.BINDINGS
- src/perch/widgets/viewer.py:317 — SyncedDiffView.can_focus = True
- src/perch/app.tcss:12-14 — #left-pane:focus-within CSS
- src/perch/app.tcss:32-34 — #sidebar:focus-within CSS
- tests/test_app.py — integration tests for tab switching and focus

## Patterns & Conventions

- Focus routing is centralized in `_focus_active_tab()` — it dispatches focus to the correct child widget per tab
- GitPanel is a compound widget (Vertical container) that delegates focus to children (ListView, CommitTree)
- All pane/focus logic uses `query_one()` to find widgets, then calls `.focus()`
- CSS uses `:focus-within` pseudo-class for pane border highlighting (no per-widget focus CSS)
- Event handlers follow `on_<widget>_<message>` naming (e.g., `on_git_panel_file_selected`)
- Tests use `async with app.run_test()` pattern with `pilot` for keyboard simulation
- No mouse/click handlers exist anywhere — all interaction is keyboard-driven
- `_focus_mode` bool tracks full-screen viewer mode; hides sidebar when active

## Validation Summary

- **High-risk topics:** None
- **External research:** Yes — validated Textual's FOCUS_ON_CLICK, focus_on_click(), TabActivated event, App.run(mouse=) via Context7
- **Issues found:** None — Textual's built-in click-to-focus and TabActivated cover most needs

## Gotchas

- `app.py:334` accesses `panel._file_list.focus()` directly (private attribute) — fragile coupling
- `action_next_tab` currently calls both `tabbed.active = ...` AND `_focus_active_tab()` — adding TabActivated handler will cause double execution unless refactored
- `on_mount()` sets `tabbed.active = "tab-files"` at `app.py:74` which may trigger TabActivated — guard needed if handler calls `_focus_active_tab()` before widgets are ready
- GitPanel.has_focus is a custom property override, not Textual's native — works by checking children, remains correct for mouse
