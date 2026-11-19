import json
from pathlib import Path

import pytest

from textadventure.commands import (COMMANDS, DEFAULT_COMMANDS, FILLER, cheatsheet_lines,
                                    load_commands, normalize)
from textadventure.engine import Game
from textadventure.verbs import VERBS
from textadventure.world import World

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"


def new_game() -> Game:
    return Game(World.load(WORLD))


def raw():
    return json.loads(DEFAULT_COMMANDS.read_text(encoding="utf-8"))


# (2) End-to-end
def test_e2e_look_around():
    g = new_game()
    out = g.handle("gucke dich um")
    assert g.location == "hof"
    assert out == g.handle("umgucken") == g.handle("wo bin ich")


def test_e2e_look_at_door_and_item():
    g = new_game()
    assert "laterne" in g.handle("sieh dir die laterne an").lower()
    g.handle("nimm laterne")
    g.handle("gehe norden")
    assert g.location == "torhaus"
    out = g.handle("sieh dir die eichentuer an")
    assert out == g.world.doors["eichentür"].description
    assert out == g.handle("untersuche eichentür")


def test_e2e_open_door_with_umlaut_input():
    g = new_game()
    g.handle("nimm laterne")
    g.handle("laufe nach norden")
    g.handle("runter")
    assert g.location == "keller"
    g.handle("nimm schluessel")
    assert "schlüssel" in g.inventory
    g.handle("hoch")
    assert g.location == "torhaus"
    g.handle("oeffne die tuer mit dem schluessel")
    assert "eichentür" in g.open_doors
    g.handle("gehe osten")
    assert g.location == "wachstube"


def test_e2e_open_with_mach_auf():
    g = new_game()
    g.handle("gehe norden"); g.handle("gehe unten"); g.handle("nimm schlüssel"); g.handle("gehe oben")
    g.handle("mach die tür mit dem schlüssel auf")
    assert "eichentür" in g.open_doors


def test_e2e_take_drop_synonyms():
    g = new_game()
    g.handle("nimm dir die laterne")
    assert g.inventory == ["laterne"]
    g.handle("lass die laterne fallen")
    assert g.inventory == [] and "laterne" in g.room_items["hof"]
    g.handle("hebe die laterne auf")
    assert g.inventory == ["laterne"]


def test_e2e_umlaut_item_lookup():
    g = new_game()
    g.handle("gehe norden"); g.handle("runter")
    g.handle("nimm Schluessel")
    assert g.inventory == ["schlüssel"]
    assert "schlüssel" in "\n".join([g.handle("sieh dir den schluessel an")]).lower()


def test_e2e_unknown_and_empty():
    g = new_game()
    assert g.handle("blubb")
    g.handle("")
    assert g.location == "hof"


def test_e2e_help_shows_cheatsheet():
    out = new_game().handle("hilfe")
    for c in COMMANDS.commands.values():
        assert c.usage in out


def test_e2e_look_with_object_delegates():
    g = new_game()
    assert g.handle("schau laterne") == g.handle("untersuche laterne")


# (3) Datenintegrität
def test_registry_matches_data():
    assert VERBS.names() == set(COMMANDS.commands)


def test_no_duplicate_aliases_in_json():
    seen = {}
    for name, c in ((n, c) for n, c in raw().items() if n != "_directions"):
        for a in c["aliases"]:
            key = normalize(a)
            assert key not in seen, f"{a!r} in {seen.get(key)} und {name}"
            seen[key] = name


def test_no_filler_in_aliases():
    for c in COMMANDS.commands.values():
        for a in c.aliases:
            assert not FILLER & set(normalize(a).split()), (c.name, a)


def test_every_entry_complete():
    for c in COMMANDS.commands.values():
        assert c.group.strip() and c.usage.strip() and c.info.strip() and c.aliases, c.name


def test_directions_cover_all():
    assert set(COMMANDS.directions.values()) >= {"norden", "süden", "osten", "westen", "oben", "unten"}
    for d in ("norden", "süden", "osten", "westen", "oben", "unten"):
        assert COMMANDS.direction(d) == d


def test_normalize():
    assert normalize("ÖffneSchlüssel Straße Spielstände Äh") == "oeffneschluessel strasse spielstaende aeh"


# (4) load_commands-Fehler
def cmd(**over):
    d = {"group": "G", "usage": "u", "info": "i", "aliases": ["a"]}
    d.update(over)
    return d


def write(tmp_path, data):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_valid_minimal(tmp_path):
    t = load_commands(write(tmp_path, {"x": cmd()}))
    assert t.match(["a"]) == ("x", 1, 1)


@pytest.mark.parametrize("data", [
    {"x": cmd(aliases=["foo"]), "y": cmd(aliases=["foo"])},
    {"x": cmd(aliases=["Foo"]), "y": cmd(aliases=["foo"])},
    {"x": cmd(aliases=["schliesse"]), "y": cmd(aliases=["schließe"])},
    {"x": cmd(aliases=["nimm die"])},
    {"x": cmd(aliases=["mit"])},
    {"x": cmd(aliases=["a * b *"])},
    {"x": cmd(aliases=["*"])},
    {"x": cmd(aliases=[""])},
    {"x": {"group": "G", "usage": "u", "aliases": ["a"]}},
    {"x": {"usage": "u", "info": "i", "aliases": ["a"]}},
    {"x": {"group": "G", "usage": "u", "info": "i"}},
    {"_directions": {"norden": ["n"], "süden": ["n"]}, "x": cmd()},
    {"_directions": {"norden": ["Nord"], "süden": ["nord"]}, "x": cmd()},
])
def test_load_errors(tmp_path, data):
    with pytest.raises(ValueError):
        load_commands(write(tmp_path, data))


# (5) cheatsheet_lines
def test_cheatsheet_contains_groups_and_usages():
    lines = cheatsheet_lines()
    text = "\n".join(lines)
    for c in COMMANDS.commands.values():
        assert c.group.upper() in lines
        assert any(line.strip() == c.usage for line in lines)
        assert c.info in text


def test_cheatsheet_extra_appended():
    lines = cheatsheet_lines(extra=["Taste F1: Hilfe", "Taste F2: Karte"])
    assert lines[-2:] == ["Taste F1: Hilfe", "Taste F2: Karte"]
    assert "Taste F1: Hilfe" not in cheatsheet_lines()


def test_cheatsheet_printable():
    for line in cheatsheet_lines(extra=["x"]):
        assert isinstance(line, str)
        assert line == "" or line.isprintable()
        assert "\n" not in line
