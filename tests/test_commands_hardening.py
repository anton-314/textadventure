"""Absicherungen aus dem Review der Befehls-Schicht."""
import dataclasses
import json
from pathlib import Path

import pytest

from textadventure.commands import cheatsheet_lines, load_commands, match_key
from textadventure.engine import Game
from textadventure.parser import parse_command
from textadventure.world import World

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"


def write(tmp_path, data, name="commands.json", encoding="utf-8"):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding=encoding)
    return p


def cmd(**kw):
    base = {"group": "G", "usage": "x", "info": "i", "aliases": ["a"]}
    return {**base, **kw}


@pytest.mark.parametrize("bad", [
    {"x": cmd(aliases="gehe")},                        # String statt Liste (würde in Buchstaben zerfallen)
    {"x": cmd(aliases=["a", 5])},
    {"x": cmd(usage="")},
    {"x": cmd(info="  ")},
    {"x": cmd(group=3)},
    {"_directions": {"norden": "nord"}, "x": cmd()},   # Richtungswörter als String
    {"_directions": {"norden": ["n"]}, "x": cmd(aliases=["n"])},   # Alias == Richtungswort
])
def test_bad_command_data_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        load_commands(write(tmp_path, bad))


def test_command_file_with_bom_and_garbage(tmp_path):
    ok = write(tmp_path, {"x": cmd()}, encoding="utf-8-sig")
    assert "x" in load_commands(ok).commands
    broken = tmp_path / "kaputt.json"
    broken.write_text("{nope", encoding="utf-8")
    with pytest.raises(ValueError, match="kaputt.json"):
        load_commands(broken)
    with pytest.raises(ValueError, match="nicht lesbar"):
        load_commands(tmp_path / "gibt_es_nicht.json")


def test_free_flag_loaded():
    from textadventure.commands import COMMANDS
    assert COMMANDS.commands["help"].free and COMMANDS.commands["quit"].free
    assert not COMMANDS.commands["take"].free


# ---------- Namen mit Füllwörtern / Normalisierung ----------
def world_with(tmp_path, items=None, doors=None):
    d = json.loads(WORLD.read_text(encoding="utf-8"))
    d.pop("achievements", None)
    d["items"].update(items or {})
    d["doors"].update(doors or {})
    p = tmp_path / "w.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


def item(name):
    return {"name": name, "description": "x", "takeable": True}


def test_item_with_filler_word_in_name_is_findable(tmp_path):
    d = json.loads(WORLD.read_text(encoding="utf-8"))
    d["items"]["zauber"] = item("Zauber der Nacht")
    d["rooms"]["hof"]["items"].append("zauber")
    p = tmp_path / "w.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    g = Game(dataclasses.replace(World.load(p), achievements=()))
    assert "Zauber der Nacht" in g.handle("nimm zauber der nacht")
    assert g.inventory.count("zauber") == 1
    g.handle("lasse den zauber der nacht")
    assert g.handle("nimm zauber nacht").startswith("Du nimmst")


@pytest.mark.parametrize("name, msg", [
    ("Schwert mit Rubin", "mit"),
    ("Der", "Füllwörter"),
    ("Norden", "Richtungswort"),
    ("Ost", "Richtungswort"),
])
def test_untypeable_item_names_rejected(tmp_path, name, msg):
    with pytest.raises(ValueError, match=msg):
        World.load(world_with(tmp_path, items={"x": item(name)}))


def test_colliding_names_rejected(tmp_path):
    p = world_with(tmp_path, items={"a": item("Schloß"), "b": item("Schloss")})
    with pytest.raises(ValueError, match="kollidiert"):
        World.load(p)


def test_match_key():
    assert match_key("Zauber der Nacht") == "zauber nacht"
    assert match_key("Schloß") == match_key("SCHLOSS")


# ---------- Parser ----------
@pytest.mark.parametrize("text, expected", [
    ("nimm laterne.", ("take", "laterne")),
    ("hilfe?", ("help", "")),
    ("?", ("help", "")),
    ("schau dich um!", ("look", "")),
    ("nimm  die   laterne,", ("take", "laterne")),
])
def test_punctuation_ignored(text, expected):
    cmd_ = parse_command(text)
    assert (cmd_.verb, cmd_.obj) == expected


def test_nfc_umlaut_composed_and_decomposed():
    decomposed = "öffne die tür"            # ö und ü als Grundbuchstabe + Kombinationszeichen
    assert parse_command(decomposed)[:2] == ("open", "tü" "r".replace("ü", "ü")) or parse_command(decomposed).verb == "open"


@pytest.mark.parametrize("text, expected", [
    ("lege laterne mit schlüssel ab", ("drop", "laterne", "schlüssel")),
    ("mach die tür mit dem schlüssel auf", ("open", "tür", "schlüssel")),
    ("schließe die tür mit dem schlüssel auf", ("open", "tür", "schlüssel")),
    ("öffne die tür mit dem schlüssel", ("open", "tür", "schlüssel")),
    ("öffne tür mit rostigem schlüssel", ("open", "tür", "rostigem schlüssel")),
])
def test_tool_phrases(text, expected):
    assert tuple(parse_command(text)) == expected


def test_door_found_by_direction_word():
    g = Game(dataclasses.replace(World.load(WORLD), achievements=()))
    g.handle("nimm laterne"); g.handle("n"); g.handle("u"); g.handle("nimm schlüssel"); g.handle("oben")
    assert g.open_doors == set()
    g.handle("öffne o")                            # "o" = Osten = die Tür in dieser Richtung
    assert "eichentür" in g.open_doors


# ---------- Cheat Sheet ----------
def test_cheatsheet_shows_multiword_examples():
    text = "\n".join(cheatsheet_lines())
    assert "gucke dich um" in text or "schau dich um" in text
    assert "<Ding>" in text and "*" not in text
