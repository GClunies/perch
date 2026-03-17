"""Tests for PRContextPanel widget."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Collapsible, DataTable, Label, Static

from perch.app import PerchApp
from perch.models import CICheck, PRComment, PRContext, PRReview
from perch.widgets.pr_context import PRContextPanel


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Create a minimal worktree with a file."""
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


class TestPRContextPanelCompose:
    """Tests for compose() — yields correct child widgets."""

    async def test_has_pr_header(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                panel = pilot.app.query_one(PRContextPanel)
                header = panel.query_one("#pr-header", Static)
                assert header is not None

    async def test_has_reviews_collapsible(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                panel = pilot.app.query_one(PRContextPanel)
                reviews = panel.query_one("#pr-reviews", Collapsible)
                assert reviews is not None

    async def test_has_comments_collapsible(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                panel = pilot.app.query_one(PRContextPanel)
                comments = panel.query_one("#pr-comments", Collapsible)
                assert comments is not None

    async def test_has_checks_collapsible_with_datatable(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                panel = pilot.app.query_one(PRContextPanel)
                checks = panel.query_one("#pr-checks", Collapsible)
                assert checks is not None
                table = panel.query_one("#checks-table", DataTable)
                assert table is not None


class TestShowGhMissing:
    """Tests for _show_gh_missing() — when gh CLI is not found."""

    async def test_shows_gh_missing_message(self, worktree: Path) -> None:
        with patch(
            "perch.services.github.get_pr_context",
            side_effect=FileNotFoundError("gh not found"),
        ), patch(
            "perch.services.github.get_checks",
            side_effect=FileNotFoundError("gh not found"),
        ):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                header = panel.query_one("#pr-header", Static)
                rendered = header.render()
                assert "gh CLI not found" in str(rendered)

    async def test_hides_collapsibles_when_gh_missing(self, worktree: Path) -> None:
        with patch(
            "perch.services.github.get_pr_context",
            side_effect=FileNotFoundError("gh not found"),
        ), patch(
            "perch.services.github.get_checks",
            side_effect=FileNotFoundError("gh not found"),
        ):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                for cid in ("pr-reviews", "pr-comments", "pr-checks"):
                    assert panel.query_one(f"#{cid}", Collapsible).display is False


class TestUpdateDisplayNoPR:
    """Tests for _update_display() when no PR is open."""

    async def test_no_pr_shows_message(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                header = panel.query_one("#pr-header", Static)
                rendered = header.render()
                assert "No PR open" in str(rendered)

    async def test_no_pr_hides_collapsibles(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                for cid in ("pr-reviews", "pr-comments", "pr-checks"):
                    assert panel.query_one(f"#{cid}", Collapsible).display is False


class TestUpdateDisplayWithPR:
    """Tests for _update_display() when a PR exists."""

    async def test_pr_header_shows_number_and_title(self, worktree: Path) -> None:
        pr = _make_pr_context(title="Fix the thing", number=99, review_decision="APPROVED")
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                header = panel.query_one("#pr-header", Static)
                rendered = str(header.render())
                assert "#99" in rendered
                assert "Fix the thing" in rendered
                assert "APPROVED" in rendered

    async def test_pr_with_no_reviews_shows_placeholder(self, worktree: Path) -> None:
        pr = _make_pr_context(reviews=[])
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                reviews_section = panel.query_one("#pr-reviews", Collapsible)
                label = reviews_section.query_one(Label)
                rendered = str(label.render())
                assert "No reviews yet" in rendered

    async def test_pr_with_reviews_shows_authors(self, worktree: Path) -> None:
        pr = _make_pr_context(
            reviews=[
                PRReview(author="alice", state="APPROVED", body="LGTM", submitted_at="2025-01-15T10:00:00Z"),
                PRReview(author="bob", state="CHANGES_REQUESTED", body="Fix tests", submitted_at="2025-01-15T11:00:00Z"),
            ]
        )
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                reviews_section = panel.query_one("#pr-reviews", Collapsible)
                label = reviews_section.query_one(Label)
                rendered = str(label.render())
                assert "alice" in rendered
                assert "bob" in rendered
                assert "APPROVED" in rendered
                assert "CHANGES_REQUESTED" in rendered

    async def test_pr_with_no_comments_shows_placeholder(self, worktree: Path) -> None:
        pr = _make_pr_context(comments=[])
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                comments_section = panel.query_one("#pr-comments", Collapsible)
                label = comments_section.query_one(Label)
                rendered = str(label.render())
                assert "No comments" in rendered

    async def test_pr_with_comments_shows_authors(self, worktree: Path) -> None:
        pr = _make_pr_context(
            comments=[
                PRComment(author="carol", body="Nice work!", created_at="2025-01-15T12:00:00Z"),
            ]
        )
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                comments_section = panel.query_one("#pr-comments", Collapsible)
                label = comments_section.query_one(Label)
                rendered = str(label.render())
                assert "carol" in rendered
                assert "Nice work!" in rendered

    async def test_checks_table_populated(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=checks):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                table = panel.query_one("#checks-table", DataTable)
                assert table.row_count == 2

    async def test_review_decision_none_shows_none(self, worktree: Path) -> None:
        pr = _make_pr_context(review_decision="")
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                header = panel.query_one("#pr-header", Static)
                rendered = str(header.render())
                assert "NONE" in rendered

    async def test_review_with_no_body(self, worktree: Path) -> None:
        pr = _make_pr_context(
            reviews=[
                PRReview(author="dan", state="APPROVED", body="", submitted_at=""),
            ]
        )
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                reviews_section = panel.query_one("#pr-reviews", Collapsible)
                label = reviews_section.query_one(Label)
                rendered = str(label.render())
                assert "dan" in rendered

    async def test_comment_with_no_body(self, worktree: Path) -> None:
        pr = _make_pr_context(
            comments=[
                PRComment(author="eve", body="", created_at=""),
            ]
        )
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                comments_section = panel.query_one("#pr-comments", Collapsible)
                label = comments_section.query_one(Label)
                rendered = str(label.render())
                assert "eve" in rendered

    async def test_sections_displayed_when_pr_exists(self, worktree: Path) -> None:
        pr = _make_pr_context()
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                for cid in ("pr-reviews", "pr-comments", "pr-checks"):
                    assert panel.query_one(f"#{cid}", Collapsible).display is True


class TestActionRefresh:
    """Tests for action_refresh()."""

    async def test_action_refresh_triggers_do_refresh(self, worktree: Path) -> None:
        with patch("perch.services.github.get_pr_context", return_value=None) as mock_pr, \
             patch("perch.services.github.get_checks", return_value=[]):
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                initial_call_count = mock_pr.call_count
                panel = pilot.app.query_one(PRContextPanel)
                panel.action_refresh()
                await pilot.pause()
                await pilot.pause()
                assert mock_pr.call_count > initial_call_count


class TestActionOpenCheck:
    """Tests for action_open_check()."""

    async def test_open_check_opens_browser(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=checks), \
             patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                table = panel.query_one("#checks-table", DataTable)
                # Focus the table and select first row
                table.focus()
                await pilot.pause()
                table.cursor_coordinate = table.cursor_coordinate
                panel.action_open_check()
                mock_open.assert_called_once_with(
                    "https://github.com/org/repo/actions/runs/123"
                )

    async def test_open_check_no_focus_does_nothing(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = _make_checks()
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=checks), \
             patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                # Don't focus the table
                panel.action_open_check()
                mock_open.assert_not_called()

    async def test_open_check_empty_table_does_nothing(self, worktree: Path) -> None:
        pr = _make_pr_context()
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=[]), \
             patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                table = panel.query_one("#checks-table", DataTable)
                table.focus()
                await pilot.pause()
                panel.action_open_check()
                mock_open.assert_not_called()

    async def test_open_check_no_link_does_nothing(self, worktree: Path) -> None:
        pr = _make_pr_context()
        checks = [
            CICheck(name="build", state="SUCCESS", bucket="pass", link="", workflow="CI"),
        ]
        with patch("perch.services.github.get_pr_context", return_value=pr), \
             patch("perch.services.github.get_checks", return_value=checks), \
             patch("webbrowser.open") as mock_open:
            async with PerchApp(worktree).run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                panel = pilot.app.query_one(PRContextPanel)
                table = panel.query_one("#checks-table", DataTable)
                table.focus()
                await pilot.pause()
                panel.action_open_check()
                mock_open.assert_not_called()
