"""Ereignisse und Ergebnis-Typ der Engine. Frontends, Erfolge, Quests und KI reagieren darauf."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar


@dataclass(frozen=True)
class Event:
    kind: ClassVar[str] = "event"


@dataclass(frozen=True)
class RoomEntered(Event):
    kind: ClassVar[str] = "room_entered"
    room: str
    first: bool


@dataclass(frozen=True)
class ItemTaken(Event):
    kind: ClassVar[str] = "item_taken"
    item: str


@dataclass(frozen=True)
class ItemDropped(Event):
    kind: ClassVar[str] = "item_dropped"
    item: str


@dataclass(frozen=True)
class ItemExamined(Event):
    kind: ClassVar[str] = "item_examined"
    item: str


@dataclass(frozen=True)
class DoorOpened(Event):
    kind: ClassVar[str] = "door_opened"
    door: str


@dataclass(frozen=True)
class AchievementUnlocked(Event):
    kind: ClassVar[str] = "achievement"
    id: str


@dataclass(frozen=True)
class SaveRequested(Event):
    """Die Engine macht kein I/O; die Session führt das Speichern aus."""
    kind: ClassVar[str] = "save_requested"
    slot: str


@dataclass(frozen=True)
class LoadRequested(Event):
    kind: ClassVar[str] = "load_requested"
    slot: str


@dataclass(frozen=True)
class SlotsRequested(Event):
    kind: ClassVar[str] = "slots_requested"


EVENT_TYPES: dict[str, type[Event]] = {
    c.kind: c for c in (RoomEntered, ItemTaken, ItemDropped, ItemExamined, DoorOpened,
                        SaveRequested, LoadRequested, SlotsRequested, AchievementUnlocked)
}


def matches(ev: Event, pattern: dict[str, Any]) -> bool:
    """Prüft ein Event gegen ein JSON-Muster, z. B. {"event": "item_taken", "item": "schlüssel"}."""
    return ev.kind == pattern.get("event") and all(
        getattr(ev, k, object()) == v for k, v in pattern.items() if k not in ("event", "count"))


def event_fields(kind: str) -> set[str]:
    return {f.name for f in fields(EVENT_TYPES[kind])}


@dataclass
class Result:
    lines: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def say(self, line: str) -> "Result":
        self.lines.append(line)
        return self

    def emit(self, event: Event) -> "Result":
        self.events.append(event)
        return self
