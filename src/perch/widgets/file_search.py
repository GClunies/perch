"""Fuzzy file search modal screen."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListView, ListItem, Label

EXCLUDED_NAMES: set[str] = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "node_modules",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    ".tox",
    ".eggs",
    ".beads",
}


def collect_files(root: Path) -> list[str]:
    """Walk the worktree and return relative file paths, excluding noise dirs."""
    results: list[str] = []
    for item in sorted(root.rglob("*")):
        # Skip if any path component is in the exclusion set or ends with .egg-info
        parts = item.relative_to(root).parts
        if any(p in EXCLUDED_NAMES or p.endswith(".egg-info") for p in parts):
            continue
        if item.is_file():
            results.append(str(item.relative_to(root)))
    return results


def fuzzy_score(query: str, candidate: str) -> int | None:
    """Score a candidate against a fuzzy query.

    Returns None if the candidate does not match, otherwise a score
    where higher is better.

    Matching is case-insensitive. Characters in the query must appear
    in order in the candidate. Scoring rewards:
    - Consecutive character matches
    - Matches at the start of path segments (after / or at position 0)
    - Shorter candidates (less noise)
    """
    if not query:
        return 0

    query_lower = query.lower()
    candidate_lower = candidate.lower()

    # Check if all query chars exist in order
    qi = 0
    positions: list[int] = []
    for ci, ch in enumerate(candidate_lower):
        if qi < len(query_lower) and ch == query_lower[qi]:
            positions.append(ci)
            qi += 1

    if qi < len(query_lower):
        return None  # Not all characters matched

    score = 100  # Base score for any match

    # Bonus for consecutive matches
    for i in range(1, len(positions)):
        if positions[i] == positions[i - 1] + 1:
            score += 10

    # Bonus for matching at start of path segments
    for pos in positions:
        if pos == 0 or candidate[pos - 1] in ("/", "\\", "_", "-", "."):
            score += 8

    # Prefer shorter paths (less noise)
    score -= len(candidate)

    return score


class FileSearchScreen(ModalScreen[str | None]):
    """Modal screen for fuzzy file search."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    FileSearchScreen {
        align: center middle;
    }
    #search-container {
        width: 80;
        max-height: 24;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #search-input {
        margin-bottom: 1;
    }
    #search-results {
        height: 1fr;
    }
    """

    def __init__(self, worktree_path: Path) -> None:
        super().__init__()
        self._worktree_path = worktree_path
        self._files: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Input(placeholder="Search files...", id="search-input")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self._files = collect_files(self._worktree_path)
        self._update_results("")

    @on(Input.Changed, "#search-input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self._update_results(event.value)

    def _update_results(self, query: str) -> None:
        list_view = self.query_one("#search-results", ListView)
        list_view.clear()

        if not query:
            # Show all files when no query
            for path in self._files[:50]:
                list_view.append(ListItem(Label(path), name=path))
            return

        # Score and rank
        scored: list[tuple[int, str]] = []
        for path in self._files:
            s = fuzzy_score(query, path)
            if s is not None:
                scored.append((s, path))

        scored.sort(key=lambda x: x[0], reverse=True)

        for _, path in scored[:50]:
            list_view.append(ListItem(Label(path), name=path))

    @on(ListView.Selected, "#search-results")
    def _on_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.name)

    def key_enter(self) -> None:
        """Dismiss with the currently highlighted item."""
        list_view = self.query_one("#search-results", ListView)
        if list_view.highlighted_child is not None:
            self.dismiss(list_view.highlighted_child.name)

    def action_cancel(self) -> None:
        self.dismiss(None)
