"""Tests for the DiscoveryCommandProvider."""

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
    assert "shrink_left_pane" in actions
    assert "grow_left_pane" in actions
    assert "focus_next_pane" in actions


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
