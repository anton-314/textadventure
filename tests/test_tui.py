import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.widgets import Input, OptionList  # noqa: E402

from textadventure.tui import AdventureApp, MenuScreen  # noqa: E402

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"


def run(coro):
    return asyncio.run(coro)


def test_menu_then_new_game_and_commands():
    async def scenario():
        app = AdventureApp(WORLD)
        async with app.run_test(size=(110, 32)) as pilot:
            assert isinstance(app.screen, MenuScreen)       # Startmenü zuerst
            assert app.game is None
            await pilot.press("enter")                      # "Neues Spiel" ist vorausgewählt
            await pilot.pause()
            assert app.game is not None and app.game.location == "hof"
            cmd = app.query_one("#cmd", Input)
            assert not cmd.disabled
            for c in "nimm laterne":
                await pilot.press(c if c != " " else "space")
            await pilot.press("enter")
            await pilot.pause()
            assert app.game.inventory == ["laterne"]
            assert "Laterne" in str(app.query_one("#inv").render())
    run(scenario())


def test_toggle_dock_side_theme_and_menu_resume():
    async def scenario():
        app = AdventureApp(WORLD)
        async with app.run_test(size=(110, 32)) as pilot:
            await pilot.press("enter")                      # Neues Spiel
            await pilot.pause()
            await pilot.press("f3")
            assert app.query_one("#cmd").has_class("top")
            await pilot.press("f2")
            assert app.query_one("#side").has_class("hidden")
            await pilot.press("f4")
            assert app.has_class("amber")
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, MenuScreen)
            assert app.screen.query_one(OptionList).option_count == 3  # Weiterspielen, Neues Spiel, Beenden
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, MenuScreen)
            assert app.game is not None
    run(scenario())


def test_quit_disables_input():
    async def scenario():
        app = AdventureApp(WORLD)
        async with app.run_test(size=(110, 32)) as pilot:
            await pilot.press("enter")
            await pilot.pause()
            app.submit("ende")
            await pilot.pause()
            assert app.query_one("#cmd", Input).disabled
    run(scenario())


def test_wasd_navigates_menu():
    async def scenario():
        app = AdventureApp(WORLD)
        async with app.run_test(size=(110, 32)) as pilot:
            menu = app.screen.query_one(OptionList)
            assert menu.highlighted == 0
            await pilot.press("s")
            assert menu.highlighted == 1                    # Beenden
            await pilot.press("w")
            assert menu.highlighted == 0
            await pilot.press("d")                          # wählt "Neues Spiel"
            await pilot.pause()
            assert app.game is not None
            # im Spiel müssen WASD normale Buchstaben bleiben
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("a")                          # zurück ins Spiel
            await pilot.pause()
            for c in "was":
                await pilot.press(c)
            assert app.query_one("#cmd", Input).value == "was"
    run(scenario())


def test_cheatsheet_opens_with_f1_and_closes():
    from textadventure.tui import CheatSheetScreen

    async def scenario():
        app = AdventureApp(WORLD)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.press("enter")                      # Neues Spiel
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            assert isinstance(app.screen, CheatSheetScreen)
            text = str(app.screen.query_one("#sheet-text").render())
            assert "SPIELANLEITUNG" in text and "gucke dich um" in text and "F5" in text
            await pilot.press("f1")                         # F1 schließt wieder
            await pilot.pause()
            assert not isinstance(app.screen, CheatSheetScreen)
            await pilot.press("f1")
            await pilot.press("escape")                     # Esc schließt ebenfalls
            await pilot.pause()
            assert not isinstance(app.screen, CheatSheetScreen)
    run(scenario())
