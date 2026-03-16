import json

from perch.models import CICheck, PRComment, PRReview
from perch.services.github import parse_checks, parse_pr_view


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
