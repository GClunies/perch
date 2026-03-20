from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GitFile:
    path: str
    status: str
    staged: bool


@dataclass
class GitStatusData:
    unstaged: list[GitFile] = field(default_factory=list)
    staged: list[GitFile] = field(default_factory=list)
    untracked: list[GitFile] = field(default_factory=list)


@dataclass
class Commit:
    hash: str
    message: str
    author: str
    relative_time: str


@dataclass
class CommitFile:
    path: str
    status: str
    old_path: str | None = None


@dataclass
class CommitSummary:
    hash: str
    subject: str
    body: str
    author: str
    date: str
    stats: str


@dataclass
class PRReview:
    author: str
    state: str
    body: str
    submitted_at: str
    url: str = ""


@dataclass
class PRComment:
    author: str
    body: str
    created_at: str
    url: str = ""


@dataclass
class CICheck:
    name: str
    state: str
    bucket: str
    link: str
    workflow: str


@dataclass
class PRContext:
    title: str
    number: int
    url: str
    review_decision: str
    body: str = ""
    reviews: list[PRReview] = field(default_factory=list)
    comments: list[PRComment] = field(default_factory=list)
    checks: list[CICheck] = field(default_factory=list)
