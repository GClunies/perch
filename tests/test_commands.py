"""Tests for the DiscoveryCommandProvider."""

from pathlib import Path

import pytest
from textual.command import DiscoveryHit, Hit

from perch.app import PerchApp
from perch.commands import COMMANDS, DiscoveryCommandProvider


def test_commands_list_is_nonempty():
    """COMMANDS list should have entries."""
    assert len(COMMANDS) > 0


def test_commands_entries_are_tuples_of_three():
    """Each command entry should be (display_name, hotkey, action)."""
    for entry in COMMANDS:
        assert len(entry) == 3
        display_name, hotkey, action = entry
        assert isinstance(display_name, str) and display_name
        assert isinstance(hotkey, str) and hotkey
        assert isinstance(action, str) and action


def test_all_app_actions_covered():
    """Commands list should cover the key app actions."""
    actions = {action for _, _, action in COMMANDS}
    assert "quit" in actions
    assert "file_search" in actions
    assert "open_editor" in actions
    assert "prev_tab" in actions
    assert "next_tab" in actions
    assert "focus_next_pane" in actions
    assert "show_help" in actions
    assert "switch_worktree" in actions


def test_stale_commands_removed():
    """next_diff_file and prev_diff_file should no longer be in COMMANDS."""
    actions = {action for _, _, action in COMMANDS}
    assert "next_diff_file" not in actions
    assert "prev_diff_file" not in actions


def test_commands_count():
    """COMMANDS should have exactly 14 entries after adding Branch Diff."""
    assert len(COMMANDS) == 14


def test_every_command_has_app_action_method():
    """Every action in COMMANDS must have a corresponding action_* method on PerchApp."""
    for _, _, action in COMMANDS:
        method_name = f"action_{action}"
        assert hasattr(PerchApp, method_name), (
            f"PerchApp is missing {method_name!r} for command action {action!r}"
        )


def test_discovery_command_provider_subclasses_provider():
    """DiscoveryCommandProvider should subclass textual.command.Provider."""
    from textual.command import Provider

    assert issubclass(DiscoveryCommandProvider, Provider)


def test_display_format_includes_hotkey():
    """Command display text should include the hotkey after an em dash."""
    for display_name, hotkey, _ in COMMANDS:
        expected = f"{display_name} — {hotkey}"
        assert "—" in expected
        assert hotkey in expected


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    (tmp_path / "hello.py").write_text("print('hello')\n")
    return tmp_path


class TestDiscoverMethod:
    """Tests for DiscoveryCommandProvider.discover()."""

    async def test_discover_yields_all_commands(self, worktree: Path) -> None:
        """discover() should yield one DiscoveryHit per COMMANDS entry."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.discover()]
            assert len(hits) == len(COMMANDS)

    async def test_discover_hits_are_discovery_hits(self, worktree: Path) -> None:
        """Each yielded hit should be a DiscoveryHit instance."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.discover()]
            for hit in hits:
                assert isinstance(hit, DiscoveryHit)

    async def test_discover_display_includes_name_and_hotkey(
        self, worktree: Path
    ) -> None:
        """Each hit display should contain the command name and hotkey."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.discover()]
            for hit, (display_name, hotkey, _) in zip(hits, COMMANDS):
                assert display_name in hit.display
                assert hotkey in hit.display

    async def test_discover_help_text(self, worktree: Path) -> None:
        """Each hit help text should show the hotkey."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.discover()]
            for hit, (_, hotkey, _) in zip(hits, COMMANDS):
                assert hit.help == f"Hotkey: {hotkey}"

    async def test_discover_command_is_callable(self, worktree: Path) -> None:
        """Each hit command should be a callable."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.discover()]
            for hit in hits:
                assert callable(hit.command)


class TestSearchMethod:
    """Tests for DiscoveryCommandProvider.search()."""

    async def test_search_returns_matching_hits(self, worktree: Path) -> None:
        """search('Quit') should return at least one hit."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.search("Quit")]
            assert len(hits) >= 1

    async def test_search_hits_are_hit_instances(self, worktree: Path) -> None:
        """Each search result should be a Hit instance."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.search("Quit")]
            for hit in hits:
                assert isinstance(hit, Hit)

    async def test_search_hit_has_positive_score(self, worktree: Path) -> None:
        """Matched hits should have a positive score."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.search("Quit")]
            for hit in hits:
                assert hit.score > 0

    async def test_search_no_match_returns_empty(self, worktree: Path) -> None:
        """search() with a non-matching query should yield no results."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.search("xyznonexistent999")]
            assert len(hits) == 0

    async def test_search_hit_help_text(self, worktree: Path) -> None:
        """Search hits should have help text with the hotkey."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.search("Quit")]
            for hit in hits:
                assert hit.help is not None
                assert "Hotkey:" in hit.help

    async def test_search_hit_command_is_callable(self, worktree: Path) -> None:
        """Search hit commands should be callable."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = DiscoveryCommandProvider(app.screen, None)  # type: ignore[arg-type]
            hits = [hit async for hit in provider.search("Diff")]
            assert len(hits) >= 1
            for hit in hits:
                assert callable(hit.command)
