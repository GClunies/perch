"""File viewer widget with syntax highlighting and line numbers."""

from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
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


def parse_diff_sides(diff_text: str) -> tuple[str, str]:
    """Parse unified diff text into left (old) and right (new) panel text.

    Returns two strings suitable for rendering with the 'diff' lexer.
    Lines are padded with blanks to maintain vertical alignment.
    """
    left_lines: list[str] = []
    right_lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("--- "):
            left_lines.append(line)
            right_lines.append("")
        elif line.startswith("+++ "):
            left_lines.append("")
            right_lines.append(line)
        elif line.startswith("-"):
            left_lines.append(line)
            right_lines.append("")
        elif line.startswith("+"):
            left_lines.append("")
            right_lines.append(line)
        else:
            left_lines.append(line)
            right_lines.append(line)
    return "\n".join(left_lines), "\n".join(right_lines)


class FileViewer(VerticalScroll):
    """Displays file content with syntax highlighting and line numbers."""

    BINDINGS = [
        Binding("d", "toggle_diff", "Toggle Diff", show=False),
        Binding("s", "toggle_diff_layout", "Toggle Diff Layout", show=False),
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

    def _get_syntax_theme(self) -> str:
        """Return a Pygments theme appropriate for the current app theme."""
        try:
            if self.app.current_theme.dark:
                return "monokai"
            return "default"
        except Exception:
            return "monokai"

    def compose(self):
        yield self._content
        with Horizontal(id="diff-container"):
            with VerticalScroll(id="diff-left"):
                yield Static("", id="diff-left-content")
            with VerticalScroll(id="diff-right"):
                yield Static("", id="diff-right-content")

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
        self.query_one("#diff-container").display = True

        left_text, right_text = parse_diff_sides(diff_text)
        theme = self._get_syntax_theme()

        left_syntax = Syntax(
            left_text, "diff", line_numbers=True, word_wrap=False, theme=theme
        )
        right_syntax = Syntax(
            right_text, "diff", line_numbers=True, word_wrap=False, theme=theme
        )

        self.query_one("#diff-left-content", Static).update(left_syntax)
        self.query_one("#diff-right-content", Static).update(right_syntax)

        for panel_id in ("#diff-left", "#diff-right"):
            try:
                self.query_one(panel_id, VerticalScroll).scroll_home(animate=False)
            except Exception:
                pass

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
            syntax = Syntax(
                diff_text,
                "diff",
                line_numbers=True,
                word_wrap=False,
                theme=self._get_syntax_theme(),
            )
            self._content.update(syntax)
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
