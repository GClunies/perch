# feat: Revamp Hotkey Display with Lazygit-Style Contextual Keybinding Bar

## Status
- **Created:** 2026-03-21
- **Reviewed:** 2026-03-21
- **Consolidated:** 2026-03-21
- **Ready for:** /fly:work

## Executive Summary

Revamp Perch's keyboard shortcut system to follow the Lazygit/Lazydocker pattern: a compact, curated footer showing only the most relevant hotkeys per focused widget, plus a dedicated `?` help screen listing all keybindings organized by panel context. The current system uses Textual's built-in Footer with ad-hoc show/hide decisions, duplicated binding definitions across 4 widgets, stale command palette entries, and no binding groups or tooltips.

The implementation extracts shared bindings into a factory function in `_bindings.py`, standardizes all BINDINGS to `Binding()` syntax, enables compact Footer mode with curated visibility, creates a `HelpScreen` modal fed by a `BINDING_REGISTRY` on the app, and rebinds `?` from command palette to help screen (palette moves to `Ctrl+Shift+P`).

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Shared nav bindings | Factory function `make_nav_bindings()` | Keeps hero `key_display` logic in one place; each widget passes its own action names (`scroll_down` vs `cursor_down`) |
| HelpScreen binding collection | `BINDING_REGISTRY` dict on PerchApp | Decoupled, testable, extensible — widgets don't need to know about HelpScreen |
| `?` key behavior | Push screen (Escape to close) | Simpler implementation; Escape is standard dismiss pattern |
| Binding syntax | Standardize all to `Binding()` objects | Enables `group`/`tooltip` on every binding; consistent syntax |
| Stale command cleanup | Move to Phase 1 | Fix existing broken behavior early — `next_diff_file`/`prev_diff_file` silently fail today |
| `toggle_markdown_preview` delegate | Add app-level delegate | Matches existing `toggle_diff`/`toggle_diff_layout` pattern at `app.py:470-477` |
| Tooltips | Help screen only | Footer stays compact; terminal hover support is inconsistent |
| Custom vs built-in Footer | Built-in with `compact=True` | Less maintenance; `group` and `check_action` cover our needs |

## Critical Items Before Implementation

### P1 Findings (MUST Address)

- **`COMMAND_PALETTE_BINDING` must change atomically with `?` rebind** (Source: reviewer-architecture, reviewer-code-quality)
  - Issue: `COMMAND_PALETTE_BINDING = "question_mark"` intercepts `?` at framework level. If not changed in same step as new `?` binding, help screen will never fire.
  - Resolution: Step 3.3 explicitly changes both in same step. Verify with smoke test.

- **`NAV_BINDINGS` action name incompatibility** (Source: reviewer-code-quality, reviewer-patterns)
  - Issue: Viewer uses `scroll_down`/`scroll_up`, others use `cursor_down`/`cursor_up`.
  - Resolution: Decided on factory function `make_nav_bindings()` — addressed in Steps 1.2-1.3.

- **`test_commands.py` will break after COMMANDS changes** (Source: reviewer-architecture, reviewer-code-quality)
  - Issue: Tests assert specific action list and `len(hits) == len(COMMANDS)`.
  - Resolution: Update tests in same step as COMMANDS changes (Steps 1.6 and 3.4).

## Implementation Checklist

### Phase 1: Foundation — Shared Binding Constants + Cleanup

Extract duplicated bindings into a factory function, standardize syntax, fix stale entries.

- [ ] **Step 1.1: Write tests for shared binding factory and constants**
  - Test `make_nav_bindings()` returns expected keys (`j`, `k`) with correct defaults (`cursor_down`, `cursor_up`)
  - Test `make_nav_bindings("scroll_down", "scroll_up", "scroll_left", "scroll_right")` returns 4 bindings with scroll actions
  - Test first binding has `key_display="hjkl/←↓↑→"` and `show=True`, rest have `show=False`
  - Test `FOCUS_BINDING` maps `f` → `app.toggle_focus_mode` with `group="Navigation"`
  - Test `REFRESH_BINDING` maps `r` → `refresh` with `group="Actions"`
  - Test all returned bindings are `Binding` instances (not tuples)
  - Test factory returns `tuple` (immutable), not `list`
  - File: `tests/test_bindings.py` (new)

- [ ] **Step 1.2: Create `src/perch/_bindings.py`**
  - `make_nav_bindings(down, up, left, right)` → returns `tuple[Binding, ...]` with hero pattern
  - `FOCUS_BINDING`: `Binding("f", "app.toggle_focus_mode", "Focus", group="Navigation")`
  - `REFRESH_BINDING`: `Binding("r", "refresh", "Refresh", group="Actions")`
  - `PAGE_BINDINGS`: `tuple` of `pageup`/`pagedown` bindings with `show=False`
  - Anti-pattern to avoid: Do NOT use `list` — use `tuple` for immutability
  - File: `src/perch/_bindings.py` (new)

- [ ] **Step 1.3: Write tests for widget binding substitutions**
  - Per widget: assert BINDINGS list contains the shared binding objects (not duplicated inline versions)
  - Test `FileTree.BINDINGS` uses `make_nav_bindings()` output (cursor_down/cursor_up)
  - Test `Viewer.BINDINGS` uses `make_nav_bindings("scroll_down", "scroll_up", ...)` output
  - Test `GitPanel.BINDINGS` uses `make_nav_bindings()` output
  - Test `GitHubPanel.BINDINGS` uses `make_nav_bindings()` output
  - Review note: `CommitTree.BINDINGS` (`git_status.py:55-59`) has `l` → `select_cursor` and page bindings — verify these don't conflict with `GitPanel` shared bindings
  - File: `tests/test_bindings.py` (extend)

- [ ] **Step 1.4: Update all widgets to use shared bindings + standardize to Binding() syntax**
  - `FileTree.BINDINGS` — replace inline nav/focus/refresh with `[*make_nav_bindings(), FOCUS_BINDING, REFRESH_BINDING, ...]`; convert remaining tuples to `Binding()`
  - `GitPanel.BINDINGS` — same replacement; keep `l` → `select_cursor` widget-specific
  - `GitHubPanel.BINDINGS` — same replacement; keep `o` → `open_in_browser` widget-specific
  - `Viewer.BINDINGS` — use `make_nav_bindings("scroll_down", "scroll_up", "scroll_left", "scroll_right")`; keep `d`, `s`, `m`, `e` widget-specific
  - `SyncedDiffView.BINDINGS` (`viewer.py:302-315`) — review for overlap with Viewer nav; keep scroll variants `show=False`
  - Anti-pattern to avoid: Do NOT add `_refresh_footer()` calls to cursor movement in other widgets — keep it limited to Viewer's explicit state transitions
  - Files: `src/perch/widgets/file_tree.py:39-54`, `src/perch/widgets/git_status.py:104-114`, `src/perch/widgets/github_panel.py:82-92`, `src/perch/widgets/viewer.py:377-389`

- [ ] **Step 1.5: Add `group` to all remaining bindings; add `action_toggle_markdown_preview` delegate**
  - App-level: `q` → `group="App"`, `Tab` → `group="Navigation"`, `[`/`]` → `group="Navigation"`
  - Viewer-specific: `d` → `group="View"`, `s` → `group="View"`, `m` → `group="View"`, `e` → `group="Actions"`
  - FileTree-specific: `Ctrl+P` → `group="Actions"`, `o` → `group="Actions"`
  - GitPanel-specific: `l` → `group="Actions"`
  - GitHubPanel-specific: `o` → `group="Actions"`
  - Add `action_toggle_markdown_preview()` to `PerchApp` — delegate to `viewer.action_toggle_markdown_preview()`, matching pattern at `app.py:470-477`
  - Files: `src/perch/app.py:27-43`, all widget files

- [ ] **Step 1.6: Remove stale `commands.py` entries + update tests**
  - Remove `next_diff_file` and `prev_diff_file` from COMMANDS list (no action implementations exist — silently fail today)
  - Update `test_commands.py` for new COMMANDS count and entries
  - Add test: every COMMANDS action has a corresponding `action_*` method on PerchApp (prevents future stale entries)
  - Files: `src/perch/commands.py:17-18`, `tests/test_commands.py`

- [ ] **Step 1.7: Verify** — `make test` passes, `make lint` passes

### Phase 2: Curated Footer Display

Switch to `compact` mode and curate which bindings appear per widget.

- [ ] **Step 2.1: Write tests for footer behavior**
  - Test `Footer` is in `compact` mode
  - Test binding `show` attribute values per widget context (more reliable than rendering-based assertions):
    - FileTree focused: `r` Refresh, `o` Open, `Ctrl+P` Search, `hjkl` Navigate, `?` Help → `show=True`
    - Viewer focused: `d` Diff, `s` Layout, `m` Markdown (via `check_action`), `hjkl` Scroll, `?` Help → `show=True`
    - GitPanel focused: `r` Refresh, `l` Select, `hjkl` Navigate, `?` Help → `show=True`
    - GitHubPanel focused: `o` Open, `r` Refresh, `hjkl` Navigate, `?` Help → `show=True`
  - Review note: Footer rendering tests via `pilot` are fragile — prefer testing `Binding.show` attributes directly
  - File: `tests/test_app.py` (extend existing footer tests)

- [ ] **Step 2.2: Enable `compact=True` on Footer**
  - Change `Footer()` → `Footer(compact=True)` in `PerchApp.compose()`
  - File: `src/perch/app.py` (compose method)

- [ ] **Step 2.3: Audit and curate binding visibility per widget**
  - Principle: show **max 5-6 bindings** in footer per context (Lazygit shows ~5-7)
  - Always show: context-specific action keys + navigation hero hint + `?` help
  - Always hide: `pageup`/`pagedown`, variant keys (`h`/`l` when `j` hero shown), `-`/`=` resize
  - Review note: Verify `check_action` on Viewer still works correctly after adding `group` — grouped footer may show/hide groups dynamically
  - Files: all widget BINDINGS lists

- [ ] **Step 2.4: Verify** — `make test`, visual check of footer per panel

### Phase 3: Help Screen

Create a dedicated keybinding help screen and rebind `?`.

- [ ] **Step 3.1: Write tests for HelpScreen**
  - Test `?` key opens `HelpScreen` (not command palette)
  - Test `HelpScreen` displays bindings organized by section from `BINDING_REGISTRY`
  - Test `Escape` closes the help screen
  - Test all sections from `BINDING_REGISTRY` appear in help screen (Global, File Tree, Viewer, Git, GitHub)
  - Test `Ctrl+Shift+P` still opens command palette
  - Test `BINDING_REGISTRY` keys match expected panel names
  - File: `tests/test_help_screen.py` (new)

- [ ] **Step 3.2: Create `src/perch/widgets/help_screen.py`**
  - `HelpScreen(ModalScreen)` that reads `self.app.BINDING_REGISTRY`
  - Displays bindings in a formatted table grouped by section using `Static` with Rich tables:
    ```
    Global ─────────────────────────────
      q        Quit
      Tab      Switch Pane
      [ / ]    Prev / Next Tab
      Ctrl+P   File Search
      ?        Help

    File Tree ──────────────────────────
      r        Refresh
      o        Open in Editor
      hjkl     Navigate
    ...
    ```
  - Use `Static` (NOT `RichLog` — `RichLog` is append-only for streaming, `Static` renders a snapshot)
  - Separate collection logic: pure function `_build_help_content(registry) -> Rich.Table` for testability
  - Bindings: `Escape` to dismiss
  - File: `src/perch/widgets/help_screen.py` (new)
  - Note: Placing in `widgets/` follows precedent of `FileSearchScreen` in `widgets/file_search.py`

- [ ] **Step 3.3: Add `BINDING_REGISTRY` to PerchApp and rebind `?`**
  - Add `BINDING_REGISTRY: ClassVar[dict[str, list[Binding]]]` mapping panel names to their BINDINGS
  - **ATOMIC CHANGE**: In the same step:
    - Change `COMMAND_PALETTE_BINDING = "question_mark"` → `"ctrl+shift+p"`
    - Remove old `Binding("question_mark", "command_palette", ...)`
    - Add `Binding("question_mark", "show_help", "Help", key_display="?", priority=True, group="App")`
    - Add `action_show_help()` → `self.push_screen(HelpScreen())`
  - Smoke test: verify `"ctrl+shift+p"` works as `COMMAND_PALETTE_BINDING` in Textual 1.1
  - Files: `src/perch/app.py`

- [ ] **Step 3.4: Update `commands.py`**
  - Add `("Help", "?", "show_help")` entry
  - Ensure all COMMANDS entries have corresponding action implementations
  - Update `test_commands.py` for new entry
  - File: `src/perch/commands.py`, `tests/test_commands.py`

- [ ] **Step 3.5: Verify** — `make test`, `?` opens help screen, `Ctrl+Shift+P` opens palette

### Phase 4: Polish and Test Coverage

- [ ] **Step 4.1: Update existing tests for changed bindings**
  - `test_app.py` — rename `test_ctrl_shift_p_binding_exists` to `test_command_palette_binding` and update assertion to `"ctrl+shift+p"`
  - `test_app.py` — update `test_has_footer` to verify compact mode
  - File: `tests/test_app.py`

- [ ] **Step 4.2: Update README keyboard shortcuts table**
  - Add `?` → "Show keybinding help" entry
  - Update `Ctrl+Shift+P` description to note it's for command palette
  - File: `README.md`

- [ ] **Step 4.3: Final verification**
  - `make test` — all tests pass
  - `make lint` — no lint errors
  - `make typecheck` — no type errors
  - Visual: launch app, verify footer per panel, verify help screen

## Technical Reference

### Best Practices to Follow

1. **Immutable shared constants** — Use `tuple[Binding, ...]` not `list[Binding]` for `_bindings.py` exports (prevents accidental mutation)
2. **Factory over static constants** — `make_nav_bindings()` accommodates different action names per widget while keeping hero `key_display` logic centralized
3. **Registry pattern for cross-cutting concerns** — `BINDING_REGISTRY` avoids tight coupling between `HelpScreen` and widget classes
4. **Atomic binding changes** — `COMMAND_PALETTE_BINDING` and `?` binding must change in same commit/step
5. **Test attributes over rendering** — Test `Binding.show` values directly; Footer rendering tests via `pilot` are fragile in Textual

### Anti-Patterns to Avoid

1. **Do NOT add `_refresh_footer()` to cursor movement handlers** — Keep it limited to Viewer's explicit state transitions (diff mode toggle, file load). Adding it elsewhere causes Footer redraws on every keystroke.
2. **Do NOT use mutable `list` for shared binding constants** — Use `tuple` to prevent silent shared-state mutation.
3. **Do NOT use `RichLog` for HelpScreen** — Use `Static` for one-shot rendered content. `RichLog` is for streaming/appending.
4. **Do NOT leave stale COMMANDS entries** — The invariant test from Step 1.6 prevents future regressions.

### Code Examples

**Factory function pattern:**
```python
# src/perch/_bindings.py
def make_nav_bindings(
    down: str = "cursor_down",
    up: str = "cursor_up",
    left: str | None = None,
    right: str | None = None,
) -> tuple[Binding, ...]:
    bindings: list[Binding] = [
        Binding("j", down, "Navigate", key_display="hjkl/←↓↑→", group="Navigation"),
        Binding("k", up, "Up", show=False, group="Navigation"),
    ]
    if left:
        bindings.append(Binding("h", left, "Left", show=False, group="Navigation"))
    if right:
        bindings.append(Binding("l", right, "Right", show=False, group="Navigation"))
    return tuple(bindings)
```

**Registry pattern:**
```python
# src/perch/app.py
BINDING_REGISTRY: ClassVar[dict[str, list[Binding]]] = {
    "Global": [b for b in PerchApp.BINDINGS if isinstance(b, Binding)],
    "File Tree": FileTree.BINDINGS,
    "Viewer": Viewer.BINDINGS,
    "Git": GitPanel.BINDINGS,
    "GitHub": GitHubPanel.BINDINGS,
}
```

### Performance Considerations

- [ ] `_refresh_footer` stays limited to Viewer state transitions — no new call sites in other widgets
- [ ] `HelpScreen` renders once on open via `Static` — no continuous computation
- [ ] `make_nav_bindings()` called at class definition time — zero runtime cost after import

## Review Findings Summary

### Addressed in Plan

| Finding | Priority | Resolution | Checklist Location |
|---------|----------|------------|-------------------|
| COMMAND_PALETTE_BINDING atomic change | P1 | Explicit atomic step with smoke test | Phase 3, Step 3.3 |
| NAV_BINDINGS action incompatibility | P1 | Factory function `make_nav_bindings()` | Phase 1, Steps 1.2-1.4 |
| test_commands.py breakage | P1 | Update tests in same step as COMMANDS changes | Phase 1 Step 1.6, Phase 3 Step 3.4 |
| HelpScreen collection strategy | P2 | BINDING_REGISTRY on app | Phase 3, Steps 3.2-3.3 |
| CommitTree.BINDINGS overlap | P2 | Review in Step 1.4 (GitPanel section) | Phase 1, Step 1.4 |
| Test-after ordering gaps | P2 | Added Step 1.3 for widget substitution tests | Phase 1, Step 1.3 |
| COMMANDS structural duplication | P2 | Noted as follow-on tech debt | N/A — future refactor |
| App-level shadow bindings | P2 | Keep for command palette compatibility; documented | Phase 1, Step 1.5 |
| Footer test fragility | P2 | Test Binding.show attributes directly | Phase 2, Step 2.1 |
| _refresh_footer pattern | P2 | Anti-pattern documented — no new call sites | Technical Reference |
| toggle_markdown_preview delegate | P2 | Add delegate matching existing pattern | Phase 1, Step 1.5 |

### Deferred Items

- **P3: `_make_section_header` duplication** — Pre-existing across `git_status.py` and `github_panel.py`. Not in scope for this feature. Consider extracting to `widgets/_utils.py` in a future refactor.
- **P3: `SyncedDiffView.BINDINGS` overlap** — Review during Step 1.4 but don't over-engineer; inner scroll bindings shadow outer correctly.
- **P3: `_bindings.py` underscore naming** — Acceptable for internal module. Tests importing private modules is standard Python practice.
- **P3: `except Exception: pass` in file_tree.py** — Pre-existing tech debt. Out of scope.
- **P3: Unicode `key_display` encoding** — Resolved naturally by `_bindings.py` using readable literal `←↓↑→`.
- **P3: Verify `ctrl+shift+p` Textual compatibility** — Smoke test in Step 3.3.

---

<details>
<summary>Appendix: Raw Review Data</summary>

**Agents run:** 5 (reviewer-architecture, reviewer-code-quality, reviewer-patterns, reviewer-performance, reviewer-plan-philosophy)
**All responded successfully.**

**Finding counts by agent:**
- reviewer-architecture: 7 findings (2 P1, 3 P2, 2 P3)
- reviewer-code-quality: 8 findings (2 P1, 4 P2, 2 P3)
- reviewer-patterns: 10 findings (2 P1, 4 P2, 4 P3)
- reviewer-performance: 4 findings (0 P1, 2 P2, 2 P3)
- reviewer-plan-philosophy: 3 findings (0 P1, 2 P2, 1 P3)

**Conflicts detected:** 1 (NAV_BINDINGS sharing strategy: factory vs separate constants → resolved by user choosing factory)

**Pre-consolidation backup:** `docs/plans/feat-revamp-hotkey-display.md.pre-consolidation.backup`

</details>
