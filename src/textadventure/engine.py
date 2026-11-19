"""Spiellogik. Gibt Ergebnisse zurück (Text + Events), macht selbst keine Ein-/Ausgabe."""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Iterable, Protocol, Sequence

from .achievements import AchievementReactor
from .commands import COMMANDS, match_key
from .events import Event, Result
from .mapview import layout, render
from .parser import parse_command
from .state import GameState
from .verbs import VERBS
from .world import Door, World

MAX_EVENTS_PER_TURN = 100


class Reactor(Protocol):
    """Reagiert auf Events (Erfolge, später Quests). Darf Text anhängen und Folge-Events liefern."""

    def react(self, ev: Event, game: "Game", out: Result) -> Iterable[Event]: ...


@dataclass
class Game:
    world: World
    state: GameState | None = None
    reactors: Sequence[Reactor] = ()
    running: bool = True

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = GameState.new(self.world)
        # Erfolge sind immer aktiv; eigene Reactors kommen danach
        self.reactors = (AchievementReactor(), *self.reactors)
        self.layout = layout(self.world)     # ValueError bei widersprüchlicher Karte

    def map_lines(self) -> list[str]:
        return render(self.world, self.layout, self.state.visited, self.location, self.state.open_doors)

    # Kurzzugriffe auf den Zustand
    @property
    def location(self) -> str:
        return self.state.location

    @property
    def inventory(self) -> list[str]:
        return self.state.inventory

    @property
    def room_items(self) -> dict[str, list[str]]:
        return self.state.room_items

    @property
    def open_doors(self) -> set[str]:
        return self.state.open_doors

    @property
    def room(self):
        return self.world.rooms[self.location]

    # Anzeige
    def describe(self) -> str:
        r = self.room
        lines = [f"== {r.name} ==", r.description]
        items = self.state.room_items[r.id]
        if items:
            lines.append("Hier liegt: " + ", ".join(self.world.items[i].name for i in items))
        lines.append("Ausgänge: " + ", ".join(self.exit_labels()))
        return "\n".join(lines)

    def exit_labels(self) -> list[str]:
        return [self._exit_label(d, e) for d, e in self.room.exits.items()]

    def inventory_names(self) -> list[str]:
        return [self.world.items[i].name for i in self.state.inventory]

    def _exit_label(self, direction: str, ex) -> str:
        if ex.door and ex.door not in self.state.open_doors:
            return f"{direction} (verschlossen)"
        return direction

    # Hilfsfunktionen für Verben
    def doors_here(self, name: str) -> list[Door]:
        """Türen im aktuellen Raum, die zu `name` passen: ID, Name, Namensende ("tür") oder Richtung."""
        found: dict[str, Door] = {}
        for direction, ex in self.room.exits.items():
            if not ex.door:
                continue
            door = self.world.doors[ex.door]
            full, wanted = match_key(door.name), match_key(name)
            if (wanted in {match_key(door.id), full, direction} or COMMANDS.direction(name) == direction
                    or (len(wanted) >= 3 and full.endswith(wanted))):
                found[door.id] = door
        return list(found.values())

    def find(self, name: str, ids: list[str]) -> str | None:
        wanted = match_key(name)
        return next((i for i in ids if match_key(self.world.items[i].name) == wanted or match_key(i) == wanted), None)

    # Eingabe
    def execute(self, text: str) -> Result:
        cmd = parse_command(text)
        res = VERBS.run(self, cmd)
        queue = deque(res.events)
        processed = 0
        while queue:
            processed += 1
            if processed > MAX_EVENTS_PER_TURN:
                res.say("(Interner Fehler: zu viele Folge-Ereignisse, Verarbeitung abgebrochen.)")
                break
            ev = queue.popleft()
            for reactor in self.reactors:
                for follow_up in reactor.react(ev, self, res):
                    res.events.append(follow_up)    # für Session und Frontends sichtbar
                    queue.append(follow_up)
        info = COMMANDS.commands.get(cmd.verb)
        if info is not None and not info.free:
            self.state.turns += 1
        return res

    def handle(self, text: str) -> str:
        return self.execute(text).text
