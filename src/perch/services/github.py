from __future__ import annotations

import json
import subprocess
from pathlib import Path

from perch.models import CICheck, PRComment, PRContext, PRReview


def _run_gh(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def get_pr_context(root: Path) -> PRContext | None:
    """Fetch PR context for the current branch. Returns None if no PR exists."""
    result = _run_gh(
        [
            "pr",
            "view",
            "--json",
            "title,number,url,reviewDecision,reviews,comments",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return None
    return parse_pr_view(result.stdout)


def parse_pr_view(raw: str) -> PRContext | None:
    """Parse JSON output from ``gh pr view --json ...``."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None

    reviews = [
        PRReview(
            author=r.get("author", {}).get("login", "unknown"),
            state=r.get("state", ""),
            body=r.get("body", ""),
            submitted_at=r.get("submittedAt", ""),
        )
        for r in data.get("reviews", [])
    ]

    comments = [
        PRComment(
            author=c.get("author", {}).get("login", "unknown"),
            body=c.get("body", ""),
            created_at=c.get("createdAt", ""),
        )
        for c in data.get("comments", [])
    ]

    return PRContext(
        title=data.get("title", ""),
        number=data.get("number", 0),
        url=data.get("url", ""),
        review_decision=data.get("reviewDecision", "") or "",
        reviews=reviews,
        comments=comments,
    )


def get_checks(root: Path) -> list[CICheck]:
    """Fetch CI checks for the current branch's PR."""
    result = _run_gh(
        ["pr", "checks", "--json", "name,state,bucket,link,workflow"],
        cwd=root,
    )
    if result.returncode != 0:
        return []
    return parse_checks(result.stdout)


def parse_checks(raw: str) -> list[CICheck]:
    """Parse JSON output from ``gh pr checks --json ...``."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        return []

    return [
        CICheck(
            name=c.get("name", ""),
            state=c.get("state", ""),
            bucket=c.get("bucket", ""),
            link=c.get("link", ""),
            workflow=c.get("workflow", {}).get("name", "") if isinstance(c.get("workflow"), dict) else str(c.get("workflow", "")),
        )
        for c in data
    ]
