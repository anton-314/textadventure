import dataclasses

import pytest

from textadventure.engine import Game
from textadventure.events import (EVENT_TYPES, DoorOpened, ItemDropped, ItemExamined, ItemTaken,
                                  Result, RoomEntered, SaveRequested, event_fields, matches)
from textadventure.world import World
from test_engine import WORLD


def plain_world() -> World:
    """Weltdaten ohne Erfolge: diese Tests prüfen Engine/Events, nicht die Erfolge."""
    return dataclasses.replace(World.load(WORLD), achievements=())


def new_game(**kw) -> Game:
    return Game(plain_world(), **kw)


def test_take_emits_event():
    g = new_game()
    assert g.execute("nimm laterne").events == [ItemTaken("laterne")]


def test_failed_take_emits_nothing():
    g = new_game()
    assert g.execute("nimm schwert").events == []
    g.execute("nimm laterne")
    assert g.execute("nimm laterne").events == []   # doppelt nehmen
    assert g.inventory == ["laterne"]


def test_drop_and_examine_events():
    g = new_game()
    g.execute("nimm laterne")
    assert g.execute("untersuche laterne").events == [ItemExamined("laterne")]
    assert g.execute("lasse laterne").events == [ItemDropped("laterne")]


def test_room_entered_first_only_once():
    g = new_game()
    assert g.execute("gehe norden").events == [RoomEntered("torhaus", True)]
    assert g.execute("gehe süden").events == [RoomEntered("hof", False)]  # Start gilt als besucht
    assert g.execute("gehe norden").events == [RoomEntered("torhaus", False)]


def test_blocked_move_emits_nothing():
    g = new_game()
    assert g.execute("gehe osten").events == []
    assert g.location == "hof"


def test_door_opened_event():
    g = new_game()
    for cmd in ("gehe norden", "gehe unten", "nimm schlüssel", "gehe oben"):
        g.execute(cmd)
    assert g.execute("öffne eichentür").events == [DoorOpened("eichentür")]
    assert "eichentür" in g.open_doors


def test_empty_and_unknown_input_no_events():
    g = new_game()
    assert g.execute("").events == []
    assert g.execute("   ").events == []
    assert g.execute("tanze wild").events == []
    assert g.location == "hof"


def test_handle_is_text_of_execute():
    g = new_game()
    assert "Laterne" in g.handle("nimm laterne")


def test_turns_counted():
    g = new_game()
    g.execute("schau")
    g.execute("gehe norden")
    g.execute("")            # leere Eingabe, unbekanntes Verb und Meta-Befehle verbrauchen keinen Zug
    g.execute("tanze")
    g.execute("hilfe")
    assert g.state.turns == 2


def test_matches():
    ev = ItemTaken("schlüssel")
    assert matches(ev, {"event": "item_taken", "item": "schlüssel"})
    assert matches(ev, {"event": "item_taken"})
    assert matches(ev, {"event": "item_taken", "count": 3})
    assert not matches(ev, {"event": "item_taken", "item": "laterne"})
    assert not matches(ev, {"event": "item_dropped", "item": "schlüssel"})
    assert not matches(ev, {"event": "item_taken", "unbekannt": 1})


def test_event_fields_and_registry():
    assert event_fields("room_entered") == {"room", "first"}
    for kind, cls in EVENT_TYPES.items():
        assert cls.kind == kind


def test_events_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        ItemTaken("a").item = "b"


def test_result_text_and_chaining():
    r = Result().say("a").say("b").emit(SaveRequested("x"))
    assert r.text == "a\nb"
    assert r.events == [SaveRequested("x")]


class Recorder:
    def __init__(self):
        self.seen = []

    def react(self, ev, game, out):
        self.seen.append(ev)
        return []


class Achiever:
    """Hängt Text an und liefert ein Folge-Event."""

    def __init__(self):
        self.seen = []

    def react(self, ev, game, out):
        self.seen.append(ev)
        if isinstance(ev, ItemTaken):
            out.say("Erfolg!")
            return [ItemExamined(ev.item)]
        return []


def test_reactor_receives_events():
    rec = Recorder()
    g = new_game(reactors=[rec])
    g.execute("nimm laterne")
    assert rec.seen == [ItemTaken("laterne")]


def test_reactor_appends_text_and_follow_up_events():
    r = Achiever()
    g = new_game(reactors=[r])
    res = g.execute("nimm laterne")
    assert "Erfolg!" in res.text
    assert r.seen == [ItemTaken("laterne"), ItemExamined("laterne")]


def test_multiple_reactors_all_called():
    a, b = Recorder(), Recorder()
    new_game(reactors=[a, b]).execute("nimm laterne")
    assert a.seen == b.seen == [ItemTaken("laterne")]
