"""Befehle als Daten: alle Schreibweisen, Richtungswörter und Hilfetexte stehen in data/commands.json.

Neue Synonyme einfügen = nur die JSON-Datei ändern. Ein Alias darf mehrere Wörter haben
("gucke dich um") und einen Platzhalter `*` für das Objekt ("sieh dir * an").
Umlaute sind austauschbar (ö = oe, ü = ue, ä = ae, ß = ss), Groß-/Kleinschreibung egal.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COMMANDS = Path(__file__).resolve().parent / "data" / "commands.json"
# Füllwörter werden aus der Eingabe entfernt ("mit" trennt das Werkzeug ab, siehe parser)
FILLER = {"nach", "zum", "zur", "den", "die", "das", "dem", "der", "mit"}
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normalize(text: str) -> str:
    """Kleinschreibung und Umlaute vereinheitlichen, nur für den Vergleich."""
    return unicodedata.normalize("NFC", text).lower().translate(_UMLAUTS)


def match_key(text: str) -> str:
    """Vergleichsschlüssel für Item-/Türnamen: normalisiert, ohne Füllwörter ("Zauber der Nacht" = "zauber nacht"),
    denn der Parser entfernt Füllwörter aus der Eingabe."""
    return " ".join(w for w in normalize(text).split() if w not in FILLER)


@dataclass(frozen=True)
class CommandInfo:
    name: str
    group: str
    usage: str
    info: str
    aliases: tuple[str, ...]
    free: bool = False        # kostet keinen Zug (Meta-Befehle wie hilfe, karte, speichern)


@dataclass(frozen=True)
class CommandTable:
    commands: dict[str, CommandInfo]
    directions: dict[str, str]                    # normalisierte Schreibweise -> Richtung (z. B. "sued" -> "süden")
    _entries: tuple[tuple[tuple[str, ...], str], ...]   # (normalisierte Alias-Wörter, Verb), spezifischste zuerst

    def match(self, tokens: list[str]) -> tuple[str, int, int] | None:
        """Findet den passenden Befehl am Anfang der (normalisierten) Wörter.
        Ergebnis: (Verb, Start, Ende) - tokens[Start:Ende] ist das Objekt.
        Die Spezifität (Start + Wörter nach dem Objekt) sagt, wie viele Wörter zum Befehl gehören."""
        n = len(tokens)
        for alias, verb in self._entries:
            if "*" in alias:
                i = alias.index("*")
                pre, post = alias[:i], alias[i + 1:]
                end = n - len(post)
                if (tokens[:len(pre)] == list(pre) and end > len(pre)
                        and (not post or tokens[end:] == list(post))):
                    return verb, len(pre), end
            elif tokens[:len(alias)] == list(alias):
                return verb, len(alias), n
        return None

    def direction(self, word: str) -> str | None:
        return self.directions.get(normalize(word))


def load_commands(path: Path | str = DEFAULT_COMMANDS) -> CommandTable:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))    # -sig: auch Dateien mit BOM (Windows)
    except (OSError, ValueError) as e:
        raise ValueError(f"{Path(path).name}: nicht lesbar ({e})") from e
    try:
        raw_dirs = raw.pop("_directions", {})
        commands: dict[str, CommandInfo] = {}
        seen: dict[tuple[str, ...], str] = {}
        entries: list[tuple[tuple[str, ...], str]] = []
        for name, c in raw.items():
            for key in ("group", "usage", "info"):
                if not isinstance(c[key], str) or not c[key].strip():
                    raise ValueError(f"Befehl '{name}': '{key}' muss ein nichtleerer Text sein")
            if not isinstance(c["aliases"], list) or not all(isinstance(a, str) for a in c["aliases"]):
                raise ValueError(f"Befehl '{name}': 'aliases' muss eine Liste von Texten sein")
            info = CommandInfo(name, c["group"], c["usage"], c["info"], tuple(c["aliases"]),
                               free=bool(c.get("free", False)))
            commands[name] = info
            for alias in info.aliases:
                tokens = tuple(normalize(alias).split())
                if not tokens or tokens.count("*") > 1 or tokens == ("*",):
                    raise ValueError(f"Befehl '{name}': ungültiger Alias '{alias}'")
                if FILLER & set(tokens):
                    raise ValueError(f"Befehl '{name}': Alias '{alias}' enthält ein Füllwort ({sorted(FILLER & set(tokens))})")
                if tokens in seen and seen[tokens] != name:
                    raise ValueError(f"Alias '{alias}' gehört zu '{seen[tokens]}' und '{name}'")
                seen[tokens] = name
                entries.append((tokens, name))
        directions: dict[str, str] = {}
        for direction, words in raw_dirs.items():
            if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
                raise ValueError(f"Richtung '{direction}': Wörter müssen eine Liste von Texten sein")
            for w in words:
                if normalize(w) in directions and directions[normalize(w)] != direction:
                    raise ValueError(f"Richtungswort '{w}' ist doppelt vergeben")
                directions[normalize(w)] = direction
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"commands.json: fehlerhafte Daten ({e!r})") from e
    for tokens, name in seen.items():                 # ein Einzelwort-Alias darf kein Richtungswort sein
        if len(tokens) == 1 and tokens[0] in directions:
            raise ValueError(f"Alias '{tokens[0]}' von '{name}' ist zugleich ein Richtungswort")
    entries.sort(key=lambda e: (-len(e[0]), "*" not in e[0]))     # längere und Platzhalter-Aliase zuerst
    return CommandTable(commands, directions, tuple(entries))


COMMANDS = load_commands()


def cheatsheet_lines(table: CommandTable = COMMANDS, extra: list[str] | None = None, examples: int = 4) -> list[str]:
    """Kurzübersicht aller Befehle, gruppiert, mit Beispiel-Schreibweisen. `extra` = Zusatzzeilen (z. B. Tasten)."""
    lines = ["=== SPIELANLEITUNG ===",
             "Du kannst frei formulieren: 'gucke dich um', 'nimm die Laterne', 'öffne die Tür mit dem Schlüssel'.",
             "Groß-/Kleinschreibung und Umlaute (oe statt ö) sind egal."]
    groups: dict[str, list[CommandInfo]] = {}
    for info in table.commands.values():
        groups.setdefault(info.group, []).append(info)
    for group, infos in groups.items():
        lines += ["", group.upper()]
        for c in infos:
            lines.append(f"  {c.usage}")
            lines.append(f"      {c.info}")
            first = normalize(c.usage.split()[0])
            multi = [a for a in c.aliases if (" " in a or "*" in a)]
            single = [a for a in c.aliases if " " not in a and "*" not in a and len(a) > 1 and normalize(a) != first]
            alts = (multi[:2] + single)[:examples]        # Mehrwort-Beispiele zuerst, das zeigt die Freiheit
            if alts:
                lines.append("      auch: " + ", ".join(a.replace("*", "<Ding>") for a in alts))
    if extra:
        lines += [""] + extra
    return lines
