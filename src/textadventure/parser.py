"""Parser: Freitext -> Befehl. Die Schreibweisen stehen in data/commands.json (siehe commands.py).

Später kann hier eine KI-Schicht (siehe ai.py) vorgeschaltet werden, die
freie Eingaben in diese Standardbefehle übersetzt.
"""
from __future__ import annotations

from typing import NamedTuple

from .commands import COMMANDS, FILLER, normalize


def _strip(word: str) -> str:
    """Satzzeichen am Wortende ("laterne." / "hilfe?") entfernen; ein einzelnes "?" bleibt als Befehl."""
    return word if word == "?" else word.rstrip(".,!?;:")


class Command(NamedTuple):
    verb: str
    obj: str = ""
    tool: str = ""      # Ding nach "mit"


def parse_command(text: str) -> Command:
    return Command(*parse_with_tool(text))


def parse_with_tool(text: str) -> tuple[str, str, str]:
    """Liefert (Verb, Objekt, Werkzeug); das Werkzeug steht nach "mit" ("öffne tür mit schlüssel")."""
    raw = [_strip(w) for w in text.lower().strip().split()]
    raw = [w for w in raw if w]
    tool_words: list[str] = []
    if "mit" in raw[1:]:
        cut = raw.index("mit", 1)
        raw, tool_words = raw[:cut], raw[cut + 1:]
    words = [w for w in raw if w not in FILLER]
    tool_list = [w for w in tool_words if w not in FILLER]
    if not words:
        return ("", "", " ".join(tool_list))
    # Eine Richtung allein ("norden", "n", "runter") bedeutet "gehe <Richtung>"
    direction = COMMANDS.direction(words[0])
    if direction and len(words) == 1:
        return ("go", direction, " ".join(tool_list))
    match = COMMANDS.match([normalize(w) for w in words])
    if len(tool_list) >= 2:
        # "lege Laterne mit Schlüssel ab": das Schlusswort ("ab") gehört zum Befehl, nicht zum Werkzeug.
        # Es gewinnt, wenn dadurch mehr Wörter zum Befehl gehören als ohne.
        trailing = words + [tool_list[-1]]
        alt = COMMANDS.match([normalize(w) for w in trailing])
        if alt is not None and (match is None or _specificity(alt, len(trailing)) > _specificity(match, len(words))):
            match, words, tool_list = alt, trailing, tool_list[:-1]
    tool = " ".join(tool_list)
    if match is None:
        return ("", " ".join(words[1:]), tool)
    verb, start, end = match
    obj = " ".join(words[start:end])
    if verb == "go":
        obj = COMMANDS.direction(obj) or obj
    return (verb, obj, tool)


def parse(text: str) -> tuple[str, str]:
    verb, obj, _ = parse_with_tool(text)
    return (verb, obj)


def _specificity(match: tuple[str, int, int], n: int) -> int:
    _, start, end = match
    return start + (n - end)
