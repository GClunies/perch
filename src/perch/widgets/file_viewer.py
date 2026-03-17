"""File viewer widget with syntax highlighting and line numbers."""

from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, VerticalScroll
from textual.widgets import Static

MAX_LINES = 10_000
BINARY_CHECK_SIZE = 8192


def is_binary(path: Path) -> bool:
    """Check if a file is binary by looking for null bytes in the first 8KB."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_CHECK_SIZE)
        return b"\x00" in chunk
    except OSError:
        return False


def read_file_content(path: Path) -> tuple[str, bool]:
    """Read file text, returning (content, was_truncated).

    Caps output at MAX_LINES. Uses 'replace' for encoding errors.
    """
    text = path.read_text(errors="replace")
    lines = text.splitlines(keepends=True)
    truncated = len(lines) > MAX_LINES
    if truncated:
        text = "".join(lines[:MAX_LINES])
    return text, truncated


def render_diff(diff_text: str, dark: bool = True) -> Text:
    """Render unified diff text with background-colored lines.

    Added lines get a green background, removed lines get a red background,
    hunk headers get a blue background, and context lines are unstyled.
    """
    if dark:
        add_style = "on #1a3a1a"
        del_style = "on #3a1a1a"
        hunk_style = "on #1a1a3a"
        meta_style = "bold"
    else:
        add_style = "on #d4ffd4"
        del_style = "on #ffd4d4"
        hunk_style = "on #d4d4ff"
        meta_style = "bold"

    result = Text()
    for i, line in enumerate(diff_text.splitlines()):
        if i > 0:
            result.append("\n")
        if line.startswith("+++") or line.startswith("---"):
            result.append(line, style=meta_style)
        elif line.startswith("+"):
            result.append(line, style=add_style)
        elif line.startswith("-"):
            result.append(line, style=del_style)
        elif line.startswith("@@"):
            result.append(line, style=hunk_style)
        else:
            result.append(line)
    return result


def parse_diff_sides(diff_text: str, dark: bool = True) -> tuple[Text, Text]:
    """Parse unified diff text into left (old) and right (new) Rich Text objects.

    Returns two Text objects with background-colored lines.
    Lines are padded with blanks to maintain vertical alignment.
    """
    if dark:
        add_style = "on #1a3a1a"
        del_style = "on #3a1a1a"
        hunk_style = "on #1a1a3a"
        meta_style = "bold"
    else:
        add_style = "on #d4ffd4"
        del_style = "on #ffd4d4"
        hunk_style = "on #d4d4ff"
        meta_style = "bold"

    left = Text()
    right = Text()
    first = True
    for line in diff_text.splitlines():
        if not first:
            left.append("\n")
            right.append("\n")
        first = False
        if line.startswith("--- "):
            left.append(line, style=meta_style)
        elif line.startswith("+++ "):
            right.append(line, style=meta_style)
        elif line.startswith("@@"):
            left.append(line, style=hunk_style)
            right.append(line, style=hunk_style)
        elif line.startswith("-"):
            left.append(line, style=del_style)
        elif line.startswith("+"):
            right.append(line, style=add_style)
        else:
            left.append(line)
            right.append(line)
    return left, right


class SyncedDiffView(ScrollableContainer):
    """A focusable container that scrolls two diff panes in sync."""

    BINDINGS = [
        Binding("up", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("left", "scroll_left", "Scroll Left", show=False),
        Binding("right", "scroll_right", "Scroll Right", show=False),
        Binding("home", "scroll_home", "Scroll Home", show=False),
        Binding("end", "scroll_end", "Scroll End", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    can_focus = True

    def compose(self):
        with Horizontal(id="diff-panels"):
            with VerticalScroll(id="diff-left"):
                yield Static("", id="diff-left-content")
            with VerticalScroll(id="diff-right"):
                yield Static("", id="diff-right-content")

    def on_mount(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.watch(left, "scroll_y", self._sync_scroll_y)
        left.watch(left, "scroll_x", self._sync_scroll_x)

    def _sync_scroll_y(self, value: float) -> None:
        right = self.query_one("#diff-right", VerticalScroll)
        if right.scroll_y != value:
            right.scroll_to(y=value, animate=False)

    def _sync_scroll_x(self, value: float) -> None:
        right = self.query_one("#diff-right", VerticalScroll)
        if right.scroll_x != value:
            right.scroll_to(x=value, animate=False)

    def action_scroll_up(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_up(animate=False)

    def action_scroll_down(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_down(animate=False)

    def action_scroll_left(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_left(animate=False)

    def action_scroll_right(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_right(animate=False)

    def action_scroll_home(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_end(animate=False)

    def action_page_up(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_page_up(animate=False)

    def action_page_down(self) -> None:
        left = self.query_one("#diff-left", VerticalScroll)
        left.scroll_page_down(animate=False)


class FileViewer(VerticalScroll):
    """Displays file content with syntax highlighting and line numbers."""

    BINDINGS = [
        ("d", "toggle_diff", "Toggle Diff"),
        ("s", "toggle_diff_layout", "Diff Layout"),
        ("n", "next_diff_file", "Next File"),
        ("p", "prev_diff_file", "Prev File"),
        ("e", "app.open_editor", "Editor"),
    ]

    def __init__(
        self,
        *,
        worktree_root: Path | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._content = Static("No file selected", id="file-content")
        self._current_path: Path | None = None
        self.worktree_root: Path | None = worktree_root
        self._diff_mode: bool = False
        self._diff_layout: str = "unified"
        self._diff_file_offsets: list[int] = []
        self._diff_file_index: int = 0

    def _get_syntax_theme(self) -> str:
        """Return a Pygments theme appropriate for the current app theme."""
        try:
            if self.app.current_theme.dark:
                return "monokai"
            return "default"
        except Exception:
            return "monokai"

    def _get_background_color(self) -> str:
        """Return the Textual theme's surface color for Syntax background.

        This ensures the syntax highlighting background matches the app theme
        instead of using the Pygments theme's default background.
        """
        try:
            surface = self.app.current_theme.surface
            if surface:
                return surface
        except Exception:
            pass
        return ""

    def _is_dark_theme(self) -> bool:
        """Return True if the current app theme is dark."""
        try:
            return self.app.current_theme.dark
        except Exception:
            return True

    def compose(self):
        yield self._content
        yield SyncedDiffView(id="diff-container")

    def _show_content_view(self) -> None:
        """Show the main content area and hide the diff container."""
        self._content.display = True
        try:
            self.query_one("#diff-container").display = False
        except Exception:
            pass

    def _show_side_by_side_view(self, diff_text: str) -> None:
        """Parse diff and show in side-by-side layout."""
        self._content.display = False
        diff_view = self.query_one("#diff-container", SyncedDiffView)
        diff_view.display = True

        dark = self._is_dark_theme()
        left_text, right_text = parse_diff_sides(diff_text, dark=dark)

        diff_view.query_one("#diff-left-content", Static).update(left_text)
        diff_view.query_one("#diff-right-content", Static).update(right_text)

        for panel_id in ("#diff-left", "#diff-right"):
            try:
                diff_view.query_one(panel_id, VerticalScroll).scroll_home(animate=False)
            except Exception:
                pass

        diff_view.focus()

    def load_file(self, path: Path) -> None:
        """Load and display a file with syntax highlighting."""
        self._current_path = path
        self._diff_mode = False
        self._diff_layout = "unified"
        self._show_content_view()

        if not path.is_file():
            self._content.update("Not a file")
            return

        if is_binary(path):
            self._content.update(
                Text("Binary file — cannot display", style="dim italic")
            )
            return

        try:
            text, truncated = read_file_content(path)
        except OSError as e:
            self._content.update(f"Error reading file: {e}")
            return

        lexer = Syntax.guess_lexer(str(path))
        syntax = Syntax(
            text,
            lexer,
            line_numbers=True,
            word_wrap=False,
            theme=self._get_syntax_theme(),
            background_color=self._get_background_color(),
        )

        if truncated:
            warning = Text(
                f"\n--- File truncated: showing first {MAX_LINES:,} lines ---",
                style="bold yellow",
            )
            self._content.update(Group(syntax, warning))
        else:
            self._content.update(syntax)

        self.scroll_home(animate=False)

    def _load_diff(self) -> None:
        """Load and display the diff for the current file."""
        if self._current_path is None or self.worktree_root is None:
            self._show_content_view()
            self._content.update(Text("No file selected", style="dim italic"))
            return

        from perch.services.git import get_diff

        try:
            rel_path = str(self._current_path.relative_to(self.worktree_root))
        except ValueError:
            self._show_content_view()
            self._content.update(Text("File not in worktree", style="dim italic"))
            return

        try:
            diff_text = get_diff(self.worktree_root, rel_path)
        except RuntimeError as e:
            self._show_content_view()
            self._content.update(f"Error getting diff: {e}")
            return

        if not diff_text:
            self._show_content_view()
            self._content.update(Text("No changes", style="dim italic"))
        elif self._diff_layout == "side-by-side":
            self._show_side_by_side_view(diff_text)
        else:
            self._show_content_view()
            styled = render_diff(diff_text, dark=self._is_dark_theme())
            self._content.update(styled)
        self.scroll_home(animate=False)

    def action_toggle_diff(self) -> None:
        """Toggle between normal file view and diff view."""
        if self._current_path is None:
            return
        self._diff_mode = not self._diff_mode
        if self._diff_mode:
            self._load_diff()
        else:
            self.load_file(self._current_path)

    def action_toggle_diff_layout(self) -> None:
        """Toggle between unified and side-by-side diff layout."""
        if not self._diff_mode:
            return
        self._diff_layout = (
            "side-by-side" if self._diff_layout == "unified" else "unified"
        )
        self._load_diff()

    def load_commit_diff(self, commit_hash: str) -> None:
        """Load and display the full diff for a commit with file jump support."""
        from perch.services.git import get_commit_diff

        if self.worktree_root is None:
            return

        self._current_path = None
        self._diff_mode = True
        self._show_content_view()

        try:
            diff_text = get_commit_diff(self.worktree_root, commit_hash)
        except RuntimeError as e:
            self._content.update(f"Error getting commit diff: {e}")
            return

        if not diff_text:
            self._content.update(Text("Empty commit", style="dim italic"))
            self._diff_file_offsets = []
            self._diff_file_index = 0
            return

        # Build file boundary offsets (line numbers where "diff --git" appears)
        self._diff_file_offsets = []
        for i, line in enumerate(diff_text.splitlines()):
            if line.startswith("diff --git "):
                self._diff_file_offsets.append(i)
        self._diff_file_index = 0

        # Build header with file count
        n_files = len(self._diff_file_offsets)
        header = Text(f"Commit {commit_hash}")
        header.stylize("bold cyan")
        header.append(f"  ({n_files} file{'s' if n_files != 1 else ''})")
        header.append("  [n] next file  [p] prev file", style="dim")
        header.append("\n\n")

        styled = render_diff(diff_text, dark=self._is_dark_theme())
        self._content.update(Group(header, styled))
        self.scroll_home(animate=False)

    def action_next_diff_file(self) -> None:
        """Jump to the next file boundary in a multi-file diff."""
        if not self._diff_file_offsets:
            return
        if self._diff_file_index < len(self._diff_file_offsets) - 1:
            self._diff_file_index += 1
        self._scroll_to_diff_file()

    def action_prev_diff_file(self) -> None:
        """Jump to the previous file boundary in a multi-file diff."""
        if not self._diff_file_offsets:
            return
        if self._diff_file_index > 0:
            self._diff_file_index -= 1
        self._scroll_to_diff_file()

    def _scroll_to_diff_file(self) -> None:
        """Scroll to the current file boundary offset."""
        if not self._diff_file_offsets:
            return
        line = self._diff_file_offsets[self._diff_file_index]
        # +2 to account for the header lines in load_commit_diff
        self.scroll_to(y=line + 2, animate=False)
