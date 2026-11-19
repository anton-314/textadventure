import json

import pytest

from textadventure.engine import Game
from textadventure.saves import SaveError, SaveStore, data_dir, migrate
from textadventure.state import SAVE_VERSION, GameState
from textadventure.world import World
from test_engine import WORLD


@pytest.fixture
def world():
    return World.load(WORLD)


@pytest.fixture
def store(tmp_path):
    return SaveStore(tmp_path)


def played(world):
    g = Game(world)
    for cmd in ("nimm laterne", "gehe norden"):
        g.execute(cmd)
    return g.state


def test_save_load_roundtrip(store, world):
    s = played(world)
    store.save("slot1", s, world)
    assert store.load("slot1", world) == s


@pytest.mark.parametrize("bad", ["../x", "A b", "", "a/b", "x" * 33, "Großbuchstabe", "a.b", "..", "a\nb"])
def test_invalid_slot_names(store, world, bad):
    with pytest.raises(SaveError):
        store.save(bad, GameState.new(world), world)
    with pytest.raises(SaveError):
        store.load(bad, world)


def test_invalid_slot_writes_nothing(store, tmp_path, world):
    with pytest.raises(SaveError):
        store.save("../x", GameState.new(world), world)
    assert not (tmp_path / "x.json").exists()
    assert not list(tmp_path.rglob("*.json"))


def test_missing_slot(store, world):
    with pytest.raises(SaveError):
        store.load("nix", world)


def test_corrupt_json(store, world):
    store.save("a", GameState.new(world), world)
    (store.root / "a.json").write_text("{kaputt", encoding="utf-8")
    with pytest.raises(SaveError):
        store.load("a", world)


@pytest.mark.parametrize("content", ["{}", '{"version": 1}', '{"version": 1, "state": {}}', "[]"])
def test_incomplete_save(store, world, content):
    store.root.mkdir(parents=True)
    (store.root / "a.json").write_text(content, encoding="utf-8")
    with pytest.raises(SaveError):
        store.load("a", world)


def test_unknown_location_is_save_error(store, world):
    store.save("a", GameState.new(world), world)
    p = store.root / "a.json"
    env = json.loads(p.read_text(encoding="utf-8"))
    env["state"]["location"] = "nirgendwo"
    p.write_text(json.dumps(env), encoding="utf-8")
    with pytest.raises(SaveError):
        store.load("a", world)


def test_newer_version_rejected(store, world):
    store.save("a", GameState.new(world), world)
    p = store.root / "a.json"
    env = json.loads(p.read_text(encoding="utf-8"))
    env["version"] = SAVE_VERSION + 1
    p.write_text(json.dumps(env), encoding="utf-8")
    with pytest.raises(SaveError, match="neuer"):
        store.load("a", world)


def test_migrate_current_unchanged():
    env = {"version": SAVE_VERSION, "state": {}}
    assert migrate(env) == env


def test_migrate_old_without_step_fails():
    with pytest.raises(SaveError):
        migrate({"version": 0})


def test_migrate_runs_steps(monkeypatch):
    import textadventure.saves as saves
    monkeypatch.setattr(saves, "MIGRATIONS", {0: lambda e: {**e, "version": 1, "migriert": True}})
    assert migrate({"version": 0})["migriert"] is True


def test_overwrite_slot_and_no_tmp_left(store, world):
    s = GameState.new(world)
    store.save("a", s, world)
    s2 = played(world)
    store.save("a", s2, world)
    assert store.load("a", world) == s2
    assert [p.name for p in store.root.iterdir()] == ["a.json"]


def test_slots_listing(store, world):
    assert store.slots() == []
    store.save("b", GameState.new(world), world)
    store.save("a", played(world), world)
    infos = store.slots()
    assert [i.slot for i in infos] == ["a", "b"]
    assert infos[0].meta == {"room": "Torhaus", "turns": 2}


def test_slots_skips_corrupt_files(store, world):
    store.save("a", GameState.new(world), world)
    (store.root / "kaputt.json").write_text("{", encoding="utf-8")
    assert [i.slot for i in store.slots()] == ["a"]


def test_data_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXTADVENTURE_HOME", str(tmp_path / "h"))
    assert data_dir() == tmp_path / "h"
    assert SaveStore().root == tmp_path / "h" / "saves"


def test_data_dir_xdg_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("TEXTADVENTURE_HOME")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("sys.platform", "linux")
    assert data_dir() == tmp_path / "xdg" / "textadventure"
