---
plan: feat-revamp-hotkey-display.md
status: in_progress
schema_version: 3
---

# Execution State: Revamp Hotkey Display

## Progress
- [x] Phase 1: Foundation — Shared Binding Constants + Cleanup
- [x] Phase 2: Curated Footer Display
- [x] Phase 3: Help Screen
- [x] Phase 4: Polish and Test Coverage

## Key Decisions
- Nav bindings: Factory function `make_nav_bindings()` with per-widget action names
- HelpScreen: `BINDING_REGISTRY` dict on PerchApp for all-panel display
- `?` behavior: Push screen (Escape to close)
- Binding syntax: Standardize all to `Binding()` objects
- Stale cleanup: Move to Phase 1
- Markdown delegate: Add `action_toggle_markdown_preview` to PerchApp
- Tooltips: Help screen only (not footer hover)
- Phase 1: `Binding.group` requires `Binding.Group("...")` wrapper, not raw strings — crashes Footer otherwise

## Learnings
- Phase 1: `Binding.Group("text")` is required for group param (not plain str). Four group constants: `_APP_GROUP`, `_NAV_GROUP`, `_ACTIONS_GROUP`, `_VIEW_GROUP` in `_bindings.py`
- Phase 1: SyncedDiffView.BINDINGS and CommitTree.BINDINGS left unchanged — separate from shared nav bindings, no conflict
- Phase 2: `FOCUS_BINDING` set to `show=False` globally — Focus mode is power-user feature
- Phase 2: Viewer `e` Editor hidden, GitPanel `l` Select shown — keeps footer to 5-6 per context
- Phase 3: `BINDING_REGISTRY` is curated ClassVar dict on PerchApp (not auto-derived from BINDINGS)
- Phase 3: `COMMAND_PALETTE_BINDING` changed to `"ctrl+shift+p"` atomically with `?` rebind
- Phase 3: `_build_help_content()` is pure function separated from HelpScreen for testability

## Code Context
- Created: `src/perch/_bindings.py` — factory + shared constants
- Created: `tests/test_bindings.py` — 46 tests for bindings
- Modified: `src/perch/app.py` — standardized BINDINGS, `action_toggle_markdown_preview` delegate, `Footer(compact=True)`
- Modified: `src/perch/widgets/file_tree.py` — uses shared bindings
- Modified: `src/perch/widgets/git_status.py` — uses shared bindings, `l` Select now show=True
- Modified: `src/perch/widgets/github_panel.py` — uses shared bindings
- Modified: `src/perch/widgets/viewer.py` — uses `make_nav_bindings("scroll_down", ...)`, `e` Editor show=False
- Modified: `src/perch/commands.py` — removed stale entries (10 commands remain)
- Modified: `tests/test_commands.py` — updated counts, added guard test, added show_help
- Modified: `tests/test_app.py` — 24 new footer visibility tests, updated COMMAND_PALETTE_BINDING assertion
- Modified: `src/perch/_bindings.py` — FOCUS_BINDING now show=False
- Created: `src/perch/widgets/help_screen.py` — HelpScreen modal with _build_help_content()
- Created: `tests/test_help_screen.py` — 17 tests for help screen
- Modified: `src/perch/app.py` — BINDING_REGISTRY, action_show_help, ? → show_help, COMMAND_PALETTE_BINDING → ctrl+shift+p
- Modified: `src/perch/commands.py` — added Help entry (11 commands)

## Blockers (if any)

## Error Log

| Error | Attempt | Approach | Outcome |
|-------|---------|----------|---------|
