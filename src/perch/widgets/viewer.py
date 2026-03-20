"""Viewer widget — renders files, diffs, markdown, logs, and status messages."""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, VerticalScroll
from textual.widgets import Static

MAX_LINES = 10_000
BINARY_CHECK_SIZE = 8192
_IMAGE_MAX_WIDTH = 60  # columns for rendered terminal images


def render_image_halfblocks(path: Path, max_width: int = _IMAGE_MAX_WIDTH) -> Text | None:
    """Render an image as colored half-block (▀) characters.

    Returns a Rich Text object, or None if the image can't be loaded.
    Each terminal row encodes two pixel rows using the upper-half-block
    character with foreground (top pixel) and background (bottom pixel).
    """
    try:
        from PIL import Image as PILImage
    except ImportError:
        return None

    try:
        img = PILImage.open(path).convert("RGB")
    except Exception:
        return None

    # Scale to fit terminal width, maintaining aspect ratio
    w, h = img.size
    if w > max_width:
        scale = max_width / w
        img = img.resize((max_width, int(h * scale)))
    w, h = img.size

    # Ensure even height for half-block pairing
    if h % 2:
        img = img.resize((w, h + 1))
        h += 1

    pixels = img.load()
    assert pixels is not None
    result = Text()
    for y in range(0, h, 2):
        if y > 0:
            result.append("\n")
        for x in range(w):
            top = pixels[x, y]
            bot = pixels[x, y + 1]
            r1, g1, b1 = int(top[0]), int(top[1]), int(top[2])  # type: ignore[index]
            r2, g2, b2 = int(bot[0]), int(bot[1]), int(bot[2])  # type: ignore[index]
            result.append(
                "▀",
                style=f"rgb({r1},{g1},{b1}) on rgb({r2},{g2},{b2})",
            )
    return result


def render_markdown_with_images(
    text: str, base_dir: Path, max_width: int = _IMAGE_MAX_WIDTH
) -> list:
    """Parse markdown text and return a list of Rich renderables.

    Images (both ``![alt](src)`` and ``<img src="...">`` HTML tags) are
    resolved relative to *base_dir* and rendered as half-block art.
    Non-image sections are rendered as Rich Markdown.
    """
    from rich.markdown import Markdown

    # Match markdown images and HTML img tags
    img_pattern = re.compile(
        r'!\[([^\]]*)\]\(([^)]+)\)'           # ![alt](src)
        r'|<img\s[^>]*src=["\']([^"\']+)["\']'  # <img src="...">
    )

    parts: list = []
    last_end = 0
    for m in img_pattern.finditer(text):
        # Add preceding markdown
        before = text[last_end : m.start()].strip()
        if before:
            parts.append(Markdown(before))

        # Resolve image path
        src = m.group(2) or m.group(3)
        img_path = base_dir / src
        rendered = render_image_halfblocks(img_path, max_width)
        if rendered:
            parts.append(Text())  # spacer
            parts.append(rendered)
            parts.append(Text())  # spacer
        else:
            alt = m.group(1) or src
            parts.append(Text(f"  [image: {alt}]", style="dim italic"))

        last_end = m.end()

    # Add trailing markdown
    remainder = text[last_end:].strip()
    if remainder:
        parts.append(Markdown(remainder))

    return parts


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


def _extract_diff_filename(line: str) -> str:
    """Extract a readable filename from a 'diff --git a/... b/...' line."""
    # "diff --git a/path/to/file b/path/to/file" -> "path/to/file"
    parts = line.split(" b/", 1)
    if len(parts) == 2:
        return parts[1]
    return line


def render_diff(diff_text: str, dark: bool = True) -> Text:
    """Render unified diff text with background-colored lines.

    Added lines get a green background, removed lines get a red background,
    hunk headers get a blue background, and context lines are unstyled.
    File boundaries get a prominent separator with the filename.
    """
    if dark:
        add_style = "on #1a3a1a"
        del_style = "on #3a1a1a"
        hunk_style = "on #1a1a3a"
        meta_style = "bold"
        separator_style = "bold cyan"
        separator_rule_style = "dim cyan"
    else:
        add_style = "on #d4ffd4"
        del_style = "on #ffd4d4"
        hunk_style = "on #d4d4ff"
        meta_style = "bold"
        separator_style = "bold blue"
        separator_rule_style = "dim blue"

    result = Text()
    file_index = 0
    for i, line in enumerate(diff_text.splitlines()):
        if i > 0:
            result.append("\n")
        if line.startswith("diff --git "):
            filename = _extract_diff_filename(line)
            if file_index > 0:
                result.append("\n")
            result.append("─" * 60, style=separator_rule_style)
            result.append("\n")
            result.append(f"  {filename}", style=separator_style)
            result.append("\n")
            result.append("─" * 60, style=separator_rule_style)
            file_index += 1
        elif line.startswith("+++") or line.startswith("---"):
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
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("h", "scroll_left", "Scroll Left", show=False),
        Binding("l", "scroll_right", "Scroll Right", show=False),
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


class Viewer(VerticalScroll):
    """Renders files, diffs, markdown, logs, and status messages."""

    BINDINGS = [
        Binding("d", "toggle_diff", "Diff"),
        Binding("s", "toggle_diff_layout", "Layout"),
        Binding("m", "toggle_markdown_preview", "Markdown"),
        Binding("n", "next_diff_file", "Next File"),
        Binding("p", "prev_diff_file", "Prev File"),
        Binding("e", "app.open_editor", "Editor"),
        Binding("f", "app.toggle_focus_mode", "Focus"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("h", "scroll_left", "Left", show=False),
        Binding("l", "scroll_right", "Right", show=False),
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
        self._content = Static(
            Text("Select a file in the sidebar to view it here", style="dim italic"),
            id="file-content",
        )
        self._current_path: Path | None = None
        self.worktree_root: Path | None = worktree_root
        self._diff_mode: bool = False
        self._diff_layout: str = "unified"
        self._diff_file_offsets: list[int] = []
        self._diff_file_index: int = 0
        self._markdown_preview: bool = False
        self._current_commit: str | None = None

    # ------------------------------------------------------------------
    # Dynamic footer — check_action controls binding visibility
    # ------------------------------------------------------------------

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:
        if action == "toggle_diff":
            return self._current_path is not None
        if action == "toggle_diff_layout":
            return self._diff_mode
        if action == "toggle_markdown_preview":
            return (
                self._current_path is not None
                and self._is_markdown(self._current_path)
                and not self._diff_mode
            )
        if action in ("next_diff_file", "prev_diff_file"):
            return bool(self._diff_file_offsets)
        return True

    def _refresh_footer(self) -> None:
        """Trigger footer re-evaluation after state changes."""
        try:
            self.screen.refresh_bindings()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------

    def _get_syntax_theme(self) -> str:
        """Return a Pygments theme appropriate for the current app theme."""
        try:
            if self.app.current_theme.dark:
                return "monokai"
            return "default"
        except Exception:
            return "monokai"

    def _get_background_color(self) -> str | None:
        """Return the Textual theme's surface color for Syntax background.

        This ensures the syntax highlighting background matches the app theme
        instead of using the Pygments theme's default background.
        Returns None when no surface color is set, letting Syntax use its default.
        """
        try:
            return self.app.current_theme.surface or None
        except Exception:
            return None

    def _is_dark_theme(self) -> bool:
        """Return True if the current app theme is dark."""
        try:
            return self.app.current_theme.dark
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def compose(self):
        yield self._content
        yield SyncedDiffView(id="diff-container")

    def _show_content_view(self) -> None:
        """Show the main content area and hide the diff container."""
        self._current_commit = None
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

    # ------------------------------------------------------------------
    # Public API — content types
    # ------------------------------------------------------------------

    def _update_border_title(self, title: str = "") -> None:
        """Set the border title shown in the viewer's top border."""
        self.border_title = title

    def _path_label(self, path: Path) -> str:
        """Return a relative path string for display, or the full path as fallback."""
        if self.worktree_root:
            try:
                return str(path.relative_to(self.worktree_root))
            except ValueError:
                pass
        return str(path)

    @staticmethod
    def _is_markdown(path: Path) -> bool:
        return path.suffix.lower() in {".md", ".markdown", ".mdown", ".mkd"}

    def load_file(self, path: Path) -> None:
        """Load and display a file with syntax highlighting."""
        self._current_path = path
        self._diff_mode = False
        self._diff_layout = "unified"
        self._show_content_view()
        self._update_border_title(self._path_label(path))

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

        if self._markdown_preview and self._is_markdown(path):
            parts = render_markdown_with_images(text, path.parent)
            if len(parts) == 1:
                self._content.update(parts[0])
            else:
                self._content.update(Group(*parts))
            self.scroll_home(animate=False)
            self._refresh_footer()
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
        self._refresh_footer()

    def load_commit_diff(self, commit_hash: str) -> None:
        """Load and display the full diff for a commit with file jump support."""
        from perch.services.git import get_commit_diff

        if self.worktree_root is None:
            return

        # Skip reload if already showing this commit (prevents scroll reset
        # when the GitPanel auto-refresh re-selects the same commit).
        if self._current_commit == commit_hash:
            return

        self._current_path = None
        self._diff_mode = True
        self._show_content_view()
        self._current_commit = commit_hash
        self._update_border_title(f"commit {commit_hash[:8]}")

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

        # Build file boundary offsets in the *rendered* output.
        # render_diff replaces each "diff --git" line with 3 lines (rule,
        # filename, rule) and adds a blank line between files, so we walk
        # the source lines and track the rendered line count.
        self._diff_file_offsets = []
        rendered_line = 0
        file_index = 0
        for line in diff_text.splitlines():
            if line.startswith("diff --git "):
                if file_index > 0:
                    rendered_line += 1  # blank line between files
                self._diff_file_offsets.append(rendered_line)
                rendered_line += 3  # rule + filename + rule
                file_index += 1
            else:
                rendered_line += 1
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
        self._refresh_footer()

    def show_deleted_file_diff(
        self, file_path: Path, rel_path: str, staged: bool = False
    ) -> None:
        """Show a diff for a file that was deleted from the worktree."""
        self._current_path = file_path
        self._diff_mode = True
        self._diff_layout = "unified"
        self._show_content_view()
        self._update_border_title(f"{rel_path} (deleted)")

        from perch.services.git import get_diff

        diff_text = ""
        if self.worktree_root is not None:
            try:
                diff_text = get_diff(self.worktree_root, rel_path, staged=staged)
            except RuntimeError:
                pass

        if diff_text:
            styled = render_diff(diff_text, dark=self._is_dark_theme())
            header = Text("File deleted — showing diff\n", style="bold red")
            self._content.update(Group(header, styled))
        else:
            self._content.update(
                Text("File deleted — no diff available", style="bold red")
            )
        self._refresh_footer()

    def show_pr_body(self, body: str, title: str = "") -> None:
        """Render a PR description as markdown in the viewer."""
        from rich.markdown import Markdown

        self._current_path = None
        self._diff_mode = False
        self._show_content_view()
        self._update_border_title(title or "PR Description")

        if not body.strip():
            self._content.update(Text("No PR description", style="dim italic"))
            return

        self._content.update(Markdown(body))
        self.scroll_home(animate=False)
        self._refresh_footer()

    def show_review(self, body: str, title: str = "") -> None:
        """Render a review submission body as markdown in the viewer."""
        from rich.markdown import Markdown

        self._current_path = None
        self._diff_mode = False
        self._show_content_view()
        self._update_border_title(title or "Review")

        if not body.strip():
            self._content.update(Text("No review body", style="dim italic"))
            return

        self._content.update(Markdown(body))
        self.scroll_home(animate=False)
        self._refresh_footer()

    def show_ci_loading(self, title: str = "") -> None:
        """Show a loading indicator while CI logs are being fetched."""
        self._current_path = None
        self._diff_mode = False
        self._show_content_view()
        self._update_border_title(title or "CI Log")
        self._content.update(Text("Loading logs...", style="bold yellow"))
        self._refresh_footer()

    @work(thread=True, exclusive=True, group="ci_log")
    def fetch_ci_log(self, url: str) -> None:
        """Fetch a CI job log in the background and display it."""
        from perch.services.github import get_job_log

        if self.worktree_root is None:
            return
        log_text = get_job_log(url, self.worktree_root)
        self.app.call_from_thread(self.show_ci_log, log_text)

    def show_ci_log(self, log_text: str) -> None:
        """Parse and display a GitHub Actions log."""
        self._current_path = None
        self._diff_mode = False
        self._show_content_view()

        if not log_text.strip():
            self._content.update(Text("No log output available", style="dim italic"))
            return

        result = Text()
        ansi_re = re.compile(r"\x1b\[[0-9;]*m")
        for line in log_text.splitlines():
            # Strip job/step/timestamp prefix: "job\tstep\t{timestamp} msg"
            parts = line.split("\t", 2)
            msg = parts[-1] if parts else line
            # Strip ISO timestamp prefix (e.g. "2026-03-17T01:26:13.1234567Z ")
            ts_match = re.match(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?", msg)
            if ts_match:
                msg = msg[ts_match.end() :]
            # Strip ANSI escape codes
            msg = ansi_re.sub("", msg)
            # Parse GitHub Actions annotations
            if msg.startswith("##[group]"):
                group_name = msg[9:]
                if result.plain:
                    result.append("\n")
                result.append(f"  {group_name}\n", style="bold cyan")
                continue
            if msg.startswith("##[endgroup]"):
                continue
            if msg.startswith("##[error]"):
                result.append(f"  {msg[9:]}\n", style="bold red")
                continue
            if msg.startswith("##[warning]"):
                result.append(f"  {msg[11:]}\n", style="yellow")
                continue
            # Regular log line
            result.append(f"    {msg}\n")

        self._content.update(result)
        self.scroll_home(animate=False)
        self._refresh_footer()

    def show_clean_tree(self) -> None:
        """Show a message indicating the working tree has no changes."""
        self._current_path = None
        self._show_content_view()
        self._update_border_title()
        self._content.update(
            Text("Working tree is clean — no changes to review", style="dim italic")
        )
        self._refresh_footer()

    def show_folder(self, path: Path) -> None:
        """Show a message when a folder is selected."""
        self._current_path = None
        self._show_content_view()
        self._update_border_title(self._path_label(path))
        self._content.update(
            Text("Folder selected — no preview available", style="dim italic")
        )
        self._refresh_footer()

    def show_empty_directory(self) -> None:
        """Show a message when the directory contains no files."""
        self._current_path = None
        self._show_content_view()
        self._update_border_title()
        self._content.update(
            Text("No files in this directory", style="dim italic")
        )
        self._refresh_footer()

    def show_placeholder(self) -> None:
        """Show the default empty-state message."""
        self._current_path = None
        self._show_content_view()
        self._update_border_title()
        self._content.update(
            Text("Select a file in the sidebar to view it here", style="dim italic")
        )
        self._refresh_footer()

    def refresh_content(self) -> None:
        """Re-render the current content (e.g. after a theme change)."""
        if self._current_path is not None:
            if self._diff_mode:
                self._load_diff()
            else:
                self.load_file(self._current_path)

    # ------------------------------------------------------------------
    # Diff actions
    # ------------------------------------------------------------------

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
        self._refresh_footer()

    def action_toggle_markdown_preview(self) -> None:
        """Toggle between raw and rendered markdown for .md files."""
        if self._current_path is None or not self._is_markdown(self._current_path):
            return
        if self._diff_mode:
            return
        self._markdown_preview = not self._markdown_preview
        self.load_file(self._current_path)

    def action_toggle_diff_layout(self) -> None:
        """Toggle between unified and side-by-side diff layout."""
        if not self._diff_mode:
            return
        self._diff_layout = (
            "side-by-side" if self._diff_layout == "unified" else "unified"
        )
        self._load_diff()

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
