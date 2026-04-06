from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, ListItem, ListView, TabbedContent, TabPane

from perch.commands import DiscoveryCommandProvider
from perch.services.editor import open_file
from perch.widgets.file_search import FileSearchScreen
from perch.widgets.file_tree import FileTree
from perch.widgets.git_status import GitPanel
from perch.widgets.github_panel import ClickableItem, GitHubPanel
from perch.widgets.help_screen import HelpScreen
from perch.widgets.splitter import DraggableSplitter
from perch.widgets.viewer import Viewer

_AUTO_SELECT_INTERVAL = 0.15  # seconds between retries
_AUTO_SELECT_MAX_ATTEMPTS = 20  # give up after ~3 seconds


class PerchApp(App):
    CSS_PATH = "app.tcss"
    COMMANDS = App.COMMANDS | {DiscoveryCommandProvider}
    COMMAND_PALETTE_BINDING = "ctrl+shift+p"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", key_display="^q", show=False),
        Binding("tab", "focus_next_pane", "Switch Pane", priority=True, show=False),
        Binding(
            "left_square_bracket",
            "prev_tab",
            "Prev/Next Tab",
            key_display="[/]",
            show=False,
        ),
        Binding("right_square_bracket", "next_tab", "Next Tab", show=False),
        Binding("f", "toggle_focus_mode", "Focus Mode", show=False),
        Binding("ctrl+p", "file_search", "File Search", show=False),
        Binding("o", "open_editor", "Open", show=False),
        Binding("minus", "shrink_pane", "Shrink", show=False, key_display="-"),
        Binding("equals_sign", "grow_pane", "Grow", show=False, key_display="="),
    ]

    BINDING_REGISTRY: ClassVar[dict[str, list[Binding]]] = {
        "Global": [
            Binding("ctrl+q", "quit", "Quit", key_display="Ctrl+Q"),
            Binding("tab", "focus_next_pane", "Switch Pane", key_display="Tab"),
            Binding(
                "left_square_bracket", "prev_tab", "Prev/Next Tab", key_display="[/]"
            ),
            Binding("ctrl+p", "file_search", "File Search", key_display="Ctrl+P"),
            Binding("c", "copy", "Copy", key_display="c"),
            Binding("question_mark", "show_help", "Help", key_display="?"),
            Binding("f", "toggle_focus_mode", "Focus Mode", key_display="f"),
            Binding("minus", "shrink_pane", "Shrink Pane", key_display="-"),
            Binding("equals_sign", "grow_pane", "Grow Pane", key_display="="),
        ],
        "File Tree": [
            Binding("r", "refresh", "Refresh", key_display="r"),
            Binding("o", "open_editor", "Open in Editor", key_display="o"),
            Binding(
                "j",
                "cursor_down",
                "Navigate",
                key_display="hjkl/\u2190\u2193\u2191\u2192",
            ),
        ],
        "Viewer": [
            Binding("d", "toggle_diff", "Toggle Diff", key_display="d"),
            Binding("s", "toggle_diff_layout", "Diff Layout", key_display="s"),
            Binding("p", "toggle_markdown_preview", "Preview", key_display="p"),
            Binding("e", "open_editor", "Open in Editor", key_display="e"),
            Binding(
                "j",
                "scroll_down",
                "Navigate",
                key_display="hjkl/\u2190\u2193\u2191\u2192",
            ),
            Binding("shift+drag", "noop", "Select", key_display="\u21e7+Drag"),
            Binding("f20", "noop", "Open URL/File", key_display="\u2318+Click"),
        ],
        "Git": [
            Binding("r", "refresh", "Refresh", key_display="r"),
            Binding("l", "select_cursor", "Select", key_display="l"),
            Binding(
                "j",
                "cursor_down",
                "Navigate",
                key_display="hjkl/\u2190\u2193\u2191\u2192",
            ),
        ],
        "GitHub": [
            Binding("r", "refresh", "Refresh", key_display="r"),
            Binding("o", "open_in_browser", "Open in Browser", key_display="o"),
            Binding(
                "j",
                "cursor_down",
                "Navigate",
                key_display="hjkl/\u2190\u2193\u2191\u2192",
            ),
        ],
    }

    def __init__(self, worktree_path: Path, editor: str | None = None) -> None:
        super().__init__()
        self.worktree_path = worktree_path
        self.editor = editor
        self._focus_mode = False
        self._branch: str | None = None
        self._files_tab_last_path: Path | None = None
        self._auto_select_done = False
        self._auto_select_attempts = 0
        self._mounted = False
        self._tab_click_pending = False
        try:
            from perch.services.git import get_current_branch, get_worktree_root

            git_root = get_worktree_root(worktree_path)
            self._branch = get_current_branch(git_root)
        except (RuntimeError, FileNotFoundError):
            pass

    def watch_theme(self, _value: str | None = None) -> None:
        """Re-render the viewer when the app theme changes."""
        try:
            viewer = self.query_one(Viewer)
        except Exception:
            return
        viewer.refresh_content()

    def on_mount(self) -> None:
        if self._branch:
            self.title = f"perch — {self._branch}"
        else:
            self.title = "perch"
        self.sub_title = str(self.worktree_path)
        self.query_one(TabbedContent).active = "tab-files"
        self._focus_active_tab()
        self.set_timer(_AUTO_SELECT_INTERVAL, self._auto_select_first_node)
        self._mounted = True

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            yield Viewer(worktree_root=self.worktree_path, id="left-pane")
            yield DraggableSplitter()
            with TabbedContent(id="sidebar"):
                with TabPane("\uf0c5", id="tab-files"):
                    yield FileTree(self.worktree_path)
                with TabPane("\ue725", id="tab-git"):
                    yield GitPanel(self.worktree_path)
                with TabPane("\uf09b", id="tab-github"):
                    yield GitHubPanel(self.worktree_path)
        yield Footer(compact=True, show_command_palette=False)

    # ------------------------------------------------------------------
    # Auto-select first file on startup
    # ------------------------------------------------------------------

    def _auto_select_first_node(self) -> None:
        """Highlight the first non-root node in the tree after it loads."""
        if self._auto_select_done:
            return

        try:
            tree = self.query_one(FileTree)
            viewer = self.query_one(Viewer)
        except Exception:
            return  # Widget not available (e.g. during shutdown)

        self._auto_select_attempts += 1

        if tree.last_line <= 0:
            if self._auto_select_attempts < _AUTO_SELECT_MAX_ATTEMPTS:
                self.set_timer(_AUTO_SELECT_INTERVAL, self._auto_select_first_node)
            else:
                self._auto_select_done = True
                viewer.show_empty_directory()
            return

        self._auto_select_done = True

        # Bail out if something was already loaded (e.g. user switched tabs)
        if viewer._current_path is not None or viewer._diff_mode:
            return

        # Select the first non-root node (file or folder)
        for line in range(tree.last_line + 1):
            node = tree.get_node_at_line(line)
            if node is None or node.data is None or node is tree.root:
                continue
            tree.cursor_line = line
            return

        viewer.show_empty_directory()

    # ------------------------------------------------------------------
    # Tree ↔ viewer sync
    # ------------------------------------------------------------------

    def _sync_tree_to_path(self, path: Path) -> None:
        """Move the file tree cursor to the node matching *path*."""
        try:
            tree = self.query_one(FileTree)
        except Exception:
            return
        for line in range(tree.last_line + 1):
            node = tree.get_node_at_line(line)
            if node is None or node.data is None:
                continue
            node_path = node.data.path if hasattr(node.data, "path") else node.data
            if isinstance(node_path, Path) and node_path == path:
                tree.cursor_line = line
                return

    # ------------------------------------------------------------------
    # Event handlers — sidebar selections → viewer
    # ------------------------------------------------------------------

    def on_git_panel_file_selected(self, event: GitPanel.FileSelected) -> None:
        """Handle file selection in the git tab — open in viewer."""
        file_path = self.worktree_path / event.path
        viewer = self.query_one(Viewer)
        if file_path.is_file():
            viewer.load_file(file_path)
        else:
            viewer.show_deleted_file_diff(file_path, event.path, staged=event.staged)

    def on_git_panel_commit_highlighted(
        self, event: GitPanel.CommitHighlighted
    ) -> None:
        """Load commit summary when a commit is highlighted in the tree."""
        if self.query_one(TabbedContent).active != "tab-git":
            return
        viewer = self.query_one(Viewer)
        viewer.worktree_root = self.worktree_path
        self._load_commit_summary(event.commit_hash)

    def on_git_panel_commit_file_highlighted(
        self, event: GitPanel.CommitFileHighlighted
    ) -> None:
        """Load file diff when a commit-file is highlighted in the tree."""
        if self.query_one(TabbedContent).active != "tab-git":
            return
        viewer = self.query_one(Viewer)
        viewer.worktree_root = self.worktree_path
        viewer.load_commit_file_diff(event.commit_hash, event.path)

    def on_git_panel_commit_toggled(self, event: GitPanel.CommitToggled) -> None:
        """Expand or collapse a commit in the tree."""
        panel = self.query_one(GitPanel)
        panel.toggle_commit(event.commit_hash)

    def on_tree_node_highlighted(self, event) -> None:
        """Update the viewer when a FileTree node is highlighted.

        Only reacts when the Files tab is active to prevent background
        tree refreshes (watchfiles, git status) from overwriting the
        viewer while the user is on another tab.
        """
        try:
            if self.query_one(TabbedContent).active != "tab-files":
                return
        except Exception:
            return  # Not yet composed during early startup
        node = event.node
        if node.data is None:
            return
        path = node.data.path if hasattr(node.data, "path") else node.data
        try:
            viewer = self.query_one(Viewer)
        except Exception:
            return
        if isinstance(path, Path) and path.is_file():
            viewer.load_file(path)
            self._files_tab_last_path = path
        elif isinstance(path, Path) and path.is_dir():
            viewer.show_folder(path)
            self._files_tab_last_path = path

    def on_directory_tree_file_selected(self, event) -> None:
        """Focus the viewer when a file is selected with enter."""
        viewer = self.query_one(Viewer)
        viewer.load_file(event.path)
        viewer.focus()

    def on_git_hub_panel_preview_requested(
        self, event: GitHubPanel.PreviewRequested
    ) -> None:
        """Show preview content in the viewer when a PR item is highlighted."""
        if self.query_one(TabbedContent).active != "tab-github":
            return
        viewer = self.query_one(Viewer)
        if event.preview_kind == "pr_body":
            viewer.show_pr_body(event.body, title=event.title)
        elif event.preview_kind == "review":
            viewer.show_review(event.body, title=event.title)
        elif event.preview_kind == "comment":
            viewer.show_review(event.body, title=event.title)
        elif event.preview_kind == "ci_check":
            viewer.show_ci_loading(title=event.title)
            viewer.fetch_ci_log(event.url)

    @work(thread=True, exclusive=True, group="commit-summary")
    def _load_commit_summary(self, commit_hash: str) -> None:
        """Load commit summary in background and update viewer."""
        from perch.services.git import get_commit_summary

        try:
            summary = get_commit_summary(self.worktree_path, commit_hash)
        except RuntimeError:
            return
        if self.query_one(TabbedContent).active != "tab-git":
            return
        self.call_from_thread(self.query_one(Viewer).show_commit_summary, summary)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Focus the viewer when a file is selected."""
        try:
            if self.query_one(TabbedContent).active == "tab-git":
                self.query_one(Viewer).focus()
        except Exception:
            pass

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

    def on_git_panel_selection_restored(
        self, event: GitPanel.SelectionRestored
    ) -> None:
        """Sync the viewer after an async git refresh, but only when Git tab is active."""
        try:
            if self.query_one(TabbedContent).active != "tab-git":
                return
            panel = self.query_one(GitPanel)
            viewer = self.query_one(Viewer)
        except Exception:
            return
        self._show_current_git_item(panel, viewer)

    # ------------------------------------------------------------------
    # Tab navigation
    # ------------------------------------------------------------------

    _TAB_ORDER = ["tab-files", "tab-git", "tab-github"]

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        """Focus the correct widget when the user clicks a tab header.

        Textual fires ``TabActivated`` for programmatic ``tabbed.active``
        changes, descendant focus switches **and** mouse clicks on tab
        headers.  We only want to react to mouse clicks; the keyboard
        actions already call ``_focus_active_tab()`` synchronously.

        To distinguish a click from other sources we check
        ``_tab_click_pending``, which is set by ``on_click`` when the
        click target is inside the sidebar tabs.
        """
        if not self._tab_click_pending:
            return
        self._tab_click_pending = False
        if self._focus_mode:
            return
        try:
            self._focus_active_tab()
        except Exception:
            return

    def on_click(self, event) -> None:
        """Focus the clicked pane and detect tab header clicks."""
        widget = event.widget
        from textual.widgets._tabbed_content import ContentTab

        while widget is not None:
            if isinstance(widget, ContentTab):
                self._tab_click_pending = True
                return
            if isinstance(widget, Viewer):
                widget.focus()
                return
            if isinstance(widget, (FileTree, GitPanel, GitHubPanel)):
                if hasattr(widget, "focus_default"):
                    widget.focus_default()
                else:
                    widget.focus()
                return
            if widget is self:
                break
            widget = widget.parent

    def action_next_tab(self) -> None:
        """Switch to the next sidebar tab."""
        tabbed = self.query_one(TabbedContent)
        try:
            idx = self._TAB_ORDER.index(tabbed.active)
        except ValueError:
            idx = -1
        tabbed.active = self._TAB_ORDER[(idx + 1) % len(self._TAB_ORDER)]
        self._focus_active_tab()

    def action_prev_tab(self) -> None:
        """Switch to the previous sidebar tab."""
        tabbed = self.query_one(TabbedContent)
        try:
            idx = self._TAB_ORDER.index(tabbed.active)
        except ValueError:
            idx = 1
        tabbed.active = self._TAB_ORDER[(idx - 1) % len(self._TAB_ORDER)]
        self._focus_active_tab()

    def action_focus_next_pane(self) -> None:
        """Move focus to the other pane."""
        viewer = self.query_one("#left-pane", Viewer)
        if viewer.has_focus:
            self._focus_active_tab()
        else:
            viewer.focus()

    def _focus_active_tab(self) -> None:
        """Focus the active sidebar tab and restore its viewer content."""
        tabbed = self.query_one(TabbedContent)
        active = tabbed.active
        viewer = self.query_one(Viewer)

        if active == "tab-files":
            tree = self.query_one(FileTree)
            tree.focus()
            if tree.cursor_line == -1:
                tree.cursor_line = 0
            # Restore the viewer from cached path or current tree cursor
            if self._files_tab_last_path and self._files_tab_last_path.exists():
                if self._files_tab_last_path.is_file():
                    viewer.load_file(self._files_tab_last_path)
                else:
                    viewer.show_folder(self._files_tab_last_path)
                self._sync_tree_to_path(self._files_tab_last_path)
            else:
                self._show_current_tree_node(tree, viewer)
        elif active == "tab-git":
            panel = self.query_one(GitPanel)
            panel.focus_default()
            self._show_current_git_item(panel, viewer)
        elif active == "tab-github":
            github = self.query_one(GitHubPanel)
            github.focus()
            # Re-apply highlight by toggling the index so the reactive
            # watcher fires and renders the highlight on the visible tab.
            idx = github.index
            if idx is not None:
                github.index = None
                github.index = idx
            self._show_current_github_item(github, viewer)
        else:
            self.query_one(FileTree).focus()

    def _show_current_tree_node(self, tree: FileTree, viewer: Viewer) -> None:
        """Load the tree's currently highlighted node into the viewer."""
        node = tree.get_node_at_line(tree.cursor_line)
        if node is None or node.data is None:
            viewer.show_placeholder()
            return
        path = node.data.path if hasattr(node.data, "path") else node.data
        if isinstance(path, Path) and path.is_file():
            viewer.load_file(path)
            self._files_tab_last_path = path
        elif isinstance(path, Path) and path.is_dir():
            viewer.show_folder(path)
        else:
            viewer.show_placeholder()

    def _show_current_git_item(self, panel: GitPanel, viewer: Viewer) -> None:
        """Load the git panel's currently highlighted item into the viewer."""
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
            staged = False
            if file_path.is_file():
                viewer.load_file(file_path)
            else:
                viewer.show_deleted_file_diff(file_path, name, staged=staged)

    def _show_current_github_item(self, github: GitHubPanel, viewer: Viewer) -> None:
        """Load the GitHub panel's currently highlighted item into the viewer."""
        item = github.highlighted_child
        if not isinstance(item, ClickableItem) or not item.preview_kind:
            viewer.show_placeholder()
            return
        body = item.preview_body
        if item.preview_kind == "pr_body" and github._pr_context:
            body = github._pr_context.body
        if item.preview_kind == "pr_body":
            viewer.show_pr_body(body, title=item.preview_title)
        elif item.preview_kind in ("review", "comment"):
            viewer.show_review(body, title=item.preview_title)
        elif item.preview_kind == "ci_check":
            viewer.show_ci_loading(title=item.preview_title)
            viewer.fetch_ci_log(item.url)

    # ------------------------------------------------------------------
    # File search
    # ------------------------------------------------------------------

    def action_file_search(self) -> None:
        """Open the fuzzy file search modal."""
        self.push_screen(FileSearchScreen(self.worktree_path), self._on_file_selected)

    def _on_file_selected(self, result: str | None) -> None:
        """Handle the result from the file search modal."""
        if result is not None:
            path = self.worktree_path / result
            if path.is_file():
                self.query_one(Viewer).load_file(path)
                self._files_tab_last_path = path
                self._sync_tree_to_path(path)

    def action_open_editor(self) -> None:
        """Open the currently highlighted file in the external editor."""
        viewer = self.query_one(Viewer)
        if viewer._current_path is not None:
            try:
                from perch.services.git import get_worktree_root

                repo_root = get_worktree_root(viewer._current_path.parent)
            except (RuntimeError, FileNotFoundError):
                repo_root = None
            open_file(self.editor, viewer._current_path, repo_root)

    # ------------------------------------------------------------------
    # Help screen
    # ------------------------------------------------------------------

    def action_show_help(self) -> None:
        """Open the help screen modal."""
        self.push_screen(HelpScreen())

    def action_copy(self) -> None:
        """Copy context-dependent text to clipboard.

        File tree / git file list → absolute path
        Commit tree              → commit SHA
        GitHub panel             → item URL
        """
        text: str | None = None
        tabbed = self.query_one(TabbedContent)

        if tabbed.active == "tab-files":
            tree = self.query_one(FileTree)
            node = tree.cursor_node
            if node is not None and hasattr(node.data, "path"):
                text = str(node.data.path)
        elif tabbed.active == "tab-git":
            panel = self.query_one(GitPanel)
            name = panel.highlighted_item_name()
            if name is not None:
                if name.startswith("commit:"):
                    text = name.removeprefix("commit:")
                elif name.startswith("commit-file:"):
                    text = str(self.worktree_path / name.split(":", 2)[-1])
                else:
                    text = str(self.worktree_path / name)
        elif tabbed.active == "tab-github":
            github = self.query_one(GitHubPanel)
            item = github.highlighted_child
            if isinstance(item, ClickableItem) and item.url:
                text = item.url

        if text:
            self.copy_to_clipboard(text)
            self.notify(f"Copied: {text}", timeout=2)

    # ------------------------------------------------------------------
    # Viewer action delegates
    # ------------------------------------------------------------------

    def action_toggle_diff(self) -> None:
        """Toggle diff view in the viewer (command palette entry)."""
        viewer = self.query_one(Viewer)
        viewer.action_toggle_diff()
        if viewer._diff_mode:
            viewer.focus()

    def action_toggle_diff_layout(self) -> None:
        """Toggle diff layout in the viewer (command palette entry)."""
        self.query_one(Viewer).action_toggle_diff_layout()

    def action_toggle_markdown_preview(self) -> None:
        """Toggle markdown preview in the viewer (command palette entry)."""
        self.query_one(Viewer).action_toggle_markdown_preview()

    # ------------------------------------------------------------------
    # Focus mode & pane resizing
    # ------------------------------------------------------------------

    def action_toggle_focus_mode(self) -> None:
        """Toggle the sidebar and splitter to give the left pane full width."""
        self._focus_mode = not self._focus_mode
        sidebar = self.query_one("#sidebar", TabbedContent)
        splitter = self.query_one(DraggableSplitter)
        viewer = self.query_one("#left-pane", Viewer)

        if self._focus_mode:
            sidebar.display = False
            splitter.display = False
            viewer.styles.width = "100%"
            viewer.focus()
        else:
            sidebar.display = True
            splitter.display = True
            viewer.styles.width = "75%"
            self._focus_active_tab()

    _RESIZE_STEP = 5  # columns per keypress

    def _focused_pane_is_left(self) -> bool:
        """Return True if the left pane (viewer) currently has focus."""
        viewer = self.query_one("#left-pane", Viewer)
        return viewer.has_focus

    def action_shrink_pane(self) -> None:
        """Shrink whichever pane is focused."""
        if self._focus_mode:
            return
        delta = (
            -self._RESIZE_STEP if self._focused_pane_is_left() else self._RESIZE_STEP
        )
        self.query_one(DraggableSplitter).resize_left_pane(delta)

    def action_grow_pane(self) -> None:
        """Grow whichever pane is focused."""
        if self._focus_mode:
            return
        delta = (
            self._RESIZE_STEP if self._focused_pane_is_left() else -self._RESIZE_STEP
        )
        self.query_one(DraggableSplitter).resize_left_pane(delta)
