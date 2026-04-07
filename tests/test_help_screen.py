"""Tests for the HelpScreen modal and BINDING_REGISTRY."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.binding import Binding

from perch.app import PerchApp
from perch.widgets.help_screen import HelpScreen, _build_help_content


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    (tmp_path / "hello.py").write_text("print('hello')\n")
    return tmp_path


class TestBuildHelpContent:
    """Tests for the pure _build_help_content() function."""

    def test_returns_string(self) -> None:
        """_build_help_content should return a string."""
        registry: dict[str, list[Binding]] = {
            "Global": [Binding("q", "quit", "Quit", key_display="q")],
        }
        result = _build_help_content(registry)
        assert isinstance(result, str)

    def test_includes_section_header(self) -> None:
        """Output should contain the section name."""
        registry: dict[str, list[Binding]] = {
            "Global": [Binding("q", "quit", "Quit", key_display="q")],
        }
        result = _build_help_content(registry)
        assert "Global" in result

    def test_includes_binding_key_display(self) -> None:
        """Output should contain the key_display for each binding."""
        registry: dict[str, list[Binding]] = {
            "Global": [Binding("q", "quit", "Quit", key_display="q")],
        }
        result = _build_help_content(registry)
        assert "q" in result

    def test_includes_binding_description(self) -> None:
        """Output should contain the description for each binding."""
        registry: dict[str, list[Binding]] = {
            "Global": [Binding("q", "quit", "Quit", key_display="q")],
        }
        result = _build_help_content(registry)
        assert "Quit" in result

    def test_multiple_sections(self) -> None:
        """Output should contain all section names."""
        registry: dict[str, list[Binding]] = {
            "Section A": [Binding("a", "act_a", "Alpha")],
            "Section B": [Binding("b", "act_b", "Beta")],
        }
        result = _build_help_content(registry)
        assert "Section A" in result
        assert "Section B" in result

    def test_empty_registry(self) -> None:
        """Empty registry should produce an empty or minimal string."""
        result = _build_help_content({})
        assert isinstance(result, str)


class TestBindingRegistry:
    """Tests for PerchApp.BINDING_REGISTRY."""

    def test_registry_exists(self) -> None:
        """PerchApp should have a BINDING_REGISTRY class variable."""
        assert hasattr(PerchApp, "BINDING_REGISTRY")

    def test_registry_is_dict(self) -> None:
        """BINDING_REGISTRY should be a dict."""
        assert isinstance(PerchApp.BINDING_REGISTRY, dict)

    def test_registry_keys_match_expected_panels(self) -> None:
        """BINDING_REGISTRY should have the expected section names."""
        expected = {"Global", "File Tree", "Viewer", "Git", "GitHub"}
        assert set(PerchApp.BINDING_REGISTRY.keys()) == expected

    def test_registry_values_are_binding_lists(self) -> None:
        """Each registry value should be a list of Binding instances."""
        for section, bindings in PerchApp.BINDING_REGISTRY.items():
            assert isinstance(bindings, list), f"{section} is not a list"
            for b in bindings:
                assert isinstance(b, Binding), f"{section} contains non-Binding: {b!r}"

    def test_global_section_has_quit(self) -> None:
        """Global section should include a 'quit' action."""
        actions = {b.action for b in PerchApp.BINDING_REGISTRY["Global"]}
        assert "quit" in actions

    def test_global_section_has_help(self) -> None:
        """Global section should include a 'show_help' action."""
        actions = {b.action for b in PerchApp.BINDING_REGISTRY["Global"]}
        assert "show_help" in actions


class TestHelpScreenModal:
    """Tests for pushing/dismissing the HelpScreen."""

    async def test_question_mark_opens_help_screen(self, worktree: Path) -> None:
        """Pressing ? should open the HelpScreen modal."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

    async def test_escape_closes_help_screen(self, worktree: Path) -> None:
        """Pressing Escape on the HelpScreen should dismiss it."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)

    async def test_help_screen_displays_all_sections(self, worktree: Path) -> None:
        """The HelpScreen should display content for all BINDING_REGISTRY sections."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("question_mark")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HelpScreen)
            # The screen should contain a Static with all section names
            from textual.widgets import Static

            statics = screen.query(Static)
            all_text = " ".join(s.content for s in statics)
            for section in PerchApp.BINDING_REGISTRY:
                assert section in all_text, (
                    f"Section {section!r} not found in help screen"
                )

    async def test_ctrl_shift_p_opens_command_palette(self, worktree: Path) -> None:
        """Ctrl+Shift+P should still open the command palette, not the help screen."""
        app = PerchApp(worktree)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+p")
            await pilot.pause()
            # Should NOT be a HelpScreen
            assert not isinstance(app.screen, HelpScreen)


class TestActionShowHelp:
    """Tests for PerchApp.action_show_help."""

    def test_action_show_help_method_exists(self) -> None:
        """PerchApp should have an action_show_help method."""
        assert hasattr(PerchApp, "action_show_help")
        assert callable(getattr(PerchApp, "action_show_help"))
