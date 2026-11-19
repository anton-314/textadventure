"""Verben-Registry: ein Handler pro Befehl. Neue Befehle = neue Funktion mit @VERBS.register."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .events import (DoorOpened, ItemDropped, ItemExamined, ItemTaken, LoadRequested, Result,
                     RoomEntered, SaveRequested, SlotsRequested)
from .commands import COMMANDS, cheatsheet_lines
from .parser import Command

if TYPE_CHECKING:
    from .engine import Game

Handler = Callable[["Game", Command], Result]


class Registry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str) -> Callable[[Handler], Handler]:
        def deco(fn: Handler) -> Handler:
            self._handlers[name] = fn
            return fn
        return deco

    def run(self, game: "Game", cmd: Command) -> Result:
        handler = self._handlers.get(cmd.verb)
        if handler is None:
            return Result().say("Das verstehe ich nicht. (hilfe für Befehle)")
        return handler(game, cmd)

    def names(self) -> set[str]:
        return set(self._handlers)

    def help_text(self) -> str:
        """Einzeilige Kurzliste (Details: commands.cheatsheet_lines)."""
        return "Befehle: " + ", ".join(c.usage for n, c in COMMANDS.commands.items() if n in self._handlers)


VERBS = Registry()


def enter(game: "Game", room_id: str) -> Result:
    """Betritt einen Raum: setzt Zustand, meldet Event, beschreibt ihn."""
    first = room_id not in game.state.visited
    game.state.location = room_id
    game.state.visited.add(room_id)
    return Result().say(game.describe()).emit(RoomEntered(room_id, first))


@VERBS.register("go")
def go(game: "Game", cmd: Command) -> Result:
    ex = game.room.exits.get(cmd.obj)
    if not ex:
        return Result().say("Dort kommst du nicht hin.")
    if ex.door and ex.door not in game.state.open_doors:
        return Result().say(game.world.doors[ex.door].locked_text)
    return enter(game, ex.to)


@VERBS.register("look")
def look(game: "Game", cmd: Command) -> Result:
    if cmd.obj:                        # "schau laterne" wie "untersuche laterne"
        return look_at(game, cmd)
    return Result().say(game.describe())


@VERBS.register("look_at")
def look_at(game: "Game", cmd: Command) -> Result:
    item = game.find(cmd.obj, game.state.inventory + game.state.room_items[game.location])
    if item:
        return Result().say(game.world.items[item].description).emit(ItemExamined(item))
    doors = game.doors_here(cmd.obj)
    return Result().say(doors[0].description if len(doors) == 1 else "Das siehst du hier nicht.")


@VERBS.register("take")
def take(game: "Game", cmd: Command) -> Result:
    here = game.state.room_items[game.location]
    item = game.find(cmd.obj, here)
    if not item:
        return Result().say("Das gibt es hier nicht.")
    if not game.world.items[item].takeable:
        return Result().say("Das lässt sich nicht mitnehmen.")
    here.remove(item)
    game.state.inventory.append(item)
    return Result().say(f"Du nimmst: {game.world.items[item].name}.").emit(ItemTaken(item))


@VERBS.register("drop")
def drop(game: "Game", cmd: Command) -> Result:
    item = game.find(cmd.obj, game.state.inventory)
    if not item:
        return Result().say("Das hast du nicht.")
    game.state.inventory.remove(item)
    game.state.room_items[game.location].append(item)
    return Result().say(f"Du lässt {game.world.items[item].name} fallen.").emit(ItemDropped(item))


@VERBS.register("open")
def open_door(game: "Game", cmd: Command) -> Result:
    doors = game.doors_here(cmd.obj)
    if not doors:
        return Result().say("Das kannst du nicht öffnen.")
    if len(doors) > 1:
        return Result().say("Welche meinst du? " + ", ".join(d.name for d in doors))
    door = doors[0]
    if door.id in game.state.open_doors:
        return Result().say("Das ist schon offen.")
    if cmd.tool:
        held = game.find(cmd.tool, game.state.inventory)
        if not held:
            return Result().say("Das hast du nicht.")
        if held != door.key:
            return Result().say("Das passt nicht ins Schloss.")
    if door.key not in game.state.inventory:
        return Result().say(door.locked_text + " Dir fehlt der passende Schlüssel.")
    game.state.open_doors.add(door.id)
    return Result().say(door.open_text).emit(DoorOpened(door.id))


@VERBS.register("inventory")
def inventory(game: "Game", cmd: Command) -> Result:
    if not game.state.inventory:
        return Result().say("Du trägst nichts bei dir.")
    return Result().say("Du trägst: " + ", ".join(game.inventory_names()))


@VERBS.register("map")
def show_map(game: "Game", cmd: Command) -> Result:
    return Result().say("\n".join(game.map_lines()))


@VERBS.register("achievements")
def show_achievements(game: "Game", cmd: Command) -> Result:
    from .achievements import achievement_lines
    return Result().say("\n".join(achievement_lines(game)))


@VERBS.register("save")
def save(game: "Game", cmd: Command) -> Result:
    return Result().emit(SaveRequested(cmd.obj or "slot1"))


@VERBS.register("load")
def load(game: "Game", cmd: Command) -> Result:
    return Result().emit(LoadRequested(cmd.obj or "auto"))


@VERBS.register("slots")
def slots(game: "Game", cmd: Command) -> Result:
    return Result().emit(SlotsRequested())


@VERBS.register("help")
def help_(game: "Game", cmd: Command) -> Result:
    return Result().say("\n".join(cheatsheet_lines()))


@VERBS.register("quit")
def quit_(game: "Game", cmd: Command) -> Result:
    game.running = False
    return Result().say("Bis bald!")


# Schnell scheitern, wenn Befehls-Daten und Handler auseinanderlaufen
_mismatch = VERBS.names() ^ set(COMMANDS.commands)
if _mismatch:
    raise RuntimeError(f"commands.json und Verben-Registry passen nicht zusammen: {sorted(_mismatch)}")
