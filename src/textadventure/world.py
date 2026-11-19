"""Weltdaten: Räume und Gegenstände, geladen aus JSON."""
from __future__ import annotations

import json
from types import MappingProxyType
from dataclasses import dataclass, field
from pathlib import Path

from .commands import COMMANDS, FILLER, match_key, normalize
from .achievements import AchievementDef, validate as validate_achievements


ITEM_KINDS = {"misc", "key", "readable", "consumable", "weapon", "armor"}
DEFAULT_WORLD = Path(__file__).resolve().parent / "data" / "world.json"


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    description: str
    takeable: bool = True
    kind: str = "misc"           # Grundlage für spätere RPG-Mechaniken
    stackable: bool = False
    props: dict = field(default_factory=dict)   # frei: {"slot": "hand", "attack": 2, "heal": 5}

    def __post_init__(self) -> None:
        # Weltdaten sind schreibgeschützt (die World wird von allen Spielen geteilt)
        object.__setattr__(self, "props", MappingProxyType(dict(self.props)))


@dataclass(frozen=True)
class Exit:
    to: str
    door: str | None = None


@dataclass(frozen=True)
class Door:
    id: str
    name: str
    description: str
    key: str
    locked_text: str = "Die Tür ist verschlossen."
    open_text: str = "Du öffnest die Tür."


@dataclass
class Room:
    id: str
    name: str
    description: str
    exits: dict[str, Exit] = field(default_factory=dict)
    items: list[str] = field(default_factory=list)
    pos: tuple[int, int, int] | None = None     # optional: manuelle Kartenposition (x, y, ebene)


@dataclass
class World:
    start: str
    rooms: dict[str, Room]
    items: dict[str, Item]
    doors: dict[str, Door] = field(default_factory=dict)
    achievements: tuple[AchievementDef, ...] = ()

    @classmethod
    def load(cls, path: str | Path) -> "World":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for key in ("start", "rooms", "items"):
            if key not in raw:
                raise ValueError(f"world.json: Pflichtfeld '{key}' fehlt")
        rooms = {}
        for rid, r in raw["rooms"].items():
            try:
                exits = {d: _exit(v) for d, v in r.get("exits", {}).items()}
                map_pos = r.get("map", {}).get("pos")
                rooms[rid] = Room(id=rid, name=r["name"], description=r["description"],
                                  exits=exits, items=list(r.get("items", [])),
                                  pos=tuple(map_pos) if map_pos is not None else None)
            except (KeyError, TypeError) as e:
                raise ValueError(f"Raum '{rid}': fehlerhafte Daten ({e!r})") from e
        items = _build(Item, raw["items"], "Item")
        doors = _build(Door, raw.get("doors", {}), "Tür")
        try:
            achievements = tuple(AchievementDef(**a) for a in raw.get("achievements", []))
        except TypeError as e:
            raise ValueError(f"Erfolge: fehlerhafte Daten ({e})") from e
        world = cls(start=raw["start"], rooms=rooms, items=items, doors=doors,
                    achievements=achievements)
        world._validate()
        from .mapview import layout   # Kartenfehler schon beim Laden melden, nicht erst im Spiel
        layout(world)
        return world

    def _validate_names(self) -> None:
        """Namen müssen eintippbar und eindeutig sein: "mit" trennt Werkzeuge ab, Richtungswörter sind Befehle."""
        seen: dict[str, str] = {}
        named = [(f"Item '{i.id}'", i.name) for i in self.items.values()] + \
                [(f"Tür '{d.id}'", d.name) for d in self.doors.values()]
        for label, name in named:
            words = normalize(name).split()
            if "mit" in words:
                raise ValueError(f"{label}: Name '{name}' enthält 'mit' und wäre nicht eintippbar")
            key = match_key(name)
            if not key:
                raise ValueError(f"{label}: Name '{name}' besteht nur aus Füllwörtern ({sorted(FILLER)})")
            if COMMANDS.direction(key):
                raise ValueError(f"{label}: Name '{name}' ist ein Richtungswort")
            if key in seen:
                raise ValueError(f"{label}: Name '{name}' kollidiert mit {seen[key]}")
            seen[key] = label

    def _validate(self) -> None:
        """Fängt Tippfehler in den JSON-Daten früh ab."""
        if self.start not in self.rooms:
            raise ValueError(f"Startraum '{self.start}' existiert nicht")
        for room in self.rooms.values():
            if room.pos is not None and not (len(room.pos) == 3 and all(
                    isinstance(v, int) and not isinstance(v, bool) for v in room.pos)):
                raise ValueError(f"Raum '{room.id}': map.pos braucht genau 3 ganze Zahlen [x, y, ebene]")
        for item in self.items.values():
            if item.kind not in ITEM_KINDS:
                raise ValueError(f"Item '{item.id}': unbekannte Art '{item.kind}'")
            if item.stackable and not item.takeable:
                raise ValueError(f"Item '{item.id}': stapelbar, aber nicht mitnehmbar")
        for room in self.rooms.values():
            for direction, ex in room.exits.items():
                if ex.to not in self.rooms:
                    raise ValueError(f"{room.id}: Ausgang '{direction}' führt zu unbekanntem Raum '{ex.to}'")
                if ex.door and ex.door not in self.doors:
                    raise ValueError(f"{room.id}: Ausgang '{direction}' nutzt unbekannte Tür '{ex.door}'")
            for iid in room.items:
                if iid not in self.items:
                    raise ValueError(f"{room.id}: unbekanntes Item '{iid}'")
        self._validate_names()
        validate_achievements(self.achievements, self)
        for door in self.doors.values():
            if door.key not in self.items:
                raise ValueError(f"Tür '{door.id}': unbekannter Schlüssel '{door.key}'")
            if not self.items[door.key].takeable:
                raise ValueError(f"Tür '{door.id}': Schlüssel '{door.key}' ist nicht mitnehmbar")


def _exit(value: str | dict) -> Exit:
    return Exit(value) if isinstance(value, str) else Exit(**value)


def _build(cls, raw: dict, label: str) -> dict:
    out = {}
    for key, fields in raw.items():
        try:
            out[key] = cls(id=key, **fields)
        except TypeError as e:
            raise ValueError(f"{label} '{key}': fehlerhafte Daten ({e})") from e
    return out
