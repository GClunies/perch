"""File viewer widget with syntax highlighting and line numbers."""

from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import VerticalScroll
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


class FileViewer(VerticalScroll):
    """Displays file content with syntax highlighting and line numbers."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._content = Static("No file selected", id="file-content")
        self._current_path: Path | None = None

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

    def load_file(self, path: Path) -> None:
        """Load and display a file with syntax highlighting."""
        self._current_path = path

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
