"""PR context panel showing reviews, comments, and CI checks."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.widgets import Label, ListItem, ListView

from perch.models import CICheck, PRContext


_BUCKET_STYLES: dict[str, str] = {
    "pass": "green",
    "fail": "red",
    "pending": "yellow",
    "skipping": "dim",
}

_REVIEW_STYLES: dict[str, str] = {
    "APPROVED": "green",
    "CHANGES_REQUESTED": "red",
    "COMMENTED": "yellow",
    "DISMISSED": "dim",
    "PENDING": "yellow",
}


def _make_section_header(title: str) -> ListItem:
    """Create a non-selectable section header."""
    text = Text(f"\n{title}", style="bold")
    item = ListItem(Label(text), classes="section-header")
    item.disabled = True
    return item


class PRContextPanel(ListView):
    """Displays PR context: header, reviews, comments, and CI checks."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("enter", "open_item", "Open in GitHub"),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    def __init__(
        self,
        worktree_root: Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._worktree_root = worktree_root
        self._pr_context: PRContext | None = None
        self._checks: list[CICheck] = []
        self._item_urls: dict[int, str] = {}

    def on_mount(self) -> None:
        self.append(_make_section_header("Loading PR context..."))
        self._do_refresh()
        self.set_interval(30, self._do_refresh)

    @work(thread=True)
    def _do_refresh(self) -> None:
        from perch.services.github import get_checks, get_pr_context

        try:
            pr = get_pr_context(self._worktree_root)
            checks = get_checks(self._worktree_root)
        except FileNotFoundError:
            self.app.call_from_thread(self._show_gh_missing)
            return

        self._pr_context = pr
        self._checks = checks
        self.app.call_from_thread(self._update_display)

    def _show_gh_missing(self) -> None:
        self.clear()
        self._item_urls = {}
        text = Text(
            "gh CLI not found. Install it from https://cli.github.com/",
            style="bold red",
        )
        self.append(ListItem(Label(text)))

    def _update_display(self) -> None:
        pr = self._pr_context
        self.clear()
        self._item_urls = {}

        if pr is None:
            text = Text("No PR open for this branch", style="dim italic")
            self.append(ListItem(Label(text)))
            return

        # PR header
        decision = pr.review_decision or "NONE"
        style = _REVIEW_STYLES.get(decision, "")
        title_text = Text()
        title_text.append(f"#{pr.number} ", style="bold cyan")
        title_text.append(pr.title, style="bold")
        title_text.append("  ")
        title_text.append(f"[{decision}]", style=f"bold {style}")
        idx = self._append_item(title_text, url=pr.url)

        # Reviews
        self.append(_make_section_header("Reviews"))
        if pr.reviews:
            for r in pr.reviews:
                text = Text()
                r_style = _REVIEW_STYLES.get(r.state, "")
                text.append(f"{r.author}", style="bold")
                text.append(f" [{r.state}]", style=r_style)
                if r.submitted_at:
                    text.append(f"  {r.submitted_at}", style="dim")
                if r.body:
                    text.append(f"\n  {r.body}")
                self._append_item(text, url=pr.url)
        else:
            item = ListItem(Label(Text("  No reviews yet", style="dim")))
            item.disabled = True
            self.append(item)

        # Comments
        self.append(_make_section_header("Comments"))
        if pr.comments:
            for c in pr.comments:
                text = Text()
                text.append(f"{c.author}", style="bold")
                if c.created_at:
                    text.append(f"  {c.created_at}", style="dim")
                if c.body:
                    text.append(f"\n  {c.body}")
                self._append_item(text, url=pr.url)
        else:
            item = ListItem(Label(Text("  No comments", style="dim")))
            item.disabled = True
            self.append(item)

        # CI Checks
        self.append(_make_section_header("CI Checks"))
        if self._checks:
            for check in self._checks:
                bucket_style = _BUCKET_STYLES.get(check.bucket, "")
                text = Text()
                text.append(
                    f"  {check.bucket or check.state:<10}", style=bucket_style
                )
                text.append(f" {check.name}")
                if check.workflow:
                    text.append(f"  ({check.workflow})", style="dim")
                self._append_item(text, url=check.link)
        else:
            item = ListItem(Label(Text("  No checks", style="dim")))
            item.disabled = True
            self.append(item)

    def _append_item(self, text: Text, url: str = "") -> int:
        """Append a selectable item and record its URL. Returns item index."""
        item = ListItem(Label(text))
        self.append(item)
        idx = len(self) - 1
        if url:
            self._item_urls[idx] = url
        return idx

    def _page_size(self) -> int:
        return max(1, self.scrollable_content_region.height)

    def action_page_up(self) -> None:
        if self.index is not None:
            self.index = max(0, self.index - self._page_size())

    def action_page_down(self) -> None:
        if self.index is not None:
            self.index = min(len(self) - 1, self.index + self._page_size())

    def action_refresh(self) -> None:
        self._do_refresh()

    def action_open_item(self) -> None:
        """Open the selected item's URL in the browser."""
        if self.index is not None and self.index in self._item_urls:
            webbrowser.open(self._item_urls[self.index])
