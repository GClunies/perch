import json
import subprocess
from pathlib import Path
from unittest.mock import call, patch

from perch.models import CICheck, PRComment, PRReview
from perch.services.github import (
    get_checks,
    get_job_log,
    get_pr_context,
    parse_checks,
    parse_ci_link,
    parse_pr_view,
)


class TestParsePrView:
    def test_empty_string(self) -> None:
        assert parse_pr_view("") is None

    def test_invalid_json(self) -> None:
        assert parse_pr_view("not json") is None

    def test_minimal_pr(self) -> None:
        data = {
            "title": "Fix bug",
            "number": 42,
            "url": "https://github.com/org/repo/pull/42",
            "reviewDecision": "APPROVED",
            "reviews": [],
            "comments": [],
        }
        result = parse_pr_view(json.dumps(data))
        assert result is not None
        assert result.title == "Fix bug"
        assert result.number == 42
        assert result.url == "https://github.com/org/repo/pull/42"
        assert result.review_decision == "APPROVED"
        assert result.reviews == []
        assert result.comments == []

    def test_pr_with_reviews(self) -> None:
        data = {
            "title": "Add feature",
            "number": 10,
            "url": "https://github.com/org/repo/pull/10",
            "reviewDecision": "CHANGES_REQUESTED",
            "reviews": [
                {
                    "author": {"login": "alice"},
                    "state": "APPROVED",
                    "body": "LGTM",
                    "submittedAt": "2025-01-15T10:00:00Z",
                },
                {
                    "author": {"login": "bob"},
                    "state": "CHANGES_REQUESTED",
                    "body": "Please fix the tests",
                    "submittedAt": "2025-01-15T11:00:00Z",
                },
            ],
            "comments": [],
        }
        result = parse_pr_view(json.dumps(data))
        assert result is not None
        assert len(result.reviews) == 2
        assert result.reviews[0] == PRReview(
            author="alice",
            state="APPROVED",
            body="LGTM",
            submitted_at="2025-01-15T10:00:00Z",
            url="https://github.com/org/repo/pull/10",
        )
        assert result.reviews[1].author == "bob"
        assert result.reviews[1].state == "CHANGES_REQUESTED"

    def test_pr_with_comments(self) -> None:
        data = {
            "title": "Update docs",
            "number": 5,
            "url": "https://github.com/org/repo/pull/5",
            "reviewDecision": "",
            "reviews": [],
            "comments": [
                {
                    "author": {"login": "carol"},
                    "body": "Nice work!",
                    "createdAt": "2025-01-15T12:00:00Z",
                },
            ],
        }
        result = parse_pr_view(json.dumps(data))
        assert result is not None
        assert len(result.comments) == 1
        assert result.comments[0] == PRComment(
            author="carol",
            body="Nice work!",
            created_at="2025-01-15T12:00:00Z",
            url="https://github.com/org/repo/pull/5",
        )

    def test_null_review_decision(self) -> None:
        data = {
            "title": "Draft PR",
            "number": 1,
            "url": "https://github.com/org/repo/pull/1",
            "reviewDecision": None,
            "reviews": [],
            "comments": [],
        }
        result = parse_pr_view(json.dumps(data))
        assert result is not None
        assert result.review_decision == ""

    def test_missing_fields_use_defaults(self) -> None:
        data = {}
        result = parse_pr_view(json.dumps(data))
        assert result is not None
        assert result.title == ""
        assert result.number == 0
        assert result.reviews == []

    def test_review_missing_author(self) -> None:
        data = {
            "title": "PR",
            "number": 1,
            "url": "",
            "reviewDecision": "",
            "reviews": [{"state": "APPROVED", "body": "", "submittedAt": ""}],
            "comments": [],
        }
        result = parse_pr_view(json.dumps(data))
        assert result is not None
        assert result.reviews[0].author == "unknown"


class TestParseChecks:
    def test_empty_string(self) -> None:
        assert parse_checks("") == []

    def test_invalid_json(self) -> None:
        assert parse_checks("not json") == []

    def test_not_a_list(self) -> None:
        assert parse_checks('{"key": "value"}') == []

    def test_single_check(self) -> None:
        data = [
            {
                "name": "build",
                "state": "SUCCESS",
                "bucket": "pass",
                "link": "https://github.com/org/repo/actions/runs/123",
                "workflow": {"name": "CI"},
            }
        ]
        result = parse_checks(json.dumps(data))
        assert result == [
            CICheck(
                name="build",
                state="SUCCESS",
                bucket="pass",
                link="https://github.com/org/repo/actions/runs/123",
                workflow="CI",
            )
        ]

    def test_multiple_checks(self) -> None:
        data = [
            {
                "name": "lint",
                "state": "SUCCESS",
                "bucket": "pass",
                "link": "https://example.com/1",
                "workflow": {"name": "Lint"},
            },
            {
                "name": "test",
                "state": "FAILURE",
                "bucket": "fail",
                "link": "https://example.com/2",
                "workflow": {"name": "Test"},
            },
            {
                "name": "deploy",
                "state": "PENDING",
                "bucket": "pending",
                "link": "",
                "workflow": {"name": "Deploy"},
            },
        ]
        result = parse_checks(json.dumps(data))
        assert len(result) == 3
        assert result[0].bucket == "pass"
        assert result[1].bucket == "fail"
        assert result[2].bucket == "pending"

    def test_workflow_as_string(self) -> None:
        data = [
            {
                "name": "check",
                "state": "SUCCESS",
                "bucket": "pass",
                "link": "",
                "workflow": "Simple Workflow",
            }
        ]
        result = parse_checks(json.dumps(data))
        assert result[0].workflow == "Simple Workflow"

    def test_missing_fields(self) -> None:
        data = [{}]
        result = parse_checks(json.dumps(data))
        assert len(result) == 1
        assert result[0].name == ""
        assert result[0].state == ""
        assert result[0].workflow == ""


class TestGetPrContext:
    """Tests for get_pr_context when _run_gh fails."""

    @patch("perch.services.github._run_gh")
    def test_returns_none_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(  # type: ignore[attr-defined]
            args=["gh", "pr", "view"],
            returncode=1,
            stdout="",
            stderr="no pull requests found",
        )
        result = get_pr_context(Path("/tmp"))
        assert result is None


class TestGetChecks:
    """Tests for get_checks when _run_gh fails."""

    @patch("perch.services.github._run_gh")
    def test_returns_empty_list_on_failure(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(  # type: ignore[attr-defined]
            args=["gh", "pr", "checks"],
            returncode=1,
            stdout="",
            stderr="no pull requests found",
        )
        result = get_checks(Path("/tmp"))
        assert result == []


class TestParseCiLink:
    """Tests for parse_ci_link with non-matching URLs."""

    def test_valid_link(self) -> None:
        result = parse_ci_link(
            "https://github.com/org/repo/actions/runs/12345/job/67890"
        )
        assert result == ("12345", "67890")

    def test_non_github_actions_url(self) -> None:
        result = parse_ci_link("https://circleci.com/gh/org/repo/123")
        assert result is None

    def test_partial_github_url_no_job(self) -> None:
        result = parse_ci_link(
            "https://github.com/org/repo/actions/runs/12345"
        )
        assert result is None

    def test_empty_string(self) -> None:
        result = parse_ci_link("")
        assert result is None

    def test_random_string(self) -> None:
        result = parse_ci_link("not-a-url-at-all")
        assert result is None


class TestGetJobLog:
    """Tests for get_job_log with mocked _run_gh."""

    @patch("perch.services.github._run_gh")
    def test_success_on_first_call(self, mock_run: object) -> None:
        mock_run.return_value = subprocess.CompletedProcess(  # type: ignore[attr-defined]
            args=["gh", "run", "view"],
            returncode=0,
            stdout="Build succeeded\nAll tests passed\n",
            stderr="",
        )
        link = "https://github.com/org/repo/actions/runs/111/job/222"
        result = get_job_log(link, Path("/tmp"))
        assert result == "Build succeeded\nAll tests passed\n"
        mock_run.assert_called_once_with(  # type: ignore[attr-defined]
            ["run", "view", "111", "--log", "-j", "222"],
            cwd=Path("/tmp"),
        )

    @patch("perch.services.github._run_gh")
    def test_fallback_to_log_failed(self, mock_run: object) -> None:
        """When first call fails, falls back to --log-failed."""
        fail = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="error"
        )
        success = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="Failed step log\n", stderr=""
        )
        mock_run.side_effect = [fail, success]  # type: ignore[attr-defined]

        link = "https://github.com/org/repo/actions/runs/111/job/222"
        result = get_job_log(link, Path("/tmp"))
        assert result == "Failed step log\n"
        assert mock_run.call_count == 2  # type: ignore[attr-defined]
        # Second call should use --log-failed
        mock_run.assert_called_with(  # type: ignore[attr-defined]
            ["run", "view", "111", "--log-failed", "-j", "222"],
            cwd=Path("/tmp"),
        )

    @patch("perch.services.github._run_gh")
    def test_both_calls_fail(self, mock_run: object) -> None:
        """When both --log and --log-failed fail, returns error message."""
        fail1 = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="log error"
        )
        fail2 = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="log-failed error"
        )
        mock_run.side_effect = [fail1, fail2]  # type: ignore[attr-defined]

        link = "https://github.com/org/repo/actions/runs/111/job/222"
        result = get_job_log(link, Path("/tmp"))
        assert result == "Failed to fetch logs: log-failed error"

    def test_unparseable_link(self) -> None:
        """When the link can't be parsed, returns error without calling gh."""
        result = get_job_log("https://example.com/not-actions", Path("/tmp"))
        assert result.startswith("Cannot parse job URL:")
