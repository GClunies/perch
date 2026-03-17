"""PR context panel showing reviews, comments, and CI checks."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, DataTable, Label, Static
from textual import work

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


class PRContextPanel(VerticalScroll):
    """Displays PR context: header, reviews, comments, and CI checks."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("enter", "open_check", "Open Check"),
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

    def compose(self):
        yield Static("Loading PR context...", id="pr-header")
        yield Collapsible(Label(""), title="Reviews", id="pr-reviews")
        yield Collapsible(Label(""), title="Comments", id="pr-comments")
        yield Collapsible(
            DataTable(id="checks-table"),
            title="CI Checks",
            id="pr-checks",
        )

    def on_mount(self) -> None:
        table = self.query_one("#checks-table", DataTable)
        table.add_columns("Status", "Name", "Workflow")
        table.cursor_type = "row"
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
        header = self.query_one("#pr-header", Static)
        header.update(
            Text(
                "gh CLI not found. Install it from https://cli.github.com/",
                style="bold red",
            )
        )
        for cid in ("pr-reviews", "pr-comments", "pr-checks"):
            self.query_one(f"#{cid}", Collapsible).display = False

    def _update_display(self) -> None:
        header = self.query_one("#pr-header", Static)
        pr = self._pr_context

        if pr is None:
            header.update(Text("No PR open for this branch", style="dim italic"))
            for cid in ("pr-reviews", "pr-comments", "pr-checks"):
                self.query_one(f"#{cid}", Collapsible).display = False
            return

        # PR header
        decision = pr.review_decision or "NONE"
        style = _REVIEW_STYLES.get(decision, "")
        title_text = Text()
        title_text.append(f"#{pr.number} ", style="bold cyan")
        title_text.append(pr.title, style="bold")
        title_text.append("  ")
        title_text.append(f"[{decision}]", style=f"bold {style}")

        header.update(title_text)

        # Reviews
        reviews_section = self.query_one("#pr-reviews", Collapsible)
        reviews_section.display = True
        if pr.reviews:
            lines = Text()
            for i, r in enumerate(pr.reviews):
                if i > 0:
                    lines.append("\n\n")
                r_style = _REVIEW_STYLES.get(r.state, "")
                lines.append(f"{r.author}", style="bold")
                lines.append(f" [{r.state}]", style=r_style)
                if r.submitted_at:
                    lines.append(f"  {r.submitted_at}", style="dim")
                if r.body:
                    lines.append(f"\n{r.body}")
            reviews_section.query_one(Label).update(lines)
        else:
            reviews_section.query_one(Label).update(Text("No reviews yet", style="dim"))

        # Comments
        comments_section = self.query_one("#pr-comments", Collapsible)
        comments_section.display = True
        if pr.comments:
            lines = Text()
            for i, c in enumerate(pr.comments):
                if i > 0:
                    lines.append("\n\n")
                lines.append(f"{c.author}", style="bold")
                if c.created_at:
                    lines.append(f"  {c.created_at}", style="dim")
                if c.body:
                    lines.append(f"\n{c.body}")
            comments_section.query_one(Label).update(lines)
        else:
            comments_section.query_one(Label).update(Text("No comments", style="dim"))

        # CI Checks
        checks_section = self.query_one("#pr-checks", Collapsible)
        checks_section.display = True
        table = self.query_one("#checks-table", DataTable)
        table.clear()
        for check in self._checks:
            style = _BUCKET_STYLES.get(check.bucket, "")
            status = Text(check.bucket or check.state, style=style)
            table.add_row(status, check.name, check.workflow)

    def action_refresh(self) -> None:
        self._do_refresh()

    def action_open_check(self) -> None:
        table = self.query_one("#checks-table", DataTable)
        if not table.has_focus or table.row_count == 0:
            return
        row_idx = table.cursor_row
        if 0 <= row_idx < len(self._checks):
            link = self._checks[row_idx].link
            if link:
                webbrowser.open(link)
