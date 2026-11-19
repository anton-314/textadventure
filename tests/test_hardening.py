import dataclasses
"""Absicherungen aus dem Architektur-Review: kaputte Spielstände, Slots, Event-Limit, Schreibschutz."""
import json
from pathlib import Path

import pytest

from textadventure.engine import MAX_EVENTS_PER_TURN, Game
from textadventure.events import ItemTaken
from textadventure.saves import SaveError, SaveStore
from textadventure.session import Session
from textadventure.world import World

WORLD = Path(__file__).resolve().parents[1] / "src" / "textadventure" / "data" / "world.json"


@pytest.fixture
def world():
    return dataclasses.replace(World.load(WORLD), achievements=())


@pytest.fixture
def store(tmp_path):
    return SaveStore(tmp_path)


def write_slot(store, name, text):
    store.root.mkdir(parents=True, exist_ok=True)
    (store.root / f"{name}.json").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("payload", [
    "[]", "null", '"text"', '{"version": "x"}', '{"version": 1, "state": []}',
    '{"version": 1, "state": {"location": "hof", "stats": {"a": null}}}',
    '{"version": 1, "state": {"location": "hof", "flags": null}}',
    '{"version": 1, "state": {"location": "hof", "room_items": []}}',
])
def test_corrupt_saves_raise_save_error_not_crash(store, world, payload):
    write_slot(store, "kaputt", payload)
    with pytest.raises(SaveError):
        store.load("kaputt", world)


def test_slots_survives_garbage_files(store):
    write_slot(store, "a", "[]")
    write_slot(store, "b", '{"meta": 5, "saved_at": 3}')
    (store.root / "c.json").write_bytes(b"\xff\xfe\x00binary")
    names = [s.slot for s in store.slots()]
    assert "b" in names and "a" not in names and "c" not in names


@pytest.mark.parametrize("name", ["abc\n", "con", "nul", "com1", "lpt9", "../x", "A", ""])
def test_bad_slot_names(store, world, name):
    with pytest.raises(SaveError):
        store.save(name, Game(world).state, world)


def test_unserializable_flags_become_save_error(store, world):
    g = Game(world)
    g.state.flags["x"] = {1, 2}
    with pytest.raises(SaveError):
        store.save("s", g.state, world)
    assert not list(store.root.glob("*")) or not (store.root / "s.json").exists()


def test_no_tmp_files_left_after_save(store, world):
    store.save("s", Game(world).state, world)
    assert [p.name for p in store.root.iterdir()] == ["s.json"]


def test_save_of_other_world_is_rejected(store, world):
    store.save("s", Game(world).state, world, world_id="andere-welt")
    with pytest.raises(SaveError, match="anderen Welt"):
        store.load("s", world)


def test_item_not_duplicated_after_world_change(store, world):
    g = Game(world)
    g.execute("nimm laterne")
    d = g.state.to_dict()
    d["room_items"].pop("hof")              # Save kennt den Raum-Eintrag nicht mehr -> Default aus der Welt
    from textadventure.state import GameState
    s = GameState.from_dict(d, world)
    assert "laterne" in s.inventory and all("laterne" not in v for v in s.room_items.values())


def test_item_props_are_read_only(world):
    item = world.items["laterne"]
    with pytest.raises(TypeError):
        item.props["x"] = 1


def test_runaway_reactor_is_stopped(world):
    class Loop:
        def react(self, ev, game, out):
            return [ItemTaken("laterne")]

    g = Game(world, reactors=(Loop(),))
    res = g.execute("nimm laterne")
    assert len(res.events) <= MAX_EVENTS_PER_TURN + 2
    assert "zu viele" in res.text


def test_follow_up_events_visible_in_result(world):
    class Echo:
        def __init__(self):
            self.done = False

        def react(self, ev, game, out):
            if isinstance(ev, ItemTaken) and not self.done:
                self.done = True
                return [ItemTaken("schlüssel")]
            return []

    res = Game(world, reactors=(Echo(),)).execute("nimm laterne")
    assert [e.item for e in res.events] == ["laterne", "schlüssel"]


def test_new_game_keeps_previous_autosave(tmp_path):
    store = SaveStore(tmp_path)
    s = Session(WORLD, store=store)
    s.new_game()
    s.submit("nimm laterne")                 # Autosave mit Laterne
    s.new_game()                             # neues Spiel
    s.submit("schau")                        # darf auto nicht mehr überschreiben als nötig
    assert "auto-prev" in [i.slot for i in store.slots()]
    assert "laterne" in store.load("auto-prev", s.world).inventory


def test_no_autosave_for_empty_or_unknown_input(tmp_path):
    store = SaveStore(tmp_path)
    s = Session(WORLD, store=store)
    s.new_game()
    for text in ("", "   ", "tanze", "hilfe"):
        s.submit(text)
    assert not (store.root / "auto.json").exists()


def test_autosave_failure_warned_once(tmp_path, monkeypatch):
    s = Session(WORLD, store=SaveStore(tmp_path))
    s.new_game()
    monkeypatch.setattr(s.store, "save", lambda *a, **k: (_ for _ in ()).throw(OSError("voll")))
    first = s.submit("gehe norden").text
    second = s.submit("gehe süden").text
    assert "Autosave fehlgeschlagen" in first and "Autosave fehlgeschlagen" not in second


def test_load_of_corrupt_slot_keeps_running_game(tmp_path):
    store = SaveStore(tmp_path)
    s = Session(WORLD, store=store)
    s.new_game()
    write_slot(store, "kaputt", "[]")
    s.submit("gehe norden")
    out = s.submit("lade kaputt").text
    assert "beschädigt" in out or "ungültig" in out
    assert s.game.location == "torhaus"
