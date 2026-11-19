"""Veränderlicher, serialisierbarer Spielzustand (getrennt von den unveränderlichen Weltdaten)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .world import World

SAVE_VERSION = 1


@dataclass
class GameState:
    location: str
    inventory: list[str] = field(default_factory=list)
    room_items: dict[str, list[str]] = field(default_factory=dict)
    open_doors: set[str] = field(default_factory=set)
    visited: set[str] = field(default_factory=set)
    flags: dict[str, Any] = field(default_factory=dict)     # Quests/Dialoge später
    stats: dict[str, int] = field(default_factory=dict)     # Zähler, z. B. für Erfolge
    achievements: set[str] = field(default_factory=set)
    turns: int = 0

    @classmethod
    def new(cls, world: World) -> "GameState":
        return cls(location=world.start,
                   room_items={rid: list(r.items) for rid, r in world.rooms.items()},
                   visited={world.start})

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "inventory": list(self.inventory),
            "room_items": {rid: list(items) for rid, items in self.room_items.items()},
            "open_doors": sorted(self.open_doors),
            "visited": sorted(self.visited),
            "flags": dict(self.flags),
            "stats": dict(self.stats),
            "achievements": sorted(self.achievements),
            "turns": self.turns,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], world: World) -> "GameState":
        """Baut den Zustand auf. Unbekannte IDs (z. B. nach Welt-Update) werden verworfen,
        neue Räume/Items kommen aus den Weltdaten."""
        if not isinstance(d, dict):
            raise ValueError("Spielstand: Zustand ist kein Objekt")
        for key, typ in (("inventory", list), ("room_items", dict), ("open_doors", list), ("visited", list),
                         ("flags", dict), ("stats", dict), ("achievements", list)):
            if not isinstance(d.get(key, typ()), typ):
                raise ValueError(f"Spielstand: '{key}' hat den falschen Typ")
        state = cls.new(world)
        if d.get("location") not in world.rooms:
            raise ValueError(f"Spielstand: unbekannter Ort '{d.get('location')}'")
        state.location = d["location"]
        state.inventory = [i for i in d.get("inventory", []) if i in world.items]
        for rid, items in d.get("room_items", {}).items():
            if rid in world.rooms:
                state.room_items[rid] = [i for i in items if i in world.items]
        state.open_doors = {x for x in d.get("open_doors", []) if x in world.doors}
        state.visited = {x for x in d.get("visited", []) if x in world.rooms} | {state.location}
        state.flags = dict(d.get("flags", {}))
        known = {a.id for a in world.achievements}
        state.stats = {k: int(v) for k, v in d.get("stats", {}).items()
                       if not k.startswith("ach:") or k[4:] in known}
        state.achievements = {a for a in d.get("achievements", []) if a in known}
        state.turns = int(d.get("turns", 0))
        # Ein (nicht stapelbares) Item existiert nur einmal: Was im Inventar ist, liegt nirgends sonst
        for item in set(state.inventory):
            if not world.items[item].stackable:
                for items in state.room_items.values():
                    while item in items:
                        items.remove(item)
        return state
