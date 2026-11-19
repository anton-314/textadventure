"""Session: die einzige Schnittstelle, die Frontends (Terminal, TUI) brauchen."""
from __future__ import annotations

from pathlib import Path

from .ai import Interpreter, PassthroughInterpreter
from .engine import Game, Reactor
from .events import LoadRequested, Result, SaveRequested, SlotsRequested
from .saves import SaveError, SaveStore
from .state import GameState
from .world import DEFAULT_WORLD, World

AUTOSAVE = "auto"


class Session:
    def __init__(self, world_file: Path = DEFAULT_WORLD, store: SaveStore | None = None,
                 interpreter: Interpreter | None = None, reactors: tuple[Reactor, ...] = ()) -> None:
        self.world = World.load(world_file)
        self.store = store or SaveStore()
        self.interpreter = interpreter or PassthroughInterpreter()
        # Reactors müssen zustandslos sein: aller Spielzustand gehört in GameState (wird sonst nicht gespeichert)
        self.reactors = reactors
        self.game: Game | None = None

    @property
    def running(self) -> bool:
        return self.game is not None and self.game.running

    def new_game(self) -> Result:
        self._keep_previous_autosave()
        self.game = Game(self.world, reactors=self.reactors)
        return Result().say(self.game.describe())

    def _keep_previous_autosave(self) -> None:
        """Ein neues Spiel soll den letzten Autosave nicht sofort überschreiben: er bleibt als 'auto-prev'."""
        try:
            state = self.store.load(AUTOSAVE, self.world)
            self.store.save("auto-prev", state, self.world)
        except (SaveError, OSError):
            pass

    def load(self, slot: str) -> Result:
        try:
            state = self.store.load(slot, self.world)
        except SaveError as e:
            return Result().say(str(e))
        self.game = Game(self.world, state, self.reactors)
        return Result().say(f"Spielstand '{slot}' geladen.").say(self.game.describe())

    def save(self, slot: str) -> Result:
        if not self.game:
            return Result().say("Es läuft kein Spiel.")
        try:
            self.store.save(slot, self.game.state, self.world)
        except (SaveError, OSError) as e:
            return Result().say(f"Speichern fehlgeschlagen: {e}")
        return Result().say(f"Gespeichert: '{slot}'.")

    def map_lines(self) -> list[str]:
        return self.game.map_lines() if self.game else []

    def achievement_lines(self) -> list[str]:
        from .achievements import achievement_lines
        return achievement_lines(self.game) if self.game else []

    def slot_lines(self) -> list[str]:
        slots = self.store.slots()
        if not slots:
            return ["Keine Spielstände vorhanden."]
        return [f"{s.slot}  –  {s.meta.get('room', '?')}, Zug {s.meta.get('turns', '?')}, {s.saved_at}"
                for s in slots]

    def submit(self, text: str) -> Result:
        if not self.game:
            return Result().say("Es läuft kein Spiel.")
        if not text.strip():
            return Result()
        command = self.interpreter.to_command(text, self.game.describe())
        turns_before = self.game.state.turns
        res = self.game.execute(command)
        for ev in res.events:
            if isinstance(ev, SaveRequested):
                res.lines.extend(self.save(ev.slot).lines)
            elif isinstance(ev, LoadRequested):
                res.lines.extend(self.load(ev.slot).lines)
                break   # Zustand wurde ersetzt, restliche Events sind hinfällig
            elif isinstance(ev, SlotsRequested):
                res.lines.extend(self.slot_lines())
        # Autosave nur, wenn sich der Spielstand wirklich verändert hat
        if self.game.running and self.game.state.turns != turns_before and not any(
                isinstance(e, (SaveRequested, LoadRequested, SlotsRequested)) for e in res.events):
            self.store_autosave(res)
        return res

    def store_autosave(self, res: Result) -> None:
        try:
            self.store.save(AUTOSAVE, self.game.state, self.world)
            self._autosave_warned = False
        except (SaveError, OSError) as e:
            if not getattr(self, "_autosave_warned", False):   # einmal warnen, dann still
                res.say(f"(Autosave fehlgeschlagen: {e})")
                self._autosave_warned = True
