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
