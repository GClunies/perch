---
plan: feat-revamp-hotkey-display.md
created: 2026-03-21
feature: "Revamp hotkey display with Lazygit-style contextual keybinding bar"
---

# Research Context: Revamp Hotkey Display

## Key File Paths

- `src/perch/app.py:27-43` — PerchApp.BINDINGS (12 bindings, mixed tuple/Binding)
- `src/perch/app.py:24-25` — COMMANDS and COMMAND_PALETTE_BINDING
- `src/perch/app.py:95` — Footer() in compose()
- `src/perch/widgets/viewer.py:302-315` — SyncedDiffView.BINDINGS (12 scroll bindings, all show=False)
- `src/perch/widgets/viewer.py:377-389` — Viewer.BINDINGS (9 bindings with hero nav)
- `src/perch/widgets/viewer.py:432-452` — check_action + _refresh_footer
- `src/perch/widgets/file_tree.py:39-54` — FileTree.BINDINGS (14 bindings)
- `src/perch/widgets/git_status.py:55-59` — CommitTree.BINDINGS (3 bindings)
- `src/perch/widgets/git_status.py:104-114` — GitPanel.BINDINGS (7 bindings)
- `src/perch/widgets/github_panel.py:82-92` — GitHubPanel.BINDINGS (8 bindings)
- `src/perch/widgets/file_search.py:91-93` — FileSearchScreen.BINDINGS (escape only)
- `src/perch/commands.py:9-22` — COMMANDS list (12 entries, 2 stale)
- `src/perch/app.tcss` — no Footer CSS overrides (uses Textual defaults)
- `tests/test_app.py:37-42` — test_has_footer (existence only)
- `tests/test_app.py:113-115` — test_ctrl_shift_p_binding_exists
- `tests/test_commands.py` — command palette structure tests

## Patterns & Conventions

- BINDINGS use mixed tuple `("key", "action", "desc")` and `Binding(...)` syntax
- Hero binding pattern: first nav key (`j`) has `show=True` with `key_display="hjkl/←↓↑→"`, rest `show=False`
- `check_action()` used in Viewer for conditional binding visibility (diff, layout, markdown)
- `_refresh_footer()` calls `screen.refresh_bindings()` after state changes
- Delegated bindings: widgets use `"app.toggle_focus_mode"` to call app actions
- Command palette via `DiscoveryCommandProvider` with `(display_name, hotkey_display, action_name)` tuples
- Tests use `pilot.press("key")` for key simulation

## DRY Violations Found

- `hjkl/←↓↑→` hero nav pattern: identical in Viewer:383, FileTree:48, GitPanel:107, GitHubPanel:86
- `f` → `app.toggle_focus_mode`: identical in Viewer:382, FileTree:43, GitPanel:106, GitHubPanel:85
- `r` → `refresh`: identical in FileTree:40, GitPanel:105, GitHubPanel:84

## Stale Code

- `commands.py:17-18`: `next_diff_file` and `prev_diff_file` have no action implementations anywhere

## Validation Summary

- **High-risk topics:** None
- **External research:** Yes — Textual Footer/Binding docs, Lazygit keybinding patterns
- **Issues found:** DRY violations (3 patterns), stale command entries (2), no binding groups/tooltips used

## Gotchas

- Textual 1.1 is installed; `group`, `tooltip`, `compact` all available
- `COMMAND_PALETTE_BINDING = "question_mark"` must change to `"ctrl+shift+p"` when rebinding `?`
- `GitPanel.can_focus = False` — container bindings propagate via child focus bubble; test after refactor
- `FileSearchScreen.key_enter()` uses raw key handler, not BINDINGS — intentional to avoid Footer display
- Viewer's `check_action` must be preserved during binding reorganization
