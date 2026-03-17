"""Tests for PRContextPanel widget."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from textual.widgets import ListItem

from perch.app import PerchApp
from perch.models import CICheck, PRComment, PRContext, PRReview
from perch.widgets.pr_context import PRContextPanel


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    (tmp_path / "hello.py").write_text("print('hello')\n")
    return tmp_path


def _make_pr_context(
    *,
    title: str = "Fix bug",
    number: int = 42,
    url: str = "https://github.com/org/repo/pull/42",
    review_decision: str = "APPROVED",
    body: str = "## Summary\nTest PR description",
    reviews: list[PRReview] | None = None,
    comments: list[PRComment] | None = None,
) -> PRContext:
    return PRContext(
        title=title,
        number=number,
        url=url,
        review_decision=review_decision,
        body=body,
        reviews=reviews or [],
        comments=comments or [],
    )


def _make_checks() -> list[CICheck]:
    return [
        CICheck(
            name="build",
            state="SUCCESS",
            bucket="pass",
            link="https://github.com/org/repo/actions/runs/123",
            workflow="CI",
        ),
        CICheck(
            name="lint",
            state="FAILURE",
            bucket="fail",
            link="https://github.com/org/repo/actions/runs/456",
            workflow="Lint",
        ),
    ]


def _patches(pr=None, checks=None):
    if checks is None:
        checks = []
    return (
        patch("perch.services.github.get_pr_context", return_value=pr),
        patch("perch.services.github.get_checks", return_value=checks),
    )


def _get_all_text(panel: PRContextPanel) -> str:
    """Get all visible text from the panel's list items."""
    from textual.widgets import Label

    parts = []
    for label in panel.query(Label):
        rendered = label.render()
        parts.append(str(rendered))
    return "\n".join(parts)


class TestShowGhMissing:
    async def test_shows_gh_missing_message(self, worktree: Path) -> None:
        p1, p2 = _patches()
        p1 = patch(
            "perch.services.github.get_pr_context",
            side_effect=FileNotFoundError("gh not found"),
        )
        p2 = patch(
            "perch.services.github.get_checks",
            side_effect=FileNotFoundError("gh not found"),
        )
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "gh CLI not found" in text


class TestNoPR:
    async def test_no_pr_shows_message(self, worktree: Path) -> None:
        p1, p2 = _patches(pr=None)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "No PR open" in text


class TestUpdateDisplayWithPR:
    async def test_header_shows_number_and_title(self, worktree: Path) -> None:
        pr = _make_pr_context(title="Fix the thing", number=99)
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "#99" in text
                assert "Fix the thing" in text
                assert "APPROVED" in text

    async def test_reviews_shown(self, worktree: Path) -> None:
        pr = _make_pr_context(
            reviews=[
                PRReview(
                    author="alice",
                    state="APPROVED",
                    body="LGTM",
                    submitted_at="2025-01-15",
                ),
            ]
        )
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "alice" in text
                assert "APPROVED" in text

    async def test_no_reviews_placeholder(self, worktree: Path) -> None:
        pr = _make_pr_context(reviews=[])
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "No reviews yet" in text

    async def test_comments_shown(self, worktree: Path) -> None:
        pr = _make_pr_context(
            comments=[
                PRComment(author="carol", body="Nice!", created_at="2025-01-15"),
            ]
        )
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "carol" in text
                assert "Nice!" in text

    async def test_no_comments_placeholder(self, worktree: Path) -> None:
        pr = _make_pr_context(comments=[])
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "No comments" in text

    async def test_checks_shown(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "build" in text
                assert "lint" in text

    async def test_no_checks_placeholder(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                text = _get_all_text(panel)
                assert "No actions" in text


class TestArrowAndEnter:
    """Arrow keys navigate between items; Enter opens the highlighted URL."""

    @staticmethod
    async def _activate_pr_tab(pilot) -> PRContextPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-pr"
        await pilot.pause()
        panel = pilot.app.query_one(PRContextPanel)
        panel.focus()
        await pilot.pause()
        return panel

    @staticmethod
    def _navigate_to(panel: PRContextPanel, text_match: str) -> None:
        """Set the highlight to the item matching the given text."""
        item = _find_item_with_text(panel, text_match)
        assert item is not None, f"Item with {text_match!r} not found"
        panel.index = list(panel.children).index(item)

    async def test_enter_on_pr_header(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                self._navigate_to(panel, "#42")
                await pilot.press("enter")
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/pull/42"
                )

    async def test_enter_on_ci_check(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                self._navigate_to(panel, "build")
                await pilot.press("enter")
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/123"
                )

    async def test_arrow_down_then_enter(self, worktree: Path) -> None:
        """Navigate with real arrow keys, then press Enter to open."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                # Start at the PR title
                self._navigate_to(panel, "#42")
                # Arrow down until we reach a CI check
                from perch.widgets.pr_context import ClickableItem

                for _ in range(20):
                    await pilot.press("down")
                    await pilot.pause()
                    hc = panel.highlighted_child
                    if isinstance(hc, ClickableItem) and "actions" in hc.url:
                        break
                await pilot.press("enter")
                await pilot.pause()
                mock_open.assert_called_once()
                # Should be one of the check URLs
                url = mock_open.call_args[0][0]
                assert "actions/runs" in url

    async def test_enter_on_header_does_nothing(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                # Set index to a disabled header
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.disabled:
                        panel.index = i
                        break
                panel.focus()
                await pilot.press("enter")
                await pilot.pause()
                mock_open.assert_not_called()


def _find_item_with_text(panel: PRContextPanel, text_match: str) -> ListItem | None:
    """Find a non-disabled ListItem containing the given text."""
    from textual.widgets import Label as _Label

    for child in panel.children:
        if isinstance(child, ListItem) and not child.disabled:
            for label in child.query(_Label):
                if text_match in str(label.render()):
                    return child
    return None


class TestMouseClick:
    """Mouse-clicking any item with a URL should open that URL in the browser."""

    @staticmethod
    async def _activate_pr_tab(pilot) -> PRContextPanel:
        """Switch to the PR tab and return the panel (items need layout to be clickable)."""
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-pr"
        await pilot.pause()
        return pilot.app.query_one(PRContextPanel)

    async def test_click_pr_title(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                item = _find_item_with_text(panel, "#42")
                assert item is not None, "PR title item not found"
                await pilot.click(item)
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/pull/42"
                )

    async def test_click_ci_check(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                item = _find_item_with_text(panel, "build")
                assert item is not None, "CI check item not found"
                await pilot.click(item)
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/123"
                )

    async def test_click_second_ci_check(self, worktree: Path) -> None:
        """Each CI check opens its own URL, not the first one's."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                item = _find_item_with_text(panel, "lint")
                assert item is not None, "lint check item not found"
                await pilot.click(item)
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/456"
                )

    async def test_click_review(self, worktree: Path) -> None:
        pr = _make_pr_context(
            reviews=[
                PRReview(
                    author="alice",
                    state="APPROVED",
                    body="LGTM",
                    submitted_at="2025-01-15",
                    url="https://github.com/org/repo/pull/42#review-1",
                ),
            ]
        )
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                item = _find_item_with_text(panel, "alice")
                assert item is not None, "review item not found"
                await pilot.click(item)
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/pull/42#review-1"
                )

    async def test_click_comment(self, worktree: Path) -> None:
        pr = _make_pr_context(
            comments=[
                PRComment(
                    author="bob",
                    body="Needs more tests",
                    created_at="2025-01-15",
                    url="https://github.com/org/repo/pull/42#comment-1",
                ),
            ]
        )
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                item = _find_item_with_text(panel, "bob")
                assert item is not None, "comment item not found"
                await pilot.click(item)
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/pull/42#comment-1"
                )

    async def test_items_clickable_after_refresh(self, worktree: Path) -> None:
        """Items remain clickable after the panel refreshes its data."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                # Simulate the 30s refresh timer firing
                panel._update_display()
                await pilot.pause()
                item = _find_item_with_text(panel, "build")
                assert item is not None, "CI check not found after refresh"
                await pilot.click(item)
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/123"
                )

    async def test_section_header_click_does_not_open(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.pr_context.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                header = None
                for child in panel.children:
                    if isinstance(child, ListItem) and child.disabled:
                        header = child
                        break
                if header is not None:
                    await pilot.click(header)
                    await pilot.pause()
                mock_open.assert_not_called()


class TestHighlightPreview:
    """Navigating to an item in the PR tab should preview its content in the FileViewer."""

    @staticmethod
    async def _activate_pr_tab(pilot) -> PRContextPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-pr"
        await pilot.pause()
        panel = pilot.app.query_one(PRContextPanel)
        panel.focus()
        await pilot.pause()
        return panel

    @staticmethod
    def _viewer_text(pilot) -> str:
        """Render the FileViewer content to plain text."""
        from io import StringIO

        from rich.console import Console

        from perch.widgets.file_viewer import FileViewer

        viewer = pilot.app.query_one(FileViewer)
        # Static stores its renderable in name-mangled _Static__content
        renderable = viewer._content._Static__content
        if renderable is None:
            return ""
        console = Console(file=StringIO(), width=120)
        console.print(renderable)
        return console.file.getvalue()

    async def test_highlight_pr_title_shows_body(self, worktree: Path) -> None:
        """Navigating to the PR title shows the PR description in the viewer."""
        pr = _make_pr_context(body="## My PR\nSome description here")
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                _find_item = _find_item_with_text(panel, "#42")
                assert _find_item is not None
                panel.index = list(panel.children).index(_find_item)
                await pilot.pause()
                await pilot.pause()
                content = self._viewer_text(pilot)
                assert "PR Description" in content or "My PR" in content

    async def test_highlight_ci_check_shows_loading(self, worktree: Path) -> None:
        """Navigating to a CI check shows a loading indicator."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.services.github.get_job_log", return_value="log output"):
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                check_item = _find_item_with_text(panel, "build")
                assert check_item is not None
                panel.index = list(panel.children).index(check_item)
                await pilot.pause()
                await pilot.pause()
                content = self._viewer_text(pilot)
                # Should show loading or the actual log (depending on timing)
                assert "Loading" in content or "log output" in content or "CI" in content

    async def test_highlight_ci_check_shows_log(self, worktree: Path) -> None:
        """After fetching, the CI check log is displayed in the viewer."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch(
            "perch.services.github.get_job_log", return_value="step 1\nstep 2\nDone"
        ):
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                check_item = _find_item_with_text(panel, "build")
                assert check_item is not None
                panel.index = list(panel.children).index(check_item)
                # Give the background worker time to complete
                for _ in range(10):
                    await pilot.pause()
                content = self._viewer_text(pilot)
                assert "step 1" in content

    async def test_section_header_does_not_preview(self, worktree: Path) -> None:
        """Highlighting a section header does not change the viewer."""
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                await self._activate_pr_tab(pilot)
                # Viewer should still show default content
                content = self._viewer_text(pilot)
                initial = content
                # The section header should not update the viewer
                # (it has no preview_kind)
                panel = pilot.app.query_one(PRContextPanel)
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.disabled:
                        panel.index = i
                        break
                await pilot.pause()
                assert self._viewer_text(pilot) == initial


class TestActionRefresh:
    async def test_refresh_calls_github(self, worktree: Path) -> None:
        with patch(
            "perch.services.github.get_pr_context", return_value=None
        ) as mock_pr, patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                initial = mock_pr.call_count
                panel = pilot.app.query_one(PRContextPanel)
                panel.action_refresh()
                await pilot.pause()
                await pilot.pause()
                assert mock_pr.call_count > initial
