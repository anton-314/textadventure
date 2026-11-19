import dataclasses
from pathlib import Path

from textadventure.engine import Game
from textadventure.parser import parse
from textadventure.world import World

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"


def plain_world() -> World:
    """Weltdaten ohne Erfolge: diese Tests prüfen Engine/Events, nicht die Erfolge."""
    return dataclasses.replace(World.load(WORLD), achievements=())


def new_game() -> Game:
    return Game(plain_world())


def at_torhaus(with_key: bool = False) -> Game:
    g = new_game()
    g.handle("gehe norden")
    if with_key:
        g.handle("gehe unten")
        g.handle("nimm schlüssel")
        g.handle("gehe oben")
    assert g.location == "torhaus"
    return g


def test_locked_door_blocks_movement():
    g = at_torhaus()
    out = g.handle("gehe osten")
    assert g.location == "torhaus"
    assert out == g.world.doors["eichentür"].locked_text


def test_open_without_key_fails():
    g = at_torhaus()
    out = g.handle("öffne eichentür")
    assert "Schlüssel" in out
    assert g.open_doors == set()
    g.handle("gehe osten")
    assert g.location == "torhaus"


def test_open_with_key_then_go():
    g = at_torhaus(with_key=True)
    out = g.handle("öffne eichentür")
    assert out == g.world.doors["eichentür"].open_text
    assert "eichentür" in g.open_doors
    g.handle("gehe osten")
    assert g.location == "wachstube"


def test_open_twice():
    g = at_torhaus(with_key=True)
    g.handle("öffne eichentür")
    assert "schon offen" in g.handle("öffne eichentür")


def test_return_west_and_door_open_from_both_sides():
    g = at_torhaus(with_key=True)
    g.handle("öffne eichentür")
    g.handle("gehe osten")
    assert "(verschlossen)" not in g.handle("schau")
    g.handle("gehe westen")
    assert g.location == "torhaus"
    g.handle("gehe osten")
    assert g.location == "wachstube"


def test_open_from_other_side_with_key():
    # Tür ist dieselbe von beiden Seiten: Öffnen im Torhaus genügt, Zustand ist geteilt
    g = at_torhaus(with_key=True)
    g.handle("öffne eichentür")
    g.handle("gehe osten")
    assert "schon offen" in g.handle("öffne eichentür")


def test_open_mit_schluessel():
    g = at_torhaus(with_key=True)
    g.handle("öffne eichentür mit schlüssel")
    assert "eichentür" in g.open_doors
    g.handle("gehe osten")
    assert g.location == "wachstube"


def test_open_mit_schluessel_without_key():
    g = at_torhaus()
    g.handle("öffne eichentür mit schlüssel")
    assert g.open_doors == set()


def test_parser_open_with_key():
    assert parse("öffne eichentür mit schlüssel") == ("open", "eichentür")
    assert parse("öffne die eichentür") == ("open", "eichentür")
    assert parse("öffne") == ("open", "")


def test_open_without_object_or_unknown():
    g = at_torhaus(with_key=True)
    assert "nicht öffnen" in g.handle("öffne")
    assert "nicht öffnen" in g.handle("öffne fenster")
    assert g.open_doors == set()


def test_open_door_not_in_this_room():
    g = new_game()
    assert "nicht öffnen" in g.handle("öffne eichentür")


def test_new_game_has_door_closed_again():
    g1 = at_torhaus(with_key=True)
    g1.handle("öffne eichentür")
    g2 = at_torhaus()
    assert g2.open_doors == set()
    g2.handle("gehe osten")
    assert g2.location == "torhaus"


def test_new_game_shares_world_but_not_state():
    world = World.load(WORLD)
    g1, g2 = Game(world), Game(world)
    g1.open_doors.add("eichentür")
    assert g2.open_doors == set()


def test_examine_door():
    g = at_torhaus()
    assert g.handle("untersuche eichentür") == g.world.doors["eichentür"].description


def test_examine_door_short_name():
    # Aufgabenstellung: 'untersuche tür'
    g = at_torhaus()
    assert g.handle("untersuche tür") == g.world.doors["eichentür"].description


def test_examine_door_elsewhere():
    g = new_game()
    assert "nicht" in g.handle("untersuche eichentür")


def test_exit_list_shows_locked():
    g = at_torhaus()
    out = g.describe()
    assert "osten (verschlossen)" in out
    assert "süden," in out or "süden" in out
    assert "süden (verschlossen)" not in out
    g2 = at_torhaus(with_key=True)
    g2.handle("öffne eichentür")
    assert "(verschlossen)" not in g2.describe()


def test_exit_list_locked_from_wachstube_side():
    g = at_torhaus(with_key=True)
    g.handle("öffne eichentür")
    g.handle("gehe osten")
    g.open_doors.clear()
    assert "westen (verschlossen)" in g.describe()


def test_playthrough_to_siegelring():
    g = new_game()
    for cmd in ["gehe norden", "gehe unten", "nimm schlüssel", "gehe oben",
                "öffne eichentür", "gehe osten", "nimm wachbuch", "gehe oben",
                "nimm siegelring"]:
        g.handle(cmd)
    assert g.location == "turmzimmer"
    assert "siegelring" in g.inventory
    assert "schlüssel" in g.inventory
    assert g.room_items["turmzimmer"] == []
