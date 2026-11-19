import json

import pytest

from textadventure.engine import Game
from textadventure.events import AchievementUnlocked
from textadventure.saves import SaveStore
from textadventure.session import Session
from textadventure.world import World
from test_engine import WORLD

TAKE_KEY = ("nimm laterne", "gehe norden", "gehe unten", "nimm schlüssel", "gehe oben")


def new_game() -> Game:
    return Game(World.load(WORLD))


def world_file(tmp_path, achievements, mutate=None):
    raw = json.loads(WORLD.read_text(encoding="utf-8"))
    raw["achievements"] = achievements
    if mutate:
        mutate(raw)
    path = tmp_path / "w.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def ach(**kw):
    base = {"id": "a", "name": "A", "description": "d", "when": {"event": "item_taken"}}
    base.update(kw)
    return base


def test_unlock_on_take_text_and_event():
    g = new_game()
    res = g.execute("nimm laterne")
    assert "[Erfolg] Lichtbringer - Die Laterne an dich genommen." in res.lines
    assert [e.id for e in res.events if isinstance(e, AchievementUnlocked)] == ["lichtbringer"]
    assert "lichtbringer" in g.state.achievements


def test_unlock_only_once_when_taking_again():
    g = new_game()
    g.handle("nimm laterne")
    g.handle("lasse laterne")
    res = g.execute("nimm laterne")
    assert "[Erfolg]" not in res.text
    assert not [e for e in res.events if isinstance(e, AchievementUnlocked)]
    assert g.state.stats["ach:lichtbringer"] == 1


def test_no_unlock_for_other_item():
    g = new_game()
    g.handle("gehe norden")
    g.handle("gehe unten")
    res = g.execute("nimm schlüssel")
    assert "Lichtbringer" not in res.text
    assert "lichtbringer" not in g.state.achievements


def test_door_achievement():
    g = new_game()
    for c in TAKE_KEY:
        g.handle(c)
    res = g.execute("öffne eichentür")
    assert "[Erfolg] Eingelassen" in res.text
    assert "eingelassen" in g.state.achievements


def test_count_achievement_progress():
    g = new_game()
    g.handle("gehe norden")
    assert g.state.stats["ach:entdecker"] == 1       # Torhaus (Hof zählt nicht: Start)
    g.handle("gehe unten")
    assert g.state.stats["ach:entdecker"] == 2
    text = g.handle("erfolge")
    assert "Entdecker - Alle Orte der Burg betreten. (2/4)" in text
    assert "entdecker" not in g.state.achievements
    # Wiederbetreten zählt nicht (first=false)
    g.handle("gehe oben")
    assert g.state.stats["ach:entdecker"] == 2


def test_count_achievement_unlocks_at_count():
    g = new_game()
    for c in TAKE_KEY:
        g.handle(c)
    g.handle("öffne eichentür")
    assert "entdecker" not in g.state.achievements
    g.handle("gehe osten")        # 3 (torhaus, keller, wachstube)
    assert "entdecker" not in g.state.achievements
    res = g.execute("gehe oben")  # 4
    assert "[Erfolg] Entdecker" in res.text
    assert "entdecker" in g.state.achievements


def test_hidden_achievement_listed_as_question_marks():
    g = new_game()
    text = g.handle("erfolge")
    assert "Erfolge (0/4):" in text
    assert "  [ ] ???" in text
    assert "Siegelträger" not in text


def test_hidden_achievement_revealed_when_unlocked():
    g = new_game()
    g.state.achievements.add("siegeltraeger")
    text = g.handle("erfolge")
    assert "[x] Siegelträger - Den Siegelring gefunden." in text
    assert "???" not in text


def test_erfolge_lists_unlocked_and_counts():
    g = new_game()
    g.handle("nimm laterne")
    text = g.handle("erfolge")
    assert "Erfolge (1/4):" in text
    assert "[x] Lichtbringer - Die Laterne an dich genommen." in text


def test_erfolge_costs_no_turn():
    g = new_game()
    g.handle("erfolge")
    assert g.state.turns == 0


def test_world_without_achievements(tmp_path):
    p = world_file(tmp_path, [])
    g = Game(World.load(p))
    assert "(keine)" in g.handle("erfolge")


def test_achievements_survive_save_and_load(tmp_path):
    store = SaveStore(tmp_path / "store")
    s = Session(WORLD, store=store)
    s.new_game()
    s.submit("nimm laterne")
    s.submit("gehe norden")
    s.submit("speichere a")
    s2 = Session(WORLD, store=store)
    assert "geladen" in s2.load("a").text
    st = s2.game.state
    assert st.achievements == {"lichtbringer"}
    assert st.stats["ach:entdecker"] == 1
    assert "[x] Lichtbringer" in s2.submit("erfolge").text


def test_no_double_award_after_load(tmp_path):
    store = SaveStore(tmp_path / "store")
    s = Session(WORLD, store=store)
    s.new_game()
    s.submit("nimm laterne")
    s.submit("speichere a")
    s.submit("lasse laterne")
    s2 = Session(WORLD, store=store)
    s2.load("a")
    s2.submit("lasse laterne")
    res = s2.submit("nimm laterne")
    assert "[Erfolg]" not in res.text
    assert not [e for e in res.events if isinstance(e, AchievementUnlocked)]


def test_progress_continues_after_load(tmp_path):
    store = SaveStore(tmp_path / "store")
    s = Session(WORLD, store=store)
    s.new_game()
    s.submit("gehe norden")
    s.submit("speichere a")
    s2 = Session(WORLD, store=store)
    s2.load("a")
    s2.submit("gehe unten")
    assert s2.game.state.stats["ach:entdecker"] == 2


def test_session_achievement_lines():
    s = Session(WORLD, store=None)
    assert s.achievement_lines() == []
    s.new_game()
    assert s.achievement_lines()[0] == "Erfolge (0/4):"


# --- Validierung -------------------------------------------------------------

def load_with(tmp_path, achievements, mutate=None):
    return World.load(world_file(tmp_path, achievements, mutate))


def test_valid_custom_achievement_loads(tmp_path):
    w = load_with(tmp_path, [ach(when={"event": "item_taken", "item": "laterne", "count": 1})])
    assert w.achievements[0].id == "a"


def test_unknown_event(tmp_path):
    with pytest.raises(ValueError, match="unbekanntes Event"):
        load_with(tmp_path, [ach(when={"event": "gibts_nicht"})])


def test_missing_event(tmp_path):
    with pytest.raises(ValueError, match="unbekanntes Event"):
        load_with(tmp_path, [ach(when={"item": "laterne"})])


def test_unknown_field(tmp_path):
    with pytest.raises(ValueError, match="kein Feld"):
        load_with(tmp_path, [ach(when={"event": "item_taken", "farbe": "rot"})])


def test_unknown_item_reference(tmp_path):
    with pytest.raises(ValueError, match="unbekannte Referenz"):
        load_with(tmp_path, [ach(when={"event": "item_taken", "item": "nix"})])


def test_unknown_door_reference(tmp_path):
    with pytest.raises(ValueError, match="unbekannte Referenz"):
        load_with(tmp_path, [ach(when={"event": "door_opened", "door": "nix"})])


def test_unknown_room_reference(tmp_path):
    with pytest.raises(ValueError, match="unbekannte Referenz"):
        load_with(tmp_path, [ach(when={"event": "room_entered", "room": "nix"})])


def test_duplicate_id(tmp_path):
    with pytest.raises(ValueError, match="doppelte ID"):
        load_with(tmp_path, [ach(), ach(name="B")])


@pytest.mark.parametrize("count", [0, -1, 1.5, "2", None])
def test_bad_count(tmp_path, count):
    with pytest.raises(ValueError, match="count"):
        load_with(tmp_path, [ach(when={"event": "item_taken", "count": count})])


def test_unknown_achievement_key(tmp_path):
    with pytest.raises(ValueError, match="Erfolge"):
        load_with(tmp_path, [ach(farbe="rot")])


def test_missing_required_achievement_key(tmp_path):
    bad = {"id": "x", "name": "X"}
    with pytest.raises(ValueError, match="Erfolge"):
        load_with(tmp_path, [bad])
