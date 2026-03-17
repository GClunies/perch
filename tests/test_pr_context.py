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
    reviews: list[PRReview] | None = None,
    comments: list[PRComment] | None = None,
) -> PRContext:
    return PRContext(
        title=title,
        number=number,
        url=url,
        review_decision=review_decision,
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
                assert "No checks" in text


class TestOpenItem:
    async def test_open_pr_header(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                # Find the PR header item (has the PR URL)
                for idx, url in panel._item_urls.items():
                    if "pull/42" in url:
                        panel.index = idx
                        break
                panel.action_open_item()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/pull/42"
                )

    async def test_open_check_link(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        p1, p2 = _patches(pr=pr, checks=checks)
        with p1, p2, patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                # Find a check item by looking for its URL
                for idx, url in panel._item_urls.items():
                    if "runs/123" in url:
                        panel.index = idx
                        break
                panel.action_open_item()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/123"
                )

    async def test_item_without_url_does_nothing(self, worktree: Path) -> None:
        pr = _make_pr_context()
        p1, p2 = _patches(pr=pr)
        with p1, p2, patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                # Find an index that has no URL
                for i in range(len(panel)):
                    if i not in panel._item_urls:
                        panel.index = i
                        break
                panel.action_open_item()
                mock_open.assert_not_called()


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
