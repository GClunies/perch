# feat: Enable mouse click support for pane and sidebar selection

## Status
- **Created:** 2026-03-21
- **Reviewed:** 2026-03-21
- **Consolidated:** 2026-03-21
- **Ready for:** /fly:work

## Executive Summary

Enable mouse interaction in the perch TUI so users can click to select sidebar tabs, sidebar items, and switch focus between panes. The root cause is a single line: `app.run(mouse=False)` in `cli.py:27`. Enabling mouse unlocks Textual's built-in click-to-focus and click-to-select on all existing widgets. The only code gap is that `_focus_active_tab()` — which routes focus to the correct child widget and restores viewer content — is only triggered by keyboard actions today. A new `on_tabbed_content_tab_activated` handler bridges that gap for mouse clicks. The refactor also introduces a public `focus_default()` method on `GitPanel` to eliminate private attribute access from `app.py`.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TabActivated for programmatic changes | Verify empirically, refactor if confirmed | User chose: test first, then commit to approach |
| `on_mount` guard strategy | `_mounted` flag in `__init__` | User chose: clean separation from auto-select logic |
| `--no-mouse` CLI flag | No (YAGNI) | User chose: skip, easy to add later |
| Split `_focus_active_tab()` | Defer to follow-up | User chose: coupling is intentional, no benefit splitting now |

## Critical Items Before Implementation

### P1 Findings (MUST Address)

- **Double execution of `_focus_active_tab()`** (Source: 4 agents)
  - Issue: Adding handler + keeping direct calls = double fire on every tab switch
  - Resolution: Phase 2 verifies TabActivated behavior first; Phase 3 adds handler + removes direct calls atomically based on results

- **`on_mount` timing double-fire** (Source: 3 agents)
  - Issue: `tabbed.active` assignment in `on_mount` triggers handler before app is ready
  - Resolution: Phase 1 adds `_mounted` flag guard; Phase 3 handler checks it

- **TabActivated reliability for programmatic changes** (Source: conflict between architecture and code-quality reviewers)
  - Issue: May not fire reliably for `tabbed.active = ...` assignments
  - Resolution: Phase 2 includes an empirical verification test. If it doesn't fire, handler is additive-only (keyboard actions keep direct calls)

## Implementation Checklist

### Phase 1: Foundation — `__init__` cleanup and `GitPanel` public API

- [ ] **Step 1.1: Write test for `GitPanel.focus_default()` method**
  - Test that calling `focus_default()` focuses the file list child
  - File: `tests/test_git_status.py`

- [ ] **Step 1.2: Add `focus_default()` to `GitPanel`**
  - Add `def focus_default(self) -> None: self._file_list.focus()` to `GitPanel` in `src/perch/widgets/git_status.py`
  - Replace `panel._file_list.focus()` with `panel.focus_default()` in `app.py:334`
  - Review note: 4 agents flagged this private attribute access. This is the right time to fix it.

- [ ] **Step 1.3: Move instance attributes to `__init__`**
  - Move `_auto_select_done = False` and `_auto_select_attempts = 0` from `on_mount` to `__init__`
  - Add `self._mounted = False` to `__init__`
  - Set `self._mounted = True` at end of `on_mount`
  - File: `src/perch/app.py`

- [ ] **Step 1.4: Verify** — `make test && make lint && make typecheck`

### Phase 2: Verification — empirically test TabActivated behavior

- [ ] **Step 2.1: Write test: does `TabActivated` fire for programmatic `tabbed.active` assignment?**
  - Use `async with app.run_test()`, set `tabbed.active = "tab-git"` programmatically
  - Assert that `TabbedContent.TabActivated` is posted
  - This determines the refactor strategy for Phase 3
  - File: `tests/test_app.py`
  - Tab selectors for `pilot.click()`: Textual renders tab headers as `Tab` widgets with IDs like `--content-tab-tab-files`

- [ ] **Step 2.2: Write mouse click tests (RED — these should fail)**
  - Test: `pilot.click()` on tab header switches tab AND focuses content widget
  - Test: `pilot.click()` on viewer pane focuses it
  - Test: keyboard navigation still works after mouse click
  - Run `make test` — confirm new mouse tests fail (RED state)
  - Anti-pattern to avoid: Don't use bare `except Exception:` — use specific `NoMatches` from `textual.css.query`
  - File: `tests/test_app.py`

- [ ] **Step 2.3: Verify** — `make test` (existing tests pass, new mouse tests fail as expected)

### Phase 3: Implementation — enable mouse and add handler

- [ ] **Step 3.1: Enable mouse support**
  - Change `app.run(mouse=False)` to `app.run()` in `src/perch/cli.py:27`

- [ ] **Step 3.2: Add `on_tabbed_content_tab_activated` handler + refactor actions (ATOMIC)**
  - Add handler to `PerchApp` in `src/perch/app.py`:
    ```python
    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if not self._mounted or self._focus_mode:
            return
        self._focus_active_tab()
    ```
  - **If Phase 2 Step 2.1 confirmed TabActivated fires for programmatic changes:**
    Remove `self._focus_active_tab()` calls from `action_next_tab` (line 292) and `action_prev_tab` (line 302). The handler becomes the single source of truth.
  - **If Phase 2 Step 2.1 showed TabActivated does NOT fire for programmatic changes:**
    Keep direct calls in `action_next_tab`/`action_prev_tab`. The handler is additive (mouse-only path). Add guard to prevent double-fire if both paths run.
  - Edge case: handler guards on `_mounted` (P1 mount timing) and `_focus_mode` (P2 focus-mode guard)
  - Handler signature must be correctly typed for CI typecheck

- [ ] **Step 3.3: Verify** — `make test && make lint && make typecheck` (all tests pass including new mouse tests — GREEN)

### Phase 4: Manual verification

- [ ] **Step 4.1: Run the app and verify mouse interactions**
  - Click on "Files" tab header → Files tab activates, FileTree focuses
  - Click on "Git" tab header → Git tab activates, file list focuses
  - Click on "GitHub" tab header → GitHub tab activates, GitHubPanel focuses
  - Click on a file in FileTree → file highlights, viewer shows content
  - Click on a file in GitPanel file list → file selects, viewer shows diff
  - Click on a commit node in CommitTree → node highlights, viewer updates
  - Click on the viewer pane → viewer focuses (border highlights)
  - Press `]` after mouse click → tab cycles correctly
  - Press `Tab` after mouse click → pane toggle works correctly
  - All existing keyboard bindings work unchanged

## Technical Reference

### Best Practices to Follow

1. **Leverage Textual built-ins** — Focusable widgets auto-focus on click via `FOCUS_ON_CLICK` (default `True`). `ListView` fires `Selected`, `Tree` fires `NodeHighlighted` — existing handlers already update the viewer. Don't duplicate this.

2. **Single entry point for tab activation focus** — `_focus_active_tab()` is the single focus-routing function. Both keyboard and mouse paths should converge here (directly or via handler).

3. **Guard new handlers defensively** — Check `_mounted` and `_focus_mode` before acting. Use specific exception types (`NoMatches`) not bare `except Exception:`.

### Anti-Patterns to Avoid

1. **Bare `except Exception: pass`** — Pre-existing in `app.py` at 7 locations. Do not propagate into new handler code.
2. **Private attribute access across widget boundaries** — `panel._file_list.focus()` is being fixed in Phase 1. Don't introduce new cross-boundary private access.
3. **Non-atomic refactors** — Steps 3.2 handler addition and direct-call removal MUST happen together.

### Performance Considerations

- [ ] Mouse hover on FileTree fires `on_tree_node_highlighted` for each node — known limitation, consider debouncing in follow-up if reported
- [ ] GitHubPanel 30s auto-refresh resets index (pre-existing) — may be more visible with mouse users who scroll to specific items
- [ ] `_focus_active_tab()` does synchronous filesystem I/O (`Path.exists()`, `Path.is_file()`) — acceptable for tab switches but don't add additional sync I/O

## Review Findings Summary

### Addressed in Plan

| Finding | Priority | Resolution | Checklist Location |
|---------|----------|------------|-------------------|
| Double execution of `_focus_active_tab()` | P1 | Atomic refactor in single step | Phase 3, Step 3.2 |
| `on_mount` timing double-fire | P1 | `_mounted` flag guard | Phase 1, Step 1.3 |
| TabActivated reliability | P1 | Empirical verification test | Phase 2, Step 2.1 |
| Private `_file_list` access | P2 | `focus_default()` public API | Phase 1, Steps 1.1-1.2 |
| Handler focus-mode guard | P2 | `_focus_mode` check in handler | Phase 3, Step 3.2 |
| Handler type signature | P2 | Correctly typed in implementation | Phase 3, Step 3.2 |
| RED-run checkpoint | P3 | Explicit fail confirmation | Phase 2, Step 2.2 |
| Tab selector for tests | P3 | Documented in Step 2.1 | Phase 2, Step 2.1 |

### Deferred Items

- **`_focus_active_tab()` dual responsibility (P2)**: Coupling is intentional — defer to follow-up
- **Mouse hover rapid viewer loads (P2)**: Known limitation — debounce in follow-up if reported
- **Bare `except Exception:` cleanup (P3)**: Pre-existing across 7 sites — separate cleanup task
- **Commit-label duplication in `git_status.py` (P3)**: Unrelated to this feature
- **`_auto_select_done` initialization order (P3)**: Addressed by P1 #2 fix (moved to `__init__`)

### Resolved Conflicts

- **TabActivated for programmatic changes**: Architecture assumed yes, code-quality warned no. Resolved by empirical verification in Phase 2 with branching implementation in Phase 3.

---

## Appendix: Raw Review Data

<details>
<summary>Original Review Summary</summary>

**Reviewed by:** reviewer-architecture, reviewer-code-quality, reviewer-patterns, reviewer-performance, reviewer-plan-philosophy
**Date:** 2026-03-21

### P1 — Critical (Must Address Before Implementation)

**1. Double execution of `_focus_active_tab()` — atomic refactor required** (Identified by 4 agents)
Step 1.3 (add handler) and Step 1.4 (remove direct calls) must be done atomically in the same commit. If the handler is added first without removing the calls from `action_next_tab`/`action_prev_tab`, every keyboard tab switch fires `_focus_active_tab()` twice — causing duplicate `query_one()` lookups, viewer loads, and for the GitHub tab, doubled `PreviewRequested` messages via the index toggle at `app.py:341-344`.
- **Location:** `app.py:284-302`, `app.py:312-347`
- **Action:** Merge Steps 1.3 and 1.4 into a single atomic step.

**2. `on_mount` timing: double-fire at startup** (Identified by 3 agents)
`on_mount` sets `tabbed.active = "tab-files"` (line 74) then calls `_focus_active_tab()` (line 75). The new handler will also fire from the reactive assignment on line 74, causing two calls. Additionally, `_auto_select_done` is initialized on line 76 — after the assignment that triggers `TabActivated` — so any guard using that attribute will fail with `AttributeError`.
- **Location:** `app.py:68-78`
- **Action:** Move `_auto_select_done` and `_auto_select_attempts` initialization to `__init__`. Add a `_mounted = False` guard initialized in `__init__`, set to `True` at end of `on_mount`. Handler skips if `not self._mounted`. Remove the direct `_focus_active_tab()` call from `on_mount` (let the handler do it after `_mounted` is set, or keep the direct call and guard the handler).

**3. OPEN QUESTION: Does `TabActivated` fire reliably for programmatic `tabbed.active` changes?** (Conflict: architecture vs code-quality)
Architecture reviewer assumes `TabActivated` fires for all `tabbed.active` assignments. Code-quality reviewer warns this may not be reliable across Textual versions. If it doesn't fire for programmatic changes, removing `_focus_active_tab()` from keyboard actions breaks tab switching silently.
- **Action:** Must verify empirically before committing to the refactor. Write a test that sets `tabbed.active` programmatically and asserts `TabActivated` is posted. If it doesn't fire, keep direct calls in actions and treat the handler as additive (mouse-only path).

### P2 — Important (Should Address)

**4. Private attribute `panel._file_list.focus()` needs public API** (Identified by 4 agents)
`app.py:334` reaches into `GitPanel`'s private `_file_list`. The mouse feature adds a second code path hitting this. `GitPanel` already has a `has_focus` property — it should also expose a `focus_default()` method.
- **Action:** Add `def focus_default(self) -> None: self._file_list.focus()` to `GitPanel`. Replace `panel._file_list.focus()` in `app.py:334` with `panel.focus_default()`.

**5. `_focus_active_tab()` has dual responsibility (focus + viewer content restore)** (Identified by 1 agent)
The function both routes focus AND loads viewer content. Making it the sole handler for `TabActivated` works but the dual responsibility makes future changes error-prone.
- **Action:** Consider splitting in a follow-up. Not blocking for this feature.

**6. `on_tree_node_highlighted` fires on mouse hover — rapid viewer loads** (Identified by 1 agent)
With mouse enabled, hovering over FileTree nodes fires continuous highlight events, each triggering `viewer.load_file()`. This could cause excessive I/O.
- **Action:** Add to "What We're NOT Doing" as a known limitation. Consider debouncing in a follow-up if user reports performance issues.

**7. Handler should guard against focus-mode** (Identified by 1 agent)
If `_focus_mode=True` and the handler somehow fires, it would try to focus hidden widgets.
- **Action:** Add `if self._focus_mode: return` guard in the handler.

**8. Handler signature must be correctly typed** (Identified by 2 agents)
`def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None` — CI runs typecheck.
- **Action:** Ensure correct type annotation in Step 1.3.

### P3 — Minor (Nice to Have)

**9. Missing RED-run checkpoint in TDD ordering** (Identified by 1 agent)
Step 1.1 writes tests but doesn't explicitly confirm they fail before implementation.
- **Action:** Add "run `make test`, confirm new tests fail" between Step 1.1 and Step 1.2.

**10. Pre-existing bare `except Exception:` pattern** (Identified by 2 agents)
Found at `app.py:64, 106, 143, 196, 244, 252, 274`. The new handler should not follow this pattern — use specific `NoMatches` exception.
- **Action:** Note for implementation; don't propagate the anti-pattern.

**11. Pre-existing: `_auto_select_done` initialized in `on_mount` not `__init__`** (Identified by 2 agents)
Addressed by P1 #2 fix above.

**12. Pre-existing: commit-label duplication in `git_status.py`** (Identified by 1 agent)
Three copies of the commit-label builder at lines 361, 448, 496. Unrelated to this feature.

**13. Tab selector for `pilot.click()` tests** (Identified by 1 agent)
Textual tab headers render as `Tab` widgets with IDs like `--content-tab-tab-files`. Tests should target these selectors.

### Open Questions (Updated)

| # | Question | Options | Source |
|---|----------|---------|--------|
| 1 | Does `TabActivated` fire for programmatic `tabbed.active` assignment? | A: Yes (refactor safe), B: No (keep direct calls, handler is additive) | CONFLICT: architecture vs code-quality — **must verify empirically** |
| 2 | Guard strategy for `on_mount` timing | A: `_mounted` flag in `__init__` (clean), B: Keep direct call in `on_mount` + guard handler | architecture, code-quality |
| 3 | Should `--no-mouse` CLI flag be added? | A: Yes (flexibility), B: No (YAGNI) — **Reviewers agree: B** | architecture, planning |
| 4 | Should `_focus_active_tab()` be split (focus vs viewer restore)? | A: Yes (SRP), B: No (follow-up) | patterns |

</details>
