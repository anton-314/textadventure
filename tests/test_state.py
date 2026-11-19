import json

import pytest

from textadventure.engine import Game
from textadventure.state import GameState
from textadventure.world import World
from test_engine import WORLD


@pytest.fixture
def world():
    return World.load(WORLD)


def test_new_state(world):
    s = GameState.new(world)
    assert s.location == "hof"
    assert s.room_items["hof"] == ["laterne"]
    assert s.visited == {"hof"}
    assert s.turns == 0


def test_new_state_does_not_share_world_lists(world):
    s = GameState.new(world)
    s.room_items["hof"].clear()
    assert world.rooms["hof"].items == ["laterne"]


def test_roundtrip_new(world):
    s = GameState.new(world)
    assert GameState.from_dict(s.to_dict(), world) == s


def test_roundtrip_after_playing(world):
    g = Game(world)
    for cmd in ("nimm laterne", "gehe norden", "gehe unten", "nimm schlüssel", "gehe oben",
                "öffne eichentür", "gehe osten", "lasse laterne"):
        g.execute(cmd)
    s = g.state
    assert s.open_doors and s.inventory and s.turns == 8
    assert GameState.from_dict(s.to_dict(), world) == s


def test_roundtrip_survives_json(world):
    g = Game(world)
    g.execute("nimm laterne")
    g.state.flags["x"] = [1, 2]
    g.state.stats["n"] = 3
    g.state.achievements.add("eingelassen")
    d = json.loads(json.dumps(g.state.to_dict()))
    assert GameState.from_dict(d, world) == g.state


def test_to_dict_is_independent_copy(world):
    s = GameState.new(world)
    d = s.to_dict()
    d["inventory"].append("x")
    d["room_items"]["hof"].clear()
    assert s.inventory == [] and s.room_items["hof"] == ["laterne"]


def test_unknown_items_dropped(world):
    d = GameState.new(world).to_dict()
    d["inventory"] = ["laterne", "gibtsnicht"]
    d["room_items"]["hof"] = ["gibtsnicht"]
    s = GameState.from_dict(d, world)
    assert s.inventory == ["laterne"]
    assert s.room_items["hof"] == []


def test_unknown_rooms_and_doors_dropped(world):
    d = GameState.new(world).to_dict()
    d["room_items"]["geisterraum"] = ["laterne"]
    d["visited"] = ["hof", "geisterraum"]
    d["open_doors"] = ["eichentür", "phantomtür"]
    s = GameState.from_dict(d, world)
    assert "geisterraum" not in s.room_items
    assert "geisterraum" not in s.visited
    assert s.open_doors == {"eichentür"}


def test_new_rooms_come_from_world(world):
    d = GameState.new(world).to_dict()
    del d["room_items"]["keller"]
    s = GameState.from_dict(d, world)
    assert s.room_items["keller"] == ["schlüssel"]


def test_unknown_location_raises(world):
    d = GameState.new(world).to_dict()
    d["location"] = "nirgendwo"
    with pytest.raises(ValueError):
        GameState.from_dict(d, world)


def test_missing_location_raises(world):
    d = GameState.new(world).to_dict()
    del d["location"]
    with pytest.raises(ValueError):
        GameState.from_dict(d, world)


def test_location_always_visited(world):
    d = GameState.new(world).to_dict()
    d["location"] = "keller"
    d["visited"] = []
    assert "keller" in GameState.from_dict(d, world).visited


def test_orphan_achievements_are_dropped(world):
    d = Game(world).state.to_dict()
    d["achievements"] = ["lichtbringer", "gibt_es_nicht"]
    d["stats"] = {"ach:gibt_es_nicht": 2, "ach:entdecker": 1, "zug": 3}
    s = GameState.from_dict(d, world)
    assert s.achievements == {"lichtbringer"}
    assert s.stats == {"ach:entdecker": 1, "zug": 3}
