import json

import pytest

from textadventure.engine import Game
from textadventure.mapview import DIRS, layout, render
from textadventure.session import Session
from textadventure.world import World
from test_engine import WORLD

OPEN_DOOR = ("nimm laterne", "gehe norden", "gehe unten", "nimm schlüssel", "gehe oben",
             "öffne eichentür")


def new_game() -> Game:
    return Game(World.load(WORLD))


def world_file(tmp_path, mutate):
    raw = json.loads(WORLD.read_text(encoding="utf-8"))
    mutate(raw)
    p = tmp_path / "w.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


def room(name):
    return {"name": name, "description": name, "exits": {}, "items": []}


# --- Layout ---------------------------------------------------------------------

def test_layout_example_world():
    assert layout(World.load(WORLD)) == {
        "hof": (0, 0, 0), "torhaus": (0, -1, 0), "keller": (0, -1, -1),
        "wachstube": (1, -1, 0), "turmzimmer": (1, -1, 1)}


def test_layout_is_deterministic_and_complete():
    w = World.load(WORLD)
    assert layout(w) == layout(w)
    assert set(layout(w)) == set(w.rooms)


def test_layout_conflict_two_rooms_same_cell(tmp_path):
    def m(raw):
        raw["rooms"]["extra"] = room("Extra")
        raw["rooms"]["hof"]["exits"]["osten"] = "extra"
        raw["rooms"]["extra"]["map"] = {"pos": [0, 0, 0]}   # liegt auf dem Hof
    with pytest.raises(ValueError, match="beide auf"):
        layout(World.load(world_file(tmp_path, m)))


def test_layout_conflict_via_game(tmp_path):
    def m(raw):
        raw["rooms"]["extra"] = room("Extra")
        raw["rooms"]["extra"]["map"] = {"pos": [0, 0, 0]}
    with pytest.raises(ValueError, match="beide auf"):
        Game(World.load(world_file(tmp_path, m)))


def test_layout_conflict_two_auto_rooms_same_cell(tmp_path):
    def m(raw):
        # a und b werden beide per BFS auf (1, 0, 0) gelegt
        raw["rooms"]["a"] = room("A")
        raw["rooms"]["b"] = room("B")
        raw["rooms"]["hof"]["exits"]["osten"] = "a"
        raw["rooms"]["torhaus"]["exits"]["süden"] = "hof"
        raw["rooms"]["a"]["exits"]["norden"] = "b"     # b bei (1,-1,0) = wachstube
    with pytest.raises(ValueError, match="beide auf"):
        layout(World.load(world_file(tmp_path, m)))


def test_layout_contradicting_path(tmp_path):
    def m(raw):
        # Hof -> norden -> Torhaus; zusätzlich Hof -> osten -> Torhaus ist widersprüchlich
        raw["rooms"]["hof"]["exits"]["osten"] = "torhaus"
    with pytest.raises(ValueError, match="passt nicht"):
        layout(World.load(world_file(tmp_path, m)))


def test_layout_unreachable_room_without_pos(tmp_path):
    def m(raw):
        raw["rooms"]["insel"] = room("Insel")
    with pytest.raises(ValueError, match="nicht erreichbar"):
        layout(World.load(world_file(tmp_path, m)))


def test_layout_unreachable_room_with_pos_ok(tmp_path):
    def m(raw):
        raw["rooms"]["insel"] = room("Insel")
        raw["rooms"]["insel"]["map"] = {"pos": [5, 5, 0]}
    pos = layout(World.load(world_file(tmp_path, m)))
    assert pos["insel"] == (5, 5, 0)


def test_manual_position_loaded_as_tuple(tmp_path):
    def m(raw):
        raw["rooms"]["insel"] = room("Insel")
        raw["rooms"]["insel"]["map"] = {"pos": [5, 5, 2]}
    w = World.load(world_file(tmp_path, m))
    assert w.rooms["insel"].pos == (5, 5, 2)
    assert w.rooms["hof"].pos is None


def test_manual_start_position_shifts_layout(tmp_path):
    def m(raw):
        raw["rooms"]["hof"]["map"] = {"pos": [3, 4, 0]}
    pos = layout(World.load(world_file(tmp_path, m)))
    assert pos["hof"] == (3, 4, 0)
    assert pos["torhaus"] == (3, 3, 0)


def test_manual_position_for_one_way_room(tmp_path):
    # Raum ohne Rückweg (z. B. Portal) darf per manueller Position abseits der Richtungslogik liegen
    def m(raw):
        raw["rooms"]["portal"] = room("Portal")
        raw["rooms"]["portal"]["map"] = {"pos": [9, 9, 1]}
        raw["rooms"]["hof"]["exits"]["osten"] = "portal"
    pos = layout(World.load(world_file(tmp_path, m)))
    assert pos["portal"] == (9, 9, 1)
    assert pos["hof"] == (0, 0, 0)


def test_dirs_are_unit_steps():
    for dx, dy, dz in DIRS.values():
        assert abs(dx) + abs(dy) + abs(dz) == 1


# --- Rendering ------------------------------------------------------------------

def test_render_start():
    g = new_game()
    assert g.map_lines() == [
        "Ebene 0",
        "[?]",
        " |",
        "[@]",
    ]


def test_render_after_torhaus():
    g = new_game()
    g.handle("gehe norden")
    assert g.map_lines() == [
        "Ebene 0",
        "[@]+[?]",
        " |",
        "[ ]",
        "Treppe: unten",
    ]


def test_render_door_open():
    g = new_game()
    for c in OPEN_DOOR:
        g.handle(c)
    assert g.map_lines() == [
        "Ebene 0",
        "[@]-[?]",
        " |",
        "[ ]",
        "Treppe: unten",
    ]


def test_render_in_wachstube():
    g = new_game()
    for c in OPEN_DOOR:
        g.handle(c)
    g.handle("gehe osten")
    assert g.map_lines() == [
        "Ebene 0",
        "[ ]-[@]",
        " |",
        "[ ]",
        "Treppe: oben",
    ]


def test_render_other_level_cellar():
    g = new_game()
    g.handle("gehe norden")
    g.handle("gehe unten")
    assert g.map_lines() == ["Ebene -1", "[@]", "Treppe: oben"]


def test_render_tower_level():
    g = new_game()
    for c in OPEN_DOOR:
        g.handle(c)
    g.handle("gehe osten")
    g.handle("gehe oben")
    assert g.map_lines() == ["Ebene 1", "[@]", "Treppe: unten"]


def test_render_explicit_floor_shows_known_room_only():
    g = new_game()
    for c in OPEN_DOOR:
        g.handle(c)
    g.handle("gehe osten")
    lines = render(g.world, g.layout, g.state.visited, g.location, g.state.open_doors, floor=1)
    assert lines[:2] == ["Ebene 1", "[?]"]


def test_render_empty_floor():
    g = new_game()
    lines = render(g.world, g.layout, g.state.visited, g.location, g.state.open_doors, floor=7)
    assert lines == ["Ebene 7: (nichts bekannt)"]


def test_closed_door_shown_from_both_sides_only_when_known():
    g = new_game()
    g.handle("gehe norden")
    assert "+" in g.map_lines()[1]
    g.state.open_doors.add("eichentür")
    assert "+" not in "".join(g.map_lines())


def test_render_never_shows_unvisited_without_known_connection():
    g = new_game()
    g.handle("gehe norden")
    w = g.world
    shown = [ln for ln in g.map_lines()]
    # Genau 3 Zellen auf Ebene 0: hof, torhaus, wachstube(?). Kein Turmzimmer/Keller.
    assert sum(ln.count("[") for ln in shown) == 3
    # Allgemein: jede gezeigte Zelle ist besucht oder Nachbar eines besuchten Raums
    for floor in (-1, 0, 1):
        lines = render(w, g.layout, g.state.visited, g.location, g.state.open_doors, floor=floor)
        cells = sum(ln.count("[") for ln in lines)
        known = set(g.state.visited) | {e.to for r in g.state.visited for e in w.rooms[r].exits.values()}
        assert cells == sum(1 for r in known if g.layout[r][2] == floor)


def test_render_hides_distant_rooms_at_start():
    g = new_game()
    text = "\n".join(g.map_lines())
    assert text.count("[") == 2           # nur Hof und Torhaus (als ?)


def test_all_map_chars_ascii_throughout_playthrough():
    g = new_game()
    steps = OPEN_DOOR + ("gehe osten", "gehe oben", "gehe unten", "gehe westen", "gehe unten")
    for c in ("",) + steps:
        if c:
            g.handle(c)
        for fl in (-1, 0, 1, None):
            lines = render(g.world, g.layout, g.state.visited, g.location, g.state.open_doors, fl)
            assert all(ln.isascii() for ln in lines), lines
    assert g.handle("karte").isascii()


def test_verb_karte_matches_map_lines_and_is_free():
    g = new_game()
    g.handle("gehe norden")
    turns = g.state.turns
    assert g.handle("karte") == "\n".join(g.map_lines())
    assert g.state.turns == turns


def test_session_map_lines(tmp_path):
    s = Session(WORLD, store=None)
    assert s.map_lines() == []
    s.new_game()
    assert s.map_lines() == new_game().map_lines()


def test_map_survives_load(tmp_path):
    from textadventure.saves import SaveStore
    store = SaveStore(tmp_path / "st")
    s = Session(WORLD, store=store)
    s.new_game()
    s.submit("gehe norden")
    s.submit("speichere k")
    before = s.map_lines()
    s2 = Session(WORLD, store=store)
    s2.load("k")
    assert s2.map_lines() == before
