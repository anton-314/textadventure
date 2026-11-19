"""Platzhalter für die KI-Schicht.

Geplante Einsatzzwecke (noch nicht umgesetzt):
- Freitext-Eingaben in Standardbefehle übersetzen (Interpreter)
- Beschreibungen/Varianten/Dialoge generieren (Narrator)

Wichtig: Die Engine bleibt die Quelle der Wahrheit für den Spielzustand;
die KI schlägt nur Befehle oder Texte vor.
"""
from __future__ import annotations

from typing import Protocol


class Interpreter(Protocol):
    def to_command(self, text: str, context: str) -> str:
        """Übersetzt freie Eingabe in einen Standardbefehl."""
        ...


class PassthroughInterpreter:
    """Standard: gibt die Eingabe unverändert an den Regel-Parser weiter."""

    def to_command(self, text: str, context: str) -> str:
        return text
