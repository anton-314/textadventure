import json
from pathlib import Path

import pytest

from textadventure.world import World

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"
OPPOSITE = {"norden": "süden", "süden": "norden", "osten": "westen",
            "westen": "osten", "oben": "unten", "unten": "oben"}


@pytest.fixture(scope="module")
def world() -> World:
    return World.load(WORLD)


def test_start_exists(world):
    assert world.start in world.rooms


def test_exits_point_to_existing_rooms(world):
    for room in world.rooms.values():
        for d, ex in room.exits.items():
            assert ex.to in world.rooms, (room.id, d)


def test_exit_directions_known(world):
    for room in world.rooms.values():
        assert set(room.exits) <= set(OPPOSITE), room.id


def test_return_paths_exist(world):
    for room in world.rooms.values():
        for d, ex in room.exits.items():
            back = world.rooms[ex.to].exits.get(OPPOSITE[d])
            assert back is not None, f"{room.id} -{d}-> {ex.to}: kein Rückweg"
            assert back.to == room.id, f"{room.id} -{d}-> {ex.to}: Rückweg führt zu {back.to}"
            assert back.door == ex.door, f"{room.id} <-> {ex.to}: Türen passen nicht"


def test_room_items_defined_and_unique(world):
    seen = []
    for room in world.rooms.values():
        for iid in room.items:
            assert iid in world.items
            seen.append(iid)
    assert len(seen) == len(set(seen)), "Item liegt in mehreren Räumen"


def test_doors_reference_valid_keys_and_are_used(world):
    used = {ex.door for r in world.rooms.values() for ex in r.exits.values() if ex.door}
    for did, door in world.doors.items():
        assert door.key in world.items, did
        assert did in used, f"Tür {did} wird nirgends verwendet"
    assert used <= set(world.doors)


def test_key_reachable_without_passing_its_door(world):
    for door in world.doors.values():
        # Erreichbare Räume vom Start, ohne durch diese Tür zu gehen
        seen, todo = {world.start}, [world.start]
        while todo:
            r = world.rooms[todo.pop()]
            for ex in r.exits.values():
                if ex.door == door.id or ex.to in seen:
                    continue
                seen.add(ex.to)
                todo.append(ex.to)
        assert any(door.key in world.rooms[r].items for r in seen), door.id


def test_all_rooms_reachable(world):
    seen, todo = {world.start}, [world.start]
    while todo:
        for ex in world.rooms[todo.pop()].exits.values():
            if ex.to not in seen:
                seen.add(ex.to)
                todo.append(ex.to)
    assert seen == set(world.rooms)


def test_siegelring_in_turmzimmer(world):
    assert "siegelring" in world.rooms["turmzimmer"].items


# --- kaputte Daten ---

def _load_broken(tmp_path, mutate):
    raw = json.loads(WORLD.read_text(encoding="utf-8"))
    mutate(raw)
    p = tmp_path / "w.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return World.load(p)


def test_load_valid_copy(tmp_path):
    assert _load_broken(tmp_path, lambda r: None).start == "hof"


def test_bad_start(tmp_path):
    with pytest.raises(ValueError, match="Startraum"):
        _load_broken(tmp_path, lambda r: r.update(start="nirgendwo"))


def test_bad_exit_target(tmp_path):
    with pytest.raises(ValueError, match="unbekanntem Raum"):
        _load_broken(tmp_path, lambda r: r["rooms"]["hof"]["exits"].update(osten="gibtsnicht"))


def test_bad_exit_target_in_door_exit(tmp_path):
    def m(r):
        r["rooms"]["torhaus"]["exits"]["osten"]["to"] = "gibtsnicht"
    with pytest.raises(ValueError, match="unbekanntem Raum"):
        _load_broken(tmp_path, m)


def test_unknown_door(tmp_path):
    def m(r):
        r["rooms"]["torhaus"]["exits"]["osten"]["door"] = "gibtsnicht"
    with pytest.raises(ValueError, match="unbekannte Tür"):
        _load_broken(tmp_path, m)


def test_unknown_key(tmp_path):
    def m(r):
        r["doors"]["eichentür"]["key"] = "gibtsnicht"
    with pytest.raises(ValueError, match="Schlüssel"):
        _load_broken(tmp_path, m)


def test_unknown_room_item(tmp_path):
    with pytest.raises(ValueError, match="unbekanntes Item"):
        _load_broken(tmp_path, lambda r: r["rooms"]["hof"]["items"].append("gibtsnicht"))


def _write_world(tmp_path, item):
    import json
    data = {"start": "a", "rooms": {"a": {"name": "A", "description": "d"}}, "items": {"x": item}}
    p = tmp_path / "w.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_item_defaults(tmp_path):
    w = World.load(_write_world(tmp_path, {"name": "X", "description": "d"}))
    assert (w.items["x"].kind, w.items["x"].stackable, w.items["x"].props) == ("misc", False, {})


def test_item_unknown_kind(tmp_path):
    with pytest.raises(ValueError, match="Art"):
        World.load(_write_world(tmp_path, {"name": "X", "description": "d", "kind": "zauberstab"}))


def test_item_stackable_not_takeable(tmp_path):
    with pytest.raises(ValueError, match="stapelbar"):
        World.load(_write_world(tmp_path, {"name": "X", "description": "d",
                                           "stackable": True, "takeable": False}))
