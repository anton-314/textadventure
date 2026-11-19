"""Terminal-Oberfläche (TUI) mit Textual: Panels, Startmenü und Tastenkürzel im Retro-Look.

Läuft in jedem Terminal unter Linux, macOS und Windows (am besten Windows Terminal).
Die Engine bleibt Quelle der Wahrheit; dieses Modul zeigt nur an und reicht Eingaben weiter.
Installation: pip install -e ".[tui]"
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from .ai import Interpreter
from .engine import Game
from .achievements import achievement_lines
from .commands import cheatsheet_lines
from .events import AchievementUnlocked, Result
from .session import AUTOSAVE, Session
from .world import DEFAULT_WORLD

WORLD_FILE = DEFAULT_WORLD

BANNER = r"""
 _____ _____ __ __ _____
|_   _| ____|\ \/ /_   _|
  | | |  _|  \  /  | |
  | | | |___ /  \  | |
  |_| |_____/_/\_\ |_|     A D V E N T U R E
"""

CSS = """
Screen { background: #050805; color: #33ff66; }
Header, Footer { background: #0b140b; color: #33ff66; }
Footer > .footer--key { background: #33ff66; color: #050805; }
#main { height: 1fr; }
#log { border: heavy #33ff66; border-title-color: #33ff66; background: #050805; padding: 0 1; width: 1fr; }
#side { width: 34; }
#side.hidden { display: none; }
.panel { border: round #1f9940; border-title-color: #33ff66; padding: 0 1; height: auto; min-height: 3; margin-bottom: 1; }
#inv { height: 1fr; }
#cmd { dock: bottom; border: heavy #33ff66; background: #050805; color: #33ff66; }
#cmd.top { dock: top; }
#cmd:focus { border: heavy #aaffcc; }
MenuScreen, CheatSheetScreen { align: center middle; }
#sheet { width: 90%; max-width: 100; height: 90%; border: heavy #33ff66; background: #050805; padding: 0 2; }
#sheet-body { height: 1fr; }
#sheet-hint { dock: bottom; color: #1f9940; content-align: center middle; width: 100%; }
#menu { width: 44; height: auto; border: heavy #33ff66; background: #050805; padding: 1 2; }
#menu Label { width: 100%; content-align: center middle; margin-bottom: 1; }
#menu OptionList { background: #050805; border: none; height: auto; }
App.amber Screen, App.amber #menu, App.amber #log, App.amber #cmd { color: #ffb000; }
App.amber #log, App.amber #cmd, App.amber #menu, App.amber #sheet { border: heavy #ffb000; }
App.amber .panel { border: round #b37a00; }
App.amber Header, App.amber Footer { color: #ffb000; }
App.amber Footer > .footer--key { background: #ffb000; color: #050805; }
"""


class MenuScreen(ModalScreen[str]):
    BINDINGS = [
        Binding("escape", "close", "Zurück"),
        # WASD gilt im Menü wie die Pfeiltasten (nur hier, nicht im Eingabefeld des Spiels)
        Binding("w", "cursor_up", show=False),
        Binding("s", "cursor_down", show=False),
        Binding("d", "select", show=False),
        Binding("a", "close", show=False),
    ]

    def __init__(self, has_game: bool, has_autosave: bool = False) -> None:
        super().__init__()
        self.has_game = has_game
        self.has_autosave = has_autosave

    def compose(self) -> ComposeResult:
        options = [Option("Neues Spiel", id="new")]
        if self.has_game:
            options.insert(0, Option("Weiterspielen", id="resume"))
        if self.has_autosave:
            options.append(Option("Letzten Stand laden", id="load"))
        options.append(Option("Beenden", id="quit"))
        with Vertical(id="menu"):
            yield Label("— HAUPTMENÜ —")
            yield OptionList(*options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_close(self) -> None:
        self.dismiss("resume")

    def action_cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_select(self) -> None:
        self.query_one(OptionList).action_select()


KEY_HELP = [
    "TASTEN (Oberfläche)",
    "  Esc            Hauptmenü (Neues Spiel, Weiterspielen, Beenden)",
    "  Strg+N         Neues Spiel",
    "  F1             Diese Hilfe",
    "  F2             Seitenleiste ein/aus",
    "  F3             Eingabezeile oben/unten",
    "  F4             Farbe Grün/Bernstein",
    "  F5             Erfolge anzeigen",
    "  Pfeil hoch/runter   frühere Befehle",
    "  Strg+Q         Beenden",
    "  Im Menü: W/S = hoch/runter, D = auswählen, A = zurück",
]


class CheatSheetScreen(ModalScreen[None]):
    """Scrollbare Übersicht aller Befehle und Tasten (aus commands.json erzeugt)."""

    BINDINGS = [
        Binding("escape", "close", "Schließen"),
        Binding("f1", "close", "Schließen"),
        Binding("q", "close", "Schließen", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="sheet"):
            with VerticalScroll(id="sheet-body"):
                yield Static(Text("\n".join(cheatsheet_lines(extra=KEY_HELP))), id="sheet-text")
            yield Label("Pfeiltasten scrollen · Esc / F1 schließt", id="sheet-hint")

    def action_close(self) -> None:
        self.dismiss(None)


class AdventureApp(App):
    CSS = CSS
    TITLE = "Textadventure"
    BINDINGS = [
        Binding("escape", "menu", "Menü"),
        Binding("ctrl+n", "new_game", "Neues Spiel"),
        Binding("f1", "help", "Hilfe / Befehle"),
        Binding("f5", "achievements", "Erfolge"),
        Binding("f2", "toggle_side", "Seitenleiste"),
        Binding("f3", "toggle_dock", "Eingabe oben/unten"),
        Binding("f4", "toggle_theme", "Farbe"),
        Binding("ctrl+q", "quit", "Beenden"),
    ]

    def __init__(self, world_file: Path = WORLD_FILE, interpreter: Interpreter | None = None) -> None:
        super().__init__()
        self.session = Session(world_file, interpreter=interpreter)
        self.history: list[str] = []
        self.history_pos = 0

    @property
    def game(self) -> Game | None:
        return self.session.game

    # ---------- Aufbau ----------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield RichLog(id="log", wrap=True, markup=False, highlight=False)
            with Vertical(id="side"):
                yield Static("", id="place", classes="panel")
                yield Static("", id="exits", classes="panel")
                yield Static("", id="map", classes="panel")
                yield Static("", id="inv", classes="panel")
        yield Input(placeholder="Was tust du?", id="cmd", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log").border_title = " Geschichte "
        self.query_one("#place").border_title = " Ort "
        self.query_one("#exits").border_title = " Ausgänge "
        self.query_one("#map").border_title = " Karte "
        self.query_one("#inv").border_title = " Inventar "
        self.query_one("#cmd").border_title = " > "
        self._show_banner()
        self.action_menu()

    # ---------- Ausgabe ----------
    @property
    def log_view(self) -> RichLog:
        return self.query_one("#log", RichLog)

    def _show_banner(self) -> None:
        self.log_view.clear()
        self.log_view.write(Text(BANNER, style="bold"))

    def _write_game_text(self, text: str) -> None:
        for line in text.split("\n"):
            if line.startswith("== ") and line.endswith(" =="):
                self.log_view.write(Text(""))
                self.log_view.write(Text(line.strip("= ").upper(), style="bold underline"))
            elif line.startswith("[Erfolg]"):
                self.log_view.write(Text(line, style="bold"))
            elif line.startswith(("Ausgänge:", "Hier liegt:")):
                self.log_view.write(Text(line, style="dim"))
            else:
                self.log_view.write(Text(line))

    def _update_side(self) -> None:
        g = self.game
        place = self.query_one("#place", Static)
        exits = self.query_one("#exits", Static)
        inv = self.query_one("#inv", Static)
        map_panel = self.query_one("#map", Static)
        if not g:
            place.update(""), exits.update(""), inv.update(""), map_panel.update("")
            return
        map_panel.update(Text("\n".join(self.session.map_lines())))
        place.update(Text(g.room.name))
        exits.update(Text("\n".join(g.exit_labels()) or "–"))
        inv.update(Text("\n".join(g.inventory_names()) or "leer", style="" if g.inventory else "dim"))

    # ---------- Aktionen ----------
    def action_menu(self) -> None:
        if isinstance(self.screen, MenuScreen):
            return
        has_auto = any(s.slot == AUTOSAVE for s in self.session.store.slots())
        self.push_screen(MenuScreen(has_game=self.session.running, has_autosave=has_auto), self._on_menu)

    def _on_menu(self, choice: str | None) -> None:
        if choice == "new":
            self.action_new_game()
        elif choice == "load":
            self._start(self.session.load(AUTOSAVE))
        elif choice == "quit":
            self.exit()
        else:
            self.query_one("#cmd", Input).focus()

    def action_new_game(self) -> None:
        self._start(self.session.new_game())

    def _start(self, res: Result) -> None:
        self.history.clear()
        self.history_pos = 0
        self.log_view.clear()
        self._write_game_text(res.text)
        cmd = self.query_one("#cmd", Input)
        cmd.disabled = not self.session.running
        cmd.value = ""
        cmd.focus()
        self._update_side()

    def action_help(self) -> None:
        if not isinstance(self.screen, (CheatSheetScreen, MenuScreen)):
            self.push_screen(CheatSheetScreen())

    def action_achievements(self) -> None:
        if self.game:
            self.log_view.write(Text(""))
            self._write_game_text("\n".join(achievement_lines(self.game)))

    def action_toggle_side(self) -> None:
        self.query_one("#side").toggle_class("hidden")

    def action_toggle_dock(self) -> None:
        self.query_one("#cmd").toggle_class("top")

    def action_toggle_theme(self) -> None:
        self.toggle_class("amber")

    # ---------- Eingabe ----------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if text:
            self.submit(text)

    def submit(self, text: str) -> None:
        if not self.game:
            return
        self.history.append(text)
        self.history_pos = len(self.history)
        self.log_view.write(Text(""))
        self.log_view.write(Text("> " + text, style="dim italic"))
        res = self.session.submit(text)
        self._write_game_text(res.text)
        for ev in res.events:
            if isinstance(ev, AchievementUnlocked):
                name = next((a.name for a in self.game.world.achievements if a.id == ev.id), ev.id)
                self.notify(name, title="Erfolg freigeschaltet", timeout=6, markup=False)
        self._update_side()
        if not self.session.running:
            self.log_view.write(Text("— Spiel beendet. Esc öffnet das Menü. —", style="dim"))
            self.query_one("#cmd", Input).disabled = True

    def on_key(self, event) -> None:
        cmd = self.query_one("#cmd", Input)
        if event.key in ("up", "down") and cmd.has_focus and self.history:
            step = -1 if event.key == "up" else 1
            self.history_pos = max(0, min(len(self.history), self.history_pos + step))
            cmd.value = self.history[self.history_pos] if self.history_pos < len(self.history) else ""
            cmd.cursor_position = len(cmd.value)
            event.stop()


def main() -> None:
    AdventureApp().run()


if __name__ == "__main__":
    main()
