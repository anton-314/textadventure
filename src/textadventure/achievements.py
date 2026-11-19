"""Erfolge: datengetriebene Regeln (in world.json), ausgewertet als Reactor auf Engine-Events.

Der Reactor ist zustandslos; Fortschritt und freigeschaltete Erfolge liegen im GameState
(`stats["ach:<id>"]`, `achievements`) und werden dadurch mitgespeichert.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterable

from .events import EVENT_TYPES, AchievementUnlocked, Event, Result, event_fields, matches

if TYPE_CHECKING:
    from .engine import Game

# Muster-Schlüssel, die auf Weltdaten verweisen (für die Validierung)
REFERENCES = {"item": "items", "door": "doors", "room": "rooms"}
# Technische Events ergeben keinen sinnvollen Erfolg
NOT_ACHIEVABLE = {"save_requested", "load_requested", "slots_requested"}


@dataclass(frozen=True)
class AchievementDef:
    id: str
    name: str
    when: dict[str, Any]
    description: str = ""
    hidden: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.when, dict):      # Weltdaten sind schreibgeschützt (von allen Spielen geteilt)
            object.__setattr__(self, "when", MappingProxyType(dict(self.when)))


def validate(defs: Iterable[AchievementDef], world) -> None:
    defs = list(defs)
    seen: set[str] = set()
    for a in defs:
        if a.id in seen:
            raise ValueError(f"Erfolg '{a.id}': doppelte ID")
        seen.add(a.id)
    for a in defs:
        if not isinstance(a.when, (dict, MappingProxyType)):
            raise ValueError(f"Erfolg '{a.id}': 'when' muss ein Objekt sein")
        kind = a.when.get("event")
        if kind not in EVENT_TYPES:
            raise ValueError(f"Erfolg '{a.id}': unbekanntes Event '{kind}'")
        if kind in NOT_ACHIEVABLE:
            raise ValueError(f"Erfolg '{a.id}': Event '{kind}' ist technisch und kann keinen Erfolg auslösen")
        if kind == "achievement" and "id" in a.when and a.when["id"] not in seen:
            raise ValueError(f"Erfolg '{a.id}': unbekannte Referenz id='{a.when['id']}'")
        for key, value in a.when.items():
            if key in ("event", "count"):
                continue
            if key not in event_fields(kind):
                raise ValueError(f"Erfolg '{a.id}': Event '{kind}' hat kein Feld '{key}'")
            if key in REFERENCES and value not in getattr(world, REFERENCES[key]):
                raise ValueError(f"Erfolg '{a.id}': unbekannte Referenz {key}='{value}'")
        count = a.when.get("count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError(f"Erfolg '{a.id}': 'count' muss eine ganze Zahl >= 1 sein")


class AchievementReactor:
    def react(self, ev: Event, game: "Game", out: Result) -> Iterable[Event]:
        unlocked: list[Event] = []
        for a in game.world.achievements:
            if a.id in game.state.achievements or not matches(ev, a.when):
                continue
            key = f"ach:{a.id}"
            progress = game.state.stats[key] = game.state.stats.get(key, 0) + 1
            if progress >= a.when.get("count", 1):
                game.state.achievements.add(a.id)
                out.say(f"[Erfolg] {a.name}" + (f" - {a.description}" if a.description else ""))
                unlocked.append(AchievementUnlocked(a.id))
        return unlocked


def achievement_lines(game: "Game") -> list[str]:
    defs = game.world.achievements
    done = game.state.achievements
    lines = [f"Erfolge ({sum(a.id in done for a in defs)}/{len(defs)}):"]
    for a in defs:
        if a.id in done:
            lines.append(f"  [x] {a.name} - {a.description}")
        elif a.hidden:
            lines.append("  [ ] ???")
        else:
            progress, need = game.state.stats.get(f"ach:{a.id}", 0), a.when.get("count", 1)
            extra = f" ({progress}/{need})" if need > 1 else ""
            lines.append(f"  [ ] {a.name} - {a.description}{extra}")
    if not defs:
        lines.append("  (keine)")
    return lines
