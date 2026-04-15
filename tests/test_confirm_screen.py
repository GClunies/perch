"""Tests for the confirmation modal screen."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from perch.widgets.confirm_screen import ConfirmScreen


class TestConfirmScreen:
    """Tests for ConfirmScreen yes/no modal."""

    async def test_y_confirms(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        (tmp_path / "file.py").write_text("x")
        results: list[bool] = []
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.push_screen(
                    ConfirmScreen("Delete?"), lambda r: results.append(r)
                )
                await pilot.pause()
                assert isinstance(pilot.app.screen, ConfirmScreen)
                await pilot.press("y")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, ConfirmScreen)
                assert results == [True]

    async def test_n_cancels(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        (tmp_path / "file.py").write_text("x")
        results: list[bool] = []
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.push_screen(
                    ConfirmScreen("Delete?"), lambda r: results.append(r)
                )
                await pilot.pause()
                await pilot.press("n")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, ConfirmScreen)
                assert results == [False]

    async def test_escape_cancels(self, tmp_path: Path) -> None:
        from perch.app import PerchApp

        (tmp_path / "file.py").write_text("x")
        results: list[bool] = []
        p1, p2, p3, p4 = _service_patches()
        with p1, p2, p3, p4:
            app = PerchApp(tmp_path)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pilot.app.push_screen(
                    ConfirmScreen("Delete?"), lambda r: results.append(r)
                )
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(pilot.app.screen, ConfirmScreen)
                assert results == [False]


def _service_patches():
    return (
        patch(
            "perch.services.git.get_status",
            return_value=__import__(
                "perch.models", fromlist=["GitStatusData"]
            ).GitStatusData(),
        ),
        patch("perch.services.git.get_log", return_value=[]),
        patch("perch.services.github.get_pr_context", return_value=None),
        patch("perch.services.github.get_checks", return_value=[]),
    )
