# textadventure (Arbeitstitel)

Ein klassisches Text-Adventure fürs Terminal. Idee: KI übernimmt die Fleißarbeit
(viele Kombinationen, Beschreibungen, Freitext-Eingaben), die Engine hält den Spielzustand.

## Starten

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
textadventure          # einfaches Terminal-Spiel
pip install -e ".[tui]"
textadventure-tui      # Vollbild-Oberfläche (Panels, Menü, Retro-Look), Linux/Windows/macOS
pytest
```

TUI-Tasten: Esc Menü · Strg+N neues Spiel · F1 Hilfe · F2 Seitenleiste · F3 Eingabe oben/unten · F4 Farbthema (Grün, Bernstein, Eis, Pergament) · Strg+Q Beenden

## Struktur

- `src/textadventure/data/world.json` – Räume, Türen und Gegenstände (reine Daten, derzeit Platzhalter-Story)
- `world.py` – unveränderliche Weltdaten + Laden/Validierung
- `state.py` – veränderlicher, serialisierbarer Spielzustand (`GameState`)
- `events.py` – Ereignisse (`ItemTaken`, `RoomEntered`, …) und `Result`
- `verbs.py` – Befehls-Registry, ein Handler pro Befehl
- `commands.py` + `data/commands.json` – alle Befehle, Schreibweisen (Synonyme), Richtungswörter und Hilfetexte als Daten
- `parser.py` – Eingabe -> Befehl
- `engine.py` – Spiellogik ohne I/O: `Game.execute(text) -> Result`; Reactors reagieren auf Events
- `saves.py` – Spielstände (Slots, versioniert, atomar), Ort: `%APPDATA%` / `~/.local/share` / `TEXTADVENTURE_HOME`
- `session.py` – einzige Schnittstelle für Frontends (Spiel, Laden/Speichern, Autosave)
- `__main__.py` – einfaches Terminal-Frontend · `tui.py` – Textual-Frontend
- `ai.py` – Platzhalter für die KI-Anbindung
- `tests/` – pytest

Spielbefehle zum Speichern: `speichere <Slot>`, `lade <Slot>`, `spielstände`. Autosave liegt im Slot `auto`;
ein neues Spiel sichert den letzten Autosave als `auto-prev`.

Abhängigkeitsrichtung: Frontends -> Session -> Engine -> Verben/Zustand/Welt. Nichts darunter kennt ein Frontend.

## Befehle und Synonyme erweitern

Alle Schreibweisen stehen in `src/textadventure/data/commands.json`, Code muss dafür nicht geändert werden.
Neuer Alias = ein Eintrag in der `aliases`-Liste des Befehls:

- Mehrere Wörter sind erlaubt: `"gucke dich um"`
- `*` ist der Platzhalter für das Objekt: `"sieh dir * an"` -> `sieh dir die Laterne an` = `untersuche laterne`
- Umlaute sind egal (`oeffne` = `öffne`), Groß-/Kleinschreibung ebenfalls
- Füllwörter (`nach zum zur den die das dem der mit`) nicht in Aliase schreiben, sie werden vor dem Vergleich entfernt
- Richtungswörter (`runter`, `hoch`, ...) stehen unter `_directions`

Die Spielanleitung (`hilfe` im Spiel, `F1` in der TUI) wird aus derselben Datei erzeugt (`group`, `usage`, `info`).
Ein neuer Befehl braucht zusätzlich einen Handler mit `@VERBS.register("name")` in `verbs.py`;
beim Start wird geprüft, dass Daten und Handler zusammenpassen.
