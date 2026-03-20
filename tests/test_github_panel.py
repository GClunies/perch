"""Tests for GitHubPanel widget."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from textual.widgets import ListItem

from perch.app import PerchApp
from perch.models import CICheck, PRComment, PRContext, PRReview
from perch.widgets.github_panel import GitHubPanel


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


def _get_all_text(panel: GitHubPanel) -> str:
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
                panel = pilot.app.query_one(GitHubPanel)
                text = _get_all_text(panel)
                assert "gh CLI not found" in text


class TestNoPR:
    async def test_no_pr_shows_message(self, worktree: Path) -> None:
        p1, p2 = _patches(pr=None)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
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
                panel = pilot.app.query_one(GitHubPanel)
                text = _get_all_text(panel)
                assert "#99" in text
                assert "Fix the thing" in text
                assert "\uf00c" in text  # nf-fa-check icon for APPROVED

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
                panel = pilot.app.query_one(GitHubPanel)
                text = _get_all_text(panel)
                assert "alice" in text
                assert "\uf00c" in text  # nf-fa-check icon for APPROVED

    async def test_no_reviews_placeholder(self, worktree: Path) -> None:
        pr = _make_pr_context(reviews=[])
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
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
                panel = pilot.app.query_one(GitHubPanel)
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
                panel = pilot.app.query_one(GitHubPanel)
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
                panel = pilot.app.query_one(GitHubPanel)
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
                panel = pilot.app.query_one(GitHubPanel)
                text = _get_all_text(panel)
                assert "No actions" in text


class TestOpenInBrowser:
    """Pressing 'o' on a highlighted item opens its URL in the browser."""

    @staticmethod
    async def _activate_github_tab(pilot) -> GitHubPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-github"
        await pilot.pause()
        panel = pilot.app.query_one(GitHubPanel)
        panel.focus()
        await pilot.pause()
        return panel

    @staticmethod
    def _navigate_to(panel: GitHubPanel, text_match: str) -> None:
        """Set the highlight to the item matching the given text."""
        item = _find_item_with_text(panel, text_match)
        assert item is not None, f"Item with {text_match!r} not found"
        panel.index = list(panel.children).index(item)

    async def test_o_opens_pr_header(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.github_panel.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                self._navigate_to(panel, "#42")
                await pilot.press("o")
                await pilot.pause()
                mock_open.assert_called_once_with("https://github.com/org/repo/pull/42")

    async def test_o_opens_ci_check(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.github_panel.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                self._navigate_to(panel, "build")
                await pilot.press("o")
                await pilot.pause()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/123"
                )

    async def test_arrow_down_then_o(self, worktree: Path) -> None:
        """Navigate with arrow keys, then press 'o' to open."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("perch.widgets.github_panel.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                self._navigate_to(panel, "#42")
                from perch.widgets.github_panel import ClickableItem

                for _ in range(20):
                    await pilot.press("down")
                    await pilot.pause()
                    hc = panel.highlighted_child
                    if isinstance(hc, ClickableItem) and "actions" in hc.url:
                        break
                await pilot.press("o")
                await pilot.pause()
                mock_open.assert_called_once()
                url = mock_open.call_args[0][0]
                assert "actions/runs" in url

    async def test_o_on_header_does_nothing(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("perch.widgets.github_panel.webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.disabled:
                        panel.index = i
                        break
                panel.focus()
                await pilot.press("o")
                await pilot.pause()
                mock_open.assert_not_called()


def _find_item_with_text(panel: GitHubPanel, text_match: str) -> ListItem | None:
    """Find a non-disabled ListItem containing the given text."""
    from textual.widgets import Label as _Label

    for child in panel.children:
        if isinstance(child, ListItem) and not child.disabled:
            for label in child.query(_Label):
                if text_match in str(label.render()):
                    return child
    return None


class TestHighlightPreview:
    """Navigating to an item in the PR tab should preview its content in the Viewer."""

    @staticmethod
    async def _activate_pr_tab(pilot) -> GitHubPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-github"
        await pilot.pause()
        panel = pilot.app.query_one(GitHubPanel)
        panel.focus()
        await pilot.pause()
        return panel

    @staticmethod
    def _viewer_text(pilot) -> str:
        """Render the Viewer content to plain text."""
        from io import StringIO

        from rich.console import Console

        from perch.widgets.viewer import Viewer

        viewer = pilot.app.query_one(Viewer)
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
        with (
            p1,
            p2,
            patch("perch.services.github.get_job_log", return_value="log output"),
        ):
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                check_item = _find_item_with_text(panel, "build")
                assert check_item is not None
                panel.index = list(panel.children).index(check_item)
                await pilot.pause()
                await pilot.pause()
                content = self._viewer_text(pilot)
                # Should show loading or the actual log (depending on timing)
                assert (
                    "Loading" in content or "log output" in content or "CI" in content
                )

    async def test_highlight_ci_check_shows_log(self, worktree: Path) -> None:
        """After fetching, the CI check log is displayed in the viewer."""
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with (
            p1,
            p2,
            patch(
                "perch.services.github.get_job_log", return_value="step 1\nstep 2\nDone"
            ),
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
                panel = pilot.app.query_one(GitHubPanel)
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.disabled:
                        panel.index = i
                        break
                await pilot.pause()
                assert self._viewer_text(pilot) == initial


class TestHighlightReview:
    """Navigating to a review should show its body in the viewer."""

    @staticmethod
    async def _activate_pr_tab(pilot) -> GitHubPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-github"
        await pilot.pause()
        panel = pilot.app.query_one(GitHubPanel)
        panel.focus()
        await pilot.pause()
        return panel

    async def test_highlight_review_shows_body(self, worktree: Path) -> None:
        pr = _make_pr_context(
            reviews=[
                PRReview(
                    author="alice",
                    state="APPROVED",
                    body="Looks great!",
                    submitted_at="2h ago",
                    url="https://github.com/org/repo/pull/42#pullrequestreview-1",
                ),
            ],
        )
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                review_item = _find_item_with_text(panel, "alice")
                assert review_item is not None
                panel.index = list(panel.children).index(review_item)
                await pilot.pause()
                await pilot.pause()
                from perch.widgets.viewer import Viewer

                viewer = pilot.app.query_one(Viewer)
                content = viewer._content._Static__content
                assert content is not None
                from io import StringIO

                from rich.console import Console

                console = Console(file=StringIO(), width=120)
                console.print(content)
                text = console.file.getvalue()
                assert "Looks great" in text

    async def test_highlight_review_no_body(self, worktree: Path) -> None:
        pr = _make_pr_context(
            reviews=[
                PRReview(
                    author="bob",
                    state="COMMENTED",
                    body="",
                    submitted_at="1d ago",
                    url="https://github.com/org/repo/pull/42#pullrequestreview-2",
                ),
            ],
        )
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_pr_tab(pilot)
                review_item = _find_item_with_text(panel, "bob")
                assert review_item is not None
                panel.index = list(panel.children).index(review_item)
                await pilot.pause()
                await pilot.pause()
                from perch.widgets.viewer import Viewer

                viewer = pilot.app.query_one(Viewer)
                content = viewer._content._Static__content
                assert content is not None
                from io import StringIO

                from rich.console import Console

                console = Console(file=StringIO(), width=120)
                console.print(content)
                text = console.file.getvalue()
                assert "No review body" in text


class TestActivateCurrentPreview:
    """Tests for GitHubPanel.activate_current_preview()."""

    async def test_no_op_when_no_preview_item_highlighted(
        self, worktree: Path
    ) -> None:
        """activate_current_preview does nothing when no previewable item is active."""
        from unittest.mock import MagicMock

        p1, p2 = _patches(pr=None, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = pilot.app.query_one(GitHubPanel)
                await pilot.pause()
                await pilot.pause()
                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    panel.activate_current_preview()
                mock_post.assert_not_called()

    async def test_posts_preview_for_pr_body(self, worktree: Path) -> None:
        """activate_current_preview posts PreviewRequested for the PR title item."""
        from unittest.mock import MagicMock

        pr = _make_pr_context(body="## My PR")
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                from textual.widgets import TabbedContent

                pilot.app.query_one(TabbedContent).active = "tab-github"
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
                # Point the index at the PR title item (first enabled item)
                from perch.widgets.github_panel import ClickableItem

                for i, child in enumerate(panel.children):
                    if isinstance(child, ClickableItem) and child.preview_kind == "pr_body":
                        panel.index = i
                        break
                await pilot.pause()

                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    panel.activate_current_preview()
                assert mock_post.call_count == 1
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitHubPanel.PreviewRequested)
                assert msg.preview_kind == "pr_body"
                assert "My PR" in msg.body


class TestActionRefresh:
    async def test_refresh_calls_github(self, worktree: Path) -> None:
        with (
            patch("perch.services.github.get_pr_context", return_value=None) as mock_pr,
            patch("perch.services.github.get_checks", return_value=[]),
        ):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                initial = mock_pr.call_count
                panel = pilot.app.query_one(GitHubPanel)
                panel.action_refresh()
                await pilot.pause()
                await pilot.pause()
                assert mock_pr.call_count > initial


class TestTwoPhaseLoading:
    """PR context should render before actions finish loading."""

    async def test_actions_show_loading_then_resolve(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        with (
            patch("perch.services.github.get_pr_context", return_value=pr),
            patch("perch.services.github.get_checks", return_value=checks),
        ):
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                for _ in range(20):
                    await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
                text = _get_all_text(panel)
                # After full load, actions should be resolved (not "Loading")
                assert "Loading actions" not in text
                assert "build" in text or "lint" in text

    async def test_gh_missing_for_checks_still_shows_pr(self, worktree: Path) -> None:
        """If get_checks raises FileNotFoundError, PR data should still display."""
        pr = _make_pr_context()
        with (
            patch("perch.services.github.get_pr_context", return_value=pr),
            patch(
                "perch.services.github.get_checks",
                side_effect=FileNotFoundError("no gh"),
            ),
        ):
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                for _ in range(20):
                    await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
                text = _get_all_text(panel)
                assert "#42" in text
                assert "Fix bug" in text


class TestStaleClickGuard:
    """Firing _on_list_item__child_clicked with a stale item should not crash."""

    async def test_stale_click_does_not_crash(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr, checks=_make_checks())
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(GitHubPanel)
                # Grab a reference to an item currently in the list
                from perch.widgets.github_panel import ClickableItem

                stale_item = None
                for child in panel.children:
                    if isinstance(child, ClickableItem):
                        stale_item = child
                        break
                assert stale_item is not None

                # Trigger a display rebuild, which clears and re-populates
                panel._update_display()
                await pilot.pause()

                # Fabricate a _ChildClicked event from the now-stale item
                event = ListItem._ChildClicked(stale_item)
                # This should silently swallow the ValueError
                panel._on_list_item__child_clicked(event)


class TestPageNavigation:
    """Tests for action_page_up / action_page_down."""

    @staticmethod
    async def _activate_github_tab(pilot) -> GitHubPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-github"
        await pilot.pause()
        panel = pilot.app.query_one(GitHubPanel)
        panel.focus()
        await pilot.pause()
        return panel

    async def test_page_down(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                # Ensure index starts at the first enabled item (0 or small)
                assert panel.index is not None
                start = panel.index
                panel.action_page_down()
                await pilot.pause()
                assert panel.index is not None
                assert panel.index >= start

    async def test_page_up_after_page_down(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                # Move down first so there's room to go back up
                panel.action_page_down()
                await pilot.pause()
                after_down = panel.index
                assert after_down is not None
                panel.action_page_up()
                await pilot.pause()
                assert panel.index is not None
                assert panel.index <= after_down

    async def test_page_up_at_top(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                panel.index = 0
                await pilot.pause()
                panel.action_page_up()
                await pilot.pause()
                assert panel.index == 0


class TestCopyUrl:
    """Tests for action_copy_url."""

    @staticmethod
    async def _activate_github_tab(pilot) -> GitHubPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-github"
        await pilot.pause()
        panel = pilot.app.query_one(GitHubPanel)
        panel.focus()
        await pilot.pause()
        return panel

    async def test_copy_url_copies_pr_url(self, worktree: Path) -> None:
        from unittest.mock import MagicMock

        pr = _make_pr_context(url="https://github.com/org/repo/pull/42")
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                # Navigate to the PR title item
                pr_item = _find_item_with_text(panel, "#42")
                assert pr_item is not None
                panel.index = list(panel.children).index(pr_item)
                await pilot.pause()

                mock_copy = MagicMock()
                mock_notify = MagicMock()
                with (
                    patch.object(pilot.app, "copy_to_clipboard", mock_copy),
                    patch.object(pilot.app, "notify", mock_notify),
                ):
                    panel.action_copy_url()
                mock_copy.assert_called_once_with(
                    "https://github.com/org/repo/pull/42"
                )
                mock_notify.assert_called_once()

    async def test_copy_url_noop_on_header(self, worktree: Path) -> None:
        from unittest.mock import MagicMock

        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)
                # Navigate to a disabled section header
                for i, child in enumerate(panel.children):
                    if isinstance(child, ListItem) and child.disabled:
                        panel.index = i
                        break
                await pilot.pause()

                mock_copy = MagicMock()
                with patch.object(pilot.app, "copy_to_clipboard", mock_copy):
                    panel.action_copy_url()
                mock_copy.assert_not_called()


class TestOnListViewHighlightedPrBody:
    """Highlighting the PR title item posts a preview with the PR body."""

    @staticmethod
    async def _activate_github_tab(pilot) -> GitHubPanel:
        from textual.widgets import TabbedContent

        await pilot.pause()
        await pilot.pause()
        pilot.app.query_one(TabbedContent).active = "tab-github"
        await pilot.pause()
        panel = pilot.app.query_one(GitHubPanel)
        panel.focus()
        await pilot.pause()
        return panel

    async def test_highlight_pr_title_uses_pr_context_body(
        self, worktree: Path
    ) -> None:
        """When a pr_body item is highlighted, body comes from _pr_context.body."""
        from unittest.mock import MagicMock

        pr = _make_pr_context(body="## Full PR Body\nWith details")
        p1, p2 = _patches(pr=pr, checks=[])
        with p1, p2:
            async with PerchApp(worktree).run_test(size=(120, 40)) as pilot:
                panel = await self._activate_github_tab(pilot)

                from perch.widgets.github_panel import ClickableItem

                # Find the PR title item (preview_kind == "pr_body")
                pr_item_idx = None
                for i, child in enumerate(panel.children):
                    if (
                        isinstance(child, ClickableItem)
                        and child.preview_kind == "pr_body"
                    ):
                        pr_item_idx = i
                        break
                assert pr_item_idx is not None

                # Capture the PreviewRequested message
                mock_post = MagicMock()
                with patch.object(panel, "post_message", mock_post):
                    # Fabricate a Highlighted event for the PR title item
                    event = GitHubPanel.Highlighted(
                        panel, panel._nodes[pr_item_idx]
                    )
                    panel.on_list_view_highlighted(event)

                mock_post.assert_called_once()
                msg = mock_post.call_args[0][0]
                assert isinstance(msg, GitHubPanel.PreviewRequested)
                assert msg.preview_kind == "pr_body"
                # Body should come from the full _pr_context.body, not item
                assert "Full PR Body" in msg.body
