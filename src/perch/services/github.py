from __future__ import annotations

import json
import re
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
            "title,number,url,body,reviewDecision,reviews,comments",
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

    pr_url = data.get("url", "")

    reviews = [
        PRReview(
            author=r.get("author", {}).get("login", "unknown"),
            state=r.get("state", ""),
            body=r.get("body", ""),
            submitted_at=r.get("submittedAt", ""),
            url=r.get("url", "") or pr_url,
        )
        for r in data.get("reviews", [])
    ]

    comments = [
        PRComment(
            author=c.get("author", {}).get("login", "unknown"),
            body=c.get("body", ""),
            created_at=c.get("createdAt", ""),
            url=c.get("url", "") or pr_url,
        )
        for c in data.get("comments", [])
    ]

    return PRContext(
        title=data.get("title", ""),
        number=data.get("number", 0),
        url=data.get("url", ""),
        review_decision=data.get("reviewDecision", "") or "",
        body=data.get("body", ""),
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
            workflow=c.get("workflow", {}).get("name", "")
            if isinstance(c.get("workflow"), dict)
            else str(c.get("workflow", "")),
        )
        for c in data
    ]


def parse_ci_link(link: str) -> tuple[str, str] | None:
    """Extract (run_id, job_id) from a GitHub Actions job link."""
    m = re.search(r"/actions/runs/(\d+)/job/(\d+)", link)
    if m:
        return m.group(1), m.group(2)
    return None


def get_job_log(link: str, cwd: Path) -> str:
    """Fetch CI job logs from GitHub Actions."""
    ids = parse_ci_link(link)
    if ids is None:
        return f"Cannot parse job URL: {link}"

    run_id, job_id = ids
    result = _run_gh(
        ["run", "view", run_id, "--log", "-j", job_id],
        cwd=cwd,
    )
    if result.returncode != 0:
        result = _run_gh(
            ["run", "view", run_id, "--log-failed", "-j", job_id],
            cwd=cwd,
        )
    if result.returncode != 0:
        return f"Failed to fetch logs: {result.stderr.strip()}"
    return result.stdout
