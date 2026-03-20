# Tree-Based Commit Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ListView-based expand/collapse hack with a compound GitPanel (ListView for files + Tree for commits), fixing the multi-highlight bug and getting native expand/collapse behavior.

**Architecture:** GitPanel changes from a `ListView` subclass to a `Vertical` container. It composes a `ListView` (file sections) and a `Tree[str]` (commits). The app interacts with GitPanel through delegate methods and typed messages. j/k navigation auto-transfers focus between the two widgets at boundaries.

**Tech Stack:** Python 3.12, Textual 8.1.1 (`Tree`, `ListView`, `Vertical`), Rich

**Spec:** `docs/specs/2026-03-20-expandable-commit-review-design.md`

**Scope:** Only `git_status.py`, `app.py`, and their tests change. Git service, viewer, models, and FileTree are already done.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/perch/widgets/git_status.py` | Rewrite | Compound GitPanel with ListView + Tree, delegate API, messages |
| `src/perch/app.py` | Modify | Handle new GitPanel messages, remove name-string inspection |
| `tests/test_git_status.py` | Rewrite | Tests for new compound widget |
| `tests/test_app.py` | Modify | Tests for new event wiring |

---

## Textual API Reference

Tree messages (from `Tree[str]`):
- `Tree.NodeHighlighted(node)` — cursor moved to a node
- `Tree.NodeSelected(node)` — Enter pressed on a node
- `Tree.NodeExpanded(node)` — node expanded
- `Tree.NodeCollapsed(node)` — node collapsed

TreeNode API:
- `node.data` — the string data (`"commit:<hash>"` etc.)
- `node.add(label, data, allow_expand=True)` — add child node
- `node.add_leaf(label, data)` — add non-expandable child
- `node.remove()` / `node.remove_children()` — remove nodes
- `node.expand()` / `node.collapse()` / `node.toggle()` — expand/collapse
- `node.is_expanded` / `node.children` — state queries
- `node.label` / `node.set_label(text)` — label access

---

### Task 1: Rewrite GitPanel as Compound Widget

This is the core change. GitPanel becomes a `Vertical` container with an internal ListView and Tree.

**Files:**
- Rewrite: `src/perch/widgets/git_status.py`
- Rewrite: `tests/test_git_status.py`

- [ ] **Step 1: Write tests for the new compound GitPanel**

Key tests to write in `tests/test_git_status.py`:

```python
# Test that GitPanel composes both widgets
class TestGitPanelComposition:
    async def test_has_file_list_and_commit_tree(self, git_worktree):
        """GitPanel should contain a ListView and a Tree."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            # Internal widgets exist
            assert panel._file_list is not None
            assert panel._commit_tree is not None

# Test file sections still work
class TestFileListBehavior:
    async def test_file_sections_populated(self, git_worktree):
        """File sections should appear in the internal ListView."""
        # Create unstaged change
        (git_worktree / "hello.py").write_text("modified\n")
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            # Should have file items
            file_items = [
                node for node in panel._file_list._nodes
                if isinstance(node, ListItem) and node.name and not node.disabled
            ]
            assert len(file_items) > 0

# Test commit tree
class TestCommitTreeBehavior:
    async def test_commits_appear_as_tree_nodes(self, git_worktree):
        """Commits should appear as root nodes in the tree."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            root = panel._commit_tree.root
            commit_nodes = [
                n for n in root.children
                if n.data and n.data.startswith("commit:")
            ]
            assert len(commit_nodes) >= 1

    async def test_expand_commit_shows_files(self, git_worktree):
        """Expanding a commit node should add file children."""
        # Need a non-root commit (root commit has no parent for diff-tree)
        (git_worktree / "hello.py").write_text("modified\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "modify"], cwd=git_worktree, check=True)
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")
            panel.toggle_commit(commit_hash)
            await pilot.pause()
            assert commit_node.is_expanded
            file_children = [
                c for c in commit_node.children
                if c.data and c.data.startswith("commit-file:")
            ]
            assert len(file_children) >= 1

    async def test_accordion_collapses_previous(self, git_worktree):
        """Expanding one commit should collapse the previous."""
        (git_worktree / "f1.txt").write_text("1\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "c1"], cwd=git_worktree, check=True)
        (git_worktree / "f2.txt").write_text("2\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "c2"], cwd=git_worktree, check=True)
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            root = panel._commit_tree.root
            commits = [n for n in root.children if n.data and n.data.startswith("commit:")]
            h1 = commits[0].data.removeprefix("commit:")
            h2 = commits[1].data.removeprefix("commit:")
            panel.toggle_commit(h1)
            await pilot.pause()
            assert commits[0].is_expanded
            panel.toggle_commit(h2)
            await pilot.pause()
            assert commits[1].is_expanded
            assert not commits[0].is_expanded

# Test messages
class TestGitPanelMessages:
    async def test_commit_highlighted_posts_message(self, git_worktree):
        """Highlighting a commit node should post CommitHighlighted."""
        # This test verifies the message is posted — the app handler test is in test_app.py
        pass  # Tested via app integration

# Test delegate API
class TestGitPanelDelegateAPI:
    async def test_highlighted_item_name(self, git_worktree):
        """highlighted_item_name should return the data of the focused widget's selection."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            name = panel.highlighted_item_name()
            # Should return something (either a file or commit)
            assert name is not None

# Test refresh
class TestRefreshBehavior:
    async def test_refresh_files_preserves_tree(self, git_worktree):
        """refresh_files should not touch the commit tree."""
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            await pilot.pause()
            root = panel._commit_tree.root
            commit_count = len([n for n in root.children if n.data and n.data.startswith("commit:")])
            panel.refresh_files()
            await pilot.pause()
            await pilot.pause()
            new_count = len([n for n in root.children if n.data and n.data.startswith("commit:")])
            assert new_count == commit_count

# Test pagination
class TestPagination:
    async def test_sentinel_appears(self, git_worktree):
        """Sentinel node should appear when page is full."""
        for i in range(3):
            (git_worktree / f"p{i}.txt").write_text(f"{i}\n")
            subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
            subprocess.run(["git", "commit", "-m", f"c{i}"], cwd=git_worktree, check=True)
        app = PerchApp(git_worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one(GitPanel)
            panel._commit_page_size = 2
            panel.refresh_commits()
            await pilot.pause()
            await pilot.pause()
            root = panel._commit_tree.root
            sentinel = any(n.data == "load-more-commits" for n in root.children)
            assert sentinel
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_git_status.py -x -v`
Expected: FAIL — GitPanel is still a ListView

- [ ] **Step 3: Rewrite GitPanel**

Replace the entire `GitPanel` class in `src/perch/widgets/git_status.py`. Keep the helper functions (`_make_file_item`, `_make_section_header`, `_STATUS_STYLES`) and the ref watcher methods. The key structural change:

```python
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Tree

class CommitTree(Tree[str]):
    """Tree widget for commit history with hjkl navigation."""
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("l", "select_cursor", "Select", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]


class GitPanel(Vertical):
    """Compound widget: ListView (files) + Tree (commits)."""

    # Messages
    class FileSelected(Message): ...
    class CommitHighlighted(Message):
        def __init__(self, commit_hash: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash
    class CommitFileHighlighted(Message):
        def __init__(self, commit_hash: str, path: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash
            self.path = path
    class CommitToggled(Message):
        def __init__(self, commit_hash: str) -> None:
            super().__init__()
            self.commit_hash = commit_hash
    class SelectionRestored(Message): ...

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        Binding("f", "app.toggle_focus_mode", "Focus"),
        Binding("j", "cursor_down", "Navigate", key_display="hjkl/←↓↑→"),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield self._file_list  # ListView
        yield Label("\nRecent Commits", classes="section-header")
        yield self._commit_tree  # Tree[str]

    def __init__(self, worktree_root, ...) -> None:
        super().__init__(...)
        self._worktree_root = worktree_root
        self._file_list = ListView(id="git-file-list")
        self._commit_tree = CommitTree("Commits", id="git-commit-tree")
        self._commit_tree.show_root = False
        self._expanded_commit: str | None = None
        self._commit_page_size = 50
        self._commits_loaded = 0
        self._loading_more = False
```

Key methods to implement:
- `compose()` — yield file list, header label, commit tree
- `on_mount()` — initial refresh + start timers
- `_do_refresh()` — full refresh (files + commits)
- `refresh_files()` / `refresh_commits()` / `refresh_all()` — delegate methods
- `toggle_commit(hash)` — expand/collapse with accordion on the Tree
- `highlighted_item_name()` — return data from whichever widget has focus
- `on_tree_node_highlighted()` — post CommitHighlighted/CommitFileHighlighted messages
- `on_tree_node_selected()` — post CommitToggled message
- `on_list_view_selected()` — post FileSelected (files only)
- Cross-widget navigation: override `action_cursor_down`/`action_cursor_up` to transfer focus at boundaries
- `_build_commit_nodes(commits)` — populate tree root with commit nodes
- `_load_more_commits()` — pagination with `@work(thread=True)`
- Ref watcher methods (keep existing `_start_ref_watcher`, `_check_refs`, etc.)

For **cross-widget navigation** (j/k at boundaries):
```python
def action_cursor_down(self) -> None:
    """Move down — transfer focus from file list to tree at boundary."""
    if self._file_list.has_focus:
        if self._file_list.index is not None and self._file_list.index >= len(self._file_list) - 1:
            self._commit_tree.focus()
            self._commit_tree.action_cursor_down()  # highlight first node
            return
        self._file_list.action_cursor_down()
    elif self._commit_tree.has_focus:
        self._commit_tree.action_cursor_down()

def action_cursor_up(self) -> None:
    """Move up — transfer focus from tree to file list at boundary."""
    if self._commit_tree.has_focus:
        if self._commit_tree.cursor_line <= 0:
            self._file_list.focus()
            return
        self._commit_tree.action_cursor_up()
    elif self._file_list.has_focus:
        self._file_list.action_cursor_up()
```

For **tree event handling** (inside GitPanel):
```python
def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
    node = event.node
    if node.data is None:
        return
    if node.data.startswith("commit:"):
        commit_hash = node.data.removeprefix("commit:")
        self.post_message(self.CommitHighlighted(commit_hash))
    elif node.data.startswith("commit-file:"):
        parts = node.data.removeprefix("commit-file:").split(":", 1)
        if len(parts) == 2:
            self.post_message(self.CommitFileHighlighted(parts[0], parts[1]))
    elif node.data == "load-more-commits":
        self._load_more_commits()

def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
    node = event.node
    if node.data and node.data.startswith("commit:"):
        commit_hash = node.data.removeprefix("commit:")
        self.post_message(self.CommitToggled(commit_hash))
```

For **toggle_commit** (using native Tree expand/collapse):
```python
def toggle_commit(self, commit_hash: str) -> None:
    """Expand or collapse a commit with accordion behavior."""
    from perch.services.git import get_commit_files

    target = None
    for node in self._commit_tree.root.children:
        if node.data == f"commit:{commit_hash}":
            target = node
            break
    if target is None:
        return

    if target.is_expanded:
        target.collapse()
        self._expanded_commit = None
    else:
        # Accordion: collapse previous
        if self._expanded_commit:
            for node in self._commit_tree.root.children:
                if node.data == f"commit:{self._expanded_commit}" and node.is_expanded:
                    node.collapse()
                    break
        # Expand and populate children
        target.remove_children()
        try:
            files = get_commit_files(self._worktree_root, commit_hash)
        except RuntimeError:
            return
        for f in files:
            style = _STATUS_STYLES.get(f.status, "")
            label = Text()
            label.append(f"{f.status:<10}", style=style)
            label.append(f" {f.path}")
            target.add_leaf(label, data=f"commit-file:{commit_hash}:{f.path}")
        target.expand()
        self._expanded_commit = commit_hash
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_git_status.py -x -v`
Expected: PASS

- [ ] **Step 5: Run full test suite (some app.py tests may fail — that's expected)**

Run: `uv run pytest tests/ -x --ignore=tests/test_app.py -v`
Expected: PASS (ignoring app tests which still use old API)

- [ ] **Step 6: Commit**

```bash
git add src/perch/widgets/git_status.py tests/test_git_status.py
git commit -m "feat: rewrite GitPanel as compound widget with ListView (files) + Tree (commits)"
```

---

### Task 2: Update App Event Handlers

**Files:**
- Modify: `src/perch/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write tests for new event wiring**

```python
class TestCommitTreeEvents:
    async def test_commit_highlighted_loads_summary(self, git_worktree):
        """CommitHighlighted should trigger summary loading."""
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            viewer = pilot.app.query_one(Viewer)
            panel = pilot.app.query_one(GitPanel)
            await pilot.pause()
            # Post a CommitHighlighted message
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")
            panel.post_message(GitPanel.CommitHighlighted(commit_hash))
            await pilot.pause()
            await pilot.pause()
            # Viewer should have updated (summary loaded in background)

    async def test_commit_toggled_expands(self, git_worktree):
        """CommitToggled should expand the commit."""
        (git_worktree / "hello.py").write_text("changed\n")
        subprocess.run(["git", "add", "."], cwd=git_worktree, check=True)
        subprocess.run(["git", "commit", "-m", "change"], cwd=git_worktree, check=True)
        app = PerchApp(git_worktree)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = pilot.app.query_one(GitPanel)
            await pilot.pause()
            root = panel._commit_tree.root
            commit_node = next(
                n for n in root.children if n.data and n.data.startswith("commit:")
            )
            commit_hash = commit_node.data.removeprefix("commit:")
            panel.post_message(GitPanel.CommitToggled(commit_hash))
            await pilot.pause()
            assert panel._expanded_commit == commit_hash
```

- [ ] **Step 2: Update app.py event handlers**

Replace the commit-related parts of the event handlers:

```python
# New handlers for GitPanel messages
def on_git_panel_commit_highlighted(self, event: GitPanel.CommitHighlighted) -> None:
    """Load commit summary when a commit is highlighted in the tree."""
    viewer = self.query_one(Viewer)
    viewer.worktree_root = self.worktree_path
    self._load_commit_summary(event.commit_hash)

def on_git_panel_commit_file_highlighted(self, event: GitPanel.CommitFileHighlighted) -> None:
    """Load file diff when a commit-file is highlighted in the tree."""
    viewer = self.query_one(Viewer)
    viewer.worktree_root = self.worktree_path
    viewer.load_commit_file_diff(event.commit_hash, event.path)

def on_git_panel_commit_toggled(self, event: GitPanel.CommitToggled) -> None:
    """Expand or collapse a commit in the tree."""
    panel = self.query_one(GitPanel)
    panel.toggle_commit(event.commit_hash)
```

Simplify `on_list_view_highlighted` — remove all commit handling (now handled by tree messages):
```python
def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
    """Preview files when navigating the git file list."""
    try:
        if self.query_one(TabbedContent).active != "tab-git":
            return
    except Exception:
        return
    item = event.item
    if not isinstance(item, ListItem) or item.name is None:
        return
    viewer = self.query_one(Viewer)
    file_path = self.worktree_path / item.name
    staged = getattr(item, "_staged", False)
    if file_path.is_file():
        viewer.load_file(file_path)
    else:
        viewer.show_deleted_file_diff(file_path, item.name, staged=staged)
```

Simplify `on_list_view_selected` — remove commit handling:
```python
def on_list_view_selected(self, event: ListView.Selected) -> None:
    """Focus the viewer when a file is selected."""
    try:
        if self.query_one(TabbedContent).active == "tab-git":
            self.query_one(Viewer).focus()
    except Exception:
        pass
```

Update `_show_current_git_item` to use `panel.highlighted_item_name()`:
```python
def _show_current_git_item(self, panel: GitPanel, viewer: Viewer) -> None:
    name = panel.highlighted_item_name()
    if name is None:
        viewer.show_clean_tree()
    elif name.startswith("commit:"):
        commit_hash = name.removeprefix("commit:")
        viewer.worktree_root = self.worktree_path
        self._load_commit_summary(commit_hash)
    elif name.startswith("commit-file:"):
        parts = name.removeprefix("commit-file:").split(":", 1)
        if len(parts) == 2:
            viewer.worktree_root = self.worktree_path
            viewer.load_commit_file_diff(parts[0], parts[1])
    else:
        file_path = self.worktree_path / name
        staged = False  # Can't determine staged from name alone — acceptable
        if file_path.is_file():
            viewer.load_file(file_path)
        else:
            viewer.show_deleted_file_diff(file_path, name, staged=staged)
```

Remove stale `n`/`p` bindings from app BINDINGS if still present.

- [ ] **Step 3: Update existing app tests**

Remove/update tests that reference old commit-handling patterns:
- Tests that check `on_list_view_highlighted` for commits → now handled by tree
- Tests that check `on_list_view_selected` for commits → now handled by tree
- Update `_show_current_git_item` tests

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -x -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/perch/app.py tests/test_app.py
git commit -m "feat: update app event handlers for Tree-based commit panel"
```

---

### Task 3: Coverage and Cleanup

**Files:**
- All modified files
- Tests

- [ ] **Step 1: Run full test suite with coverage**

Run: `uv run pytest tests/ --cov=src/perch --cov-report=term-missing --no-header -q`
Expected: All tests pass

- [ ] **Step 2: Check coverage threshold**

If below 95%, add targeted tests for uncovered paths in the new code.

- [ ] **Step 3: Run linter**

Run: `uv run ruff check src/ tests/`
Fix any issues.

- [ ] **Step 4: Verify the app runs**

Run: `uv run perch` (or however the app is launched) and manually verify:
- Files tab works as before
- Git tab shows file list + commit tree
- j/k navigates between file list and commit tree
- Enter on a commit expands it (shows changed files)
- Highlighting a commit shows summary in viewer
- Highlighting a commit-file shows its diff in viewer
- Accordion works (only one commit expanded)
- r refreshes

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: coverage and cleanup for tree-based commit review"
```
