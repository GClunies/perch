"""Custom command provider for the Perch command palette."""

from __future__ import annotations

from textual.command import DiscoveryHit, Hit, Hits, Provider


# Commands: (display_name, hotkey_display, action_name)
COMMANDS: list[tuple[str, str, str]] = [
    ("Quit", "q", "quit"),
    ("Switch Pane", "Tab", "focus_next_pane"),
    ("Files Tab", "1", "show_tab('tab-files')"),
    ("Git Tab", "2", "show_tab('tab-git')"),
    ("PR Tab", "3", "show_tab('tab-pr')"),
    ("Toggle Diff View", "d", "toggle_diff"),
    ("Toggle Diff Layout", "s", "toggle_diff_layout"),
    ("Next File in Diff", "n", "next_diff_file"),
    ("Previous File in Diff", "p", "prev_diff_file"),
    ("Focus Mode", "f", "toggle_focus_mode"),
    ("Fuzzy File Search", "Ctrl+P", "file_search"),
    ("Open in Editor", "e", "open_editor"),
    ("Shrink Left Pane", "[", "shrink_left_pane"),
    ("Grow Left Pane", "]", "grow_left_pane"),
]


class DiscoveryCommandProvider(Provider):
    """Provides all Perch commands for the command palette."""

    async def discover(self) -> Hits:
        """Yield all commands as discovery hits."""
        for display_name, hotkey, action in COMMANDS:
            yield DiscoveryHit(
                display=f"{display_name} — {hotkey}",
                command=self._make_command(action),
                help=f"Hotkey: {hotkey}",
            )

    async def search(self, query: str) -> Hits:
        """Search commands by fuzzy matching against the query."""
        matcher = self.matcher(query)
        for display_name, hotkey, action in COMMANDS:
            text = f"{display_name} — {hotkey}"
            score = matcher.match(text)
            if score > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(text),
                    command=self._make_command(action),
                    help=f"Hotkey: {hotkey}",
                )

    def _make_command(self, action: str):
        """Create a callback that runs the given app action."""

        async def command() -> None:
            await self.app.run_action(action)

        return command
