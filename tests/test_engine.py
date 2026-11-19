from pathlib import Path

from textadventure.engine import Game
from textadventure.world import World

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"


def new_game() -> Game:
    return Game(World.load(WORLD))


def test_start_room():
    assert new_game().location == "hof"


def test_move_and_blocked():
    g = new_game()
    g.handle("gehe norden")
    assert g.location == "torhaus"
    assert "nicht" in g.handle("gehe osten")


def test_take_and_drop():
    g = new_game()
    g.handle("nimm laterne")
    assert g.inventory == ["laterne"]
    g.handle("lasse laterne")
    assert g.inventory == []


def test_quit():
    g = new_game()
    g.handle("ende")
    assert not g.running
