"""GitHub panel showing PR details, reviews, comments, and Actions."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Label, ListItem, ListView

from perch.models import CICheck, PRContext


_BUCKET_ICONS: dict[str, tuple[str, str]] = {
    "pass": ("\uf00c", "green"),  # nf-fa-check
    "fail": ("\uf00d", "red"),  # nf-fa-close
    "pending": ("\uf017", "yellow"),  # nf-fa-clock_o
    "skipping": ("\uf068", "dim"),  # nf-fa-minus
}

_REVIEW_ICONS: dict[str, tuple[str, str, str]] = {
    "APPROVED": ("\uf00c", "green", "approved"),
    "CHANGES_REQUESTED": ("\uf00d", "red", "requested changes"),
    "COMMENTED": ("\uf0e5", "yellow", "commented"),  # nf-fa-comment_o
    "DISMISSED": ("\uf068", "dim", "dismissed"),
    "PENDING": ("\uf017", "yellow", "pending"),
}


class ClickableItem(ListItem):
    """A ListItem that can open a URL in the browser."""

    DEFAULT_CSS = """
    ClickableItem {
        height: auto;
        width: auto;
    }
    """

    def __init__(
        self,
        *children,
        url: str = "",
        preview_kind: str = "",
        preview_title: str = "",
        preview_body: str = "",
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.url = url
        self.preview_kind = preview_kind
        self.preview_title = preview_title
        self.preview_body = preview_body


def _make_section_header(title: str) -> ListItem:
    """Create a non-selectable section header."""
    text = Text(f"\n{title}", style="bold")
    item = ListItem(Label(text), classes="section-header")
    item.disabled = True
    return item


class GitHubPanel(ListView):
    """Displays PR context: header, reviews, comments, and GitHub Actions."""

    class PreviewRequested(Message):
        """Posted when the user highlights an item that has preview content."""

        def __init__(
            self, preview_kind: str, url: str, body: str = "", title: str = ""
        ) -> None:
            super().__init__()
            self.preview_kind = preview_kind
            self.url = url
            self.body = body
            self.title = title

    BINDINGS = [
        ("o", "open_in_browser", "Open"),
        ("r", "refresh", "Refresh"),
        Binding("pageup", "page_up", "", show=False),
        Binding("pagedown", "page_down", "", show=False),
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
        self._actions: list[CICheck] = []
        self._actions_loaded = True

    def _on_list_item__child_clicked(self, event: ListItem._ChildClicked) -> None:
        """Guard against stale item references after an auto-refresh."""
        try:
            super()._on_list_item__child_clicked(event)
        except ValueError:
            pass  # Item was replaced by a concurrent refresh

    def on_mount(self) -> None:
        self.append(_make_section_header("Loading PR context..."))
        self._do_refresh()
        self.set_interval(30, self._do_refresh)

    @work(thread=True)
    def _do_refresh(self) -> None:
        from perch.services.github import get_checks, get_pr_context

        # Phase 1: fetch PR context and render immediately
        try:
            pr = get_pr_context(self._worktree_root)
        except FileNotFoundError:
            self.app.call_from_thread(self._show_gh_missing)
            return

        self._pr_context = pr
        self._actions = []
        self._actions_loaded = False
        self.app.call_from_thread(self._update_display)

        # Phase 2: fetch actions and update the display
        try:
            actions = get_checks(self._worktree_root)
        except FileNotFoundError:
            actions = []

        self._actions = actions
        self._actions_loaded = True
        self.app.call_from_thread(self._update_display)

    def _show_gh_missing(self) -> None:
        self.clear()
        text = Text(
            "gh CLI not found. Install it from https://cli.github.com/",
            style="bold red",
        )
        self.append(ListItem(Label(text)))

    def _update_display(self) -> None:
        pr = self._pr_context
        self.clear()

        if pr is None:
            text = Text("No PR open for this branch", style="dim italic")
            self.append(ListItem(Label(text)))
            return

        # PR header
        decision = pr.review_decision or "NONE"
        icon, color, _label = _REVIEW_ICONS.get(decision, ("", "", ""))
        title_text = Text()
        title_text.append(f"#{pr.number} ", style="bold cyan")
        title_text.append(pr.title, style="bold")
        if icon:
            title_text.append(f"  {icon}", style=color)
        self._append_item(
            title_text,
            url=pr.url,
            preview_kind="pr_body",
            preview_title=f"#{pr.number}",
        )

        # Reviews
        self.append(_make_section_header("Reviews"))
        if pr.reviews:
            for r in pr.reviews:
                text = Text()
                r_icon, r_color, r_label = _REVIEW_ICONS.get(
                    r.state, ("", "", r.state.lower())
                )
                if r_icon:
                    text.append(f"  {r_icon} ", style=r_color)
                text.append(f"{r.author}", style="bold")
                text.append(f" {r_label}", style=r_color or "dim")
                if r.submitted_at:
                    text.append(f"  {r.submitted_at}", style="dim")
                self._append_item(
                    text,
                    url=r.url,
                    preview_kind="review",
                    preview_title=f"{r.author} — {r_label}",
                    preview_body=r.body or "",
                )
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
                self._append_item(text, url=c.url)
        else:
            item = ListItem(Label(Text("  No comments", style="dim")))
            item.disabled = True
            self.append(item)

        # Actions
        self.append(_make_section_header("Actions"))
        if not self._actions_loaded:
            item = ListItem(Label(Text("  Loading actions...", style="dim italic")))
            item.disabled = True
            self.append(item)
        elif self._actions:
            for check in self._actions:
                icon, color = _BUCKET_ICONS.get(
                    check.bucket,
                    ("\uf128", "dim"),  # nf-fa-question
                )
                text = Text()
                text.append(f"  {icon} ", style=color)
                text.append(check.name)
                self._append_item(
                    text,
                    url=check.link,
                    preview_kind="ci_check",
                    preview_title=check.name,
                )
        else:
            item = ListItem(Label(Text("  No actions", style="dim")))
            item.disabled = True
            self.append(item)

        # Select the first enabled item so Enter/click works immediately
        for i, node in enumerate(self._nodes):
            if isinstance(node, ListItem) and not node.disabled:
                self.index = i
                break

    def _append_item(
        self,
        text: Text,
        url: str = "",
        preview_kind: str = "",
        preview_title: str = "",
        preview_body: str = "",
    ) -> None:
        """Append a clickable item that opens a URL when clicked."""
        self.append(
            ClickableItem(
                Label(text),
                url=url,
                preview_kind=preview_kind,
                preview_title=preview_title,
                preview_body=preview_body,
            )
        )

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

    def action_open_in_browser(self) -> None:
        """Open the highlighted item's URL in the browser."""
        item = self.highlighted_child
        if isinstance(item, ClickableItem) and item.url:
            webbrowser.open(item.url)

    def activate_current_preview(self) -> None:
        """Post PreviewRequested for the currently highlighted item.

        Called by the app when switching back to the GitHub tab to restore
        the viewer to whatever was last shown.
        """
        item = self.highlighted_child
        if not isinstance(item, ClickableItem) or not item.preview_kind:
            return
        body = item.preview_body
        if item.preview_kind == "pr_body" and self._pr_context:
            body = self._pr_context.body
        self.post_message(
            self.PreviewRequested(
                preview_kind=item.preview_kind,
                url=item.url,
                body=body,
                title=item.preview_title,
            )
        )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Post a preview message when the user highlights an item."""
        if event.item is None or not isinstance(event.item, ClickableItem):
            return
        if not event.item.preview_kind:
            return

        body = event.item.preview_body
        if event.item.preview_kind == "pr_body" and self._pr_context:
            body = self._pr_context.body

        self.post_message(
            self.PreviewRequested(
                preview_kind=event.item.preview_kind,
                url=event.item.url,
                body=body,
                title=event.item.preview_title,
            )
        )
