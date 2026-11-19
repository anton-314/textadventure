from pathlib import Path

import pytest

from textadventure.events import AchievementUnlocked, ItemDropped, ItemTaken
from textadventure.saves import SaveStore
from textadventure.session import AUTOSAVE, Session
from textadventure.world import World
from test_engine import WORLD

@pytest.fixture
def store(tmp_path):
    return SaveStore(tmp_path / "store")


@pytest.fixture
def session(store):
    s = Session(WORLD, store=store)
    s.new_game()
    return s


def test_no_game_running():
    s = Session(WORLD)
    assert not s.running
    assert "kein Spiel" in s.submit("schau").text


def test_new_game_describes(store):
    s = Session(WORLD, store=store)
    assert "Verfallener Hof" in s.new_game().text
    assert s.running


def test_save_and_load_restores_state(session):
    for cmd in ("nimm laterne", "gehe norden", "gehe unten", "nimm schlüssel", "gehe oben",
                "öffne eichentür"):
        session.submit(cmd)
    assert "Gespeichert" in session.submit("speichere eins").text
    session.submit("gehe osten")
    session.submit("lasse schlüssel")
    assert session.game.location == "wachstube"
    res = session.submit("lade eins")
    assert "geladen" in res.text
    g = session.game
    assert g.location == "torhaus"
    assert sorted(g.inventory) == ["laterne", "schlüssel"]
    assert "eichentür" in g.open_doors
    assert g.room_items["wachstube"] == ["wachbuch"]


def test_load_into_fresh_session(store):
    a = Session(WORLD, store=store)
    a.new_game()
    a.submit("nimm laterne")
    a.submit("speichere x")
    b = Session(WORLD, store=store)
    assert "geladen" in b.load("x").text
    assert b.game.inventory == ["laterne"]


def test_load_missing_slot_keeps_game(session):
    session.submit("nimm laterne")
    res = session.submit("lade gibtsnicht")
    assert "gibt es nicht" in res.text
    assert session.game.inventory == ["laterne"]


def test_load_invalid_slot_name(session):
    res = session.submit("lade ../x")
    assert "Ungültig" in res.text
    assert session.game.location == "hof"


def test_save_invalid_slot_reports(session, tmp_path):
    res = session.submit("speichere ../x")
    assert "fehlgeschlagen" in res.text
    assert not list(tmp_path.rglob("x.json"))


def test_save_default_slot(session, store):
    session.submit("speichere")
    assert [i.slot for i in store.slots()] == ["slot1"]


def test_slots_listed(session):
    session.submit("speichere eins")
    text = session.submit("spielstände").text
    assert "eins" in text and "Verfallener Hof" in text


def test_slots_empty_without_any_save(store):
    s = Session(WORLD, store=store)
    s.new_game()
    assert "Keine Spielstände" in s.submit("spielstände").text


def test_autosave_created_after_command(session, store):
    assert store.slots() == []
    session.submit("nimm laterne")
    assert (store.root / f"{AUTOSAVE}.json").exists()
    fresh = Session(WORLD, store=store)
    fresh.load("auto")
    assert fresh.game.inventory == ["laterne"]


def test_autosave_not_after_quit(session, store):
    session.submit("ende")
    assert not (store.root / "auto.json").exists()


def test_autosave_not_overwriting_on_save_load_commands(session, store):
    session.submit("nimm laterne")
    session.submit("gehe norden")
    session.submit("lade auto")   # lädt Stand nach 'gehe norden'
    assert session.game.location == "torhaus"


def test_load_default_is_auto(session):
    session.submit("nimm laterne")   # Autosave: Laterne im Inventar
    session.submit("lasse laterne")  # Autosave: Laterne im Raum
    session.submit("nimm laterne")
    session.submit("lade")
    assert session.game.inventory == ["laterne"]
    session.submit("lasse laterne")
    session.submit("lade")           # 'auto' enthält jetzt den Stand nach 'lasse'
    assert session.game.inventory == []


def test_interpreter_is_used(store):
    class Fake:
        def to_command(self, text, context):
            return "nimm laterne"
    s = Session(WORLD, store=store, interpreter=Fake())
    s.new_game()
    s.submit("ich will licht")
    assert s.game.inventory == ["laterne"]


def test_reactors_passed_to_game(store):
    seen = []

    class R:
        def react(self, ev, game, out):
            seen.append(ev)
            return []
    s = Session(WORLD, store=store, reactors=(R(),))
    s.new_game()
    s.submit("nimm laterne")
    assert [e for e in seen if not isinstance(e, AchievementUnlocked)] == [ItemTaken("laterne")]
    s.submit("speichere a")
    s.load("a")
    s.submit("lasse laterne")
    assert seen[-1] == ItemDropped("laterne")   # Reactors überleben das Laden


def test_nothing_written_outside_tmp(tmp_path, monkeypatch):
    """Session ohne expliziten Store schreibt nur nach TEXTADVENTURE_HOME (= tmp_path)."""
    s = Session(WORLD)
    s.new_game()
    s.submit("nimm laterne")
    s.submit("speichere a")
    home = tmp_path / "home"
    assert (home / "saves" / "auto.json").exists()
    assert (home / "saves" / "a.json").exists()
    real = Path.home() / ".local" / "share" / "textadventure" / "saves"
    assert not real.exists() or not (real / "a.json").exists()
