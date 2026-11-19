"""Terminal-Oberfläche (TUI) mit Textual: Panels, Startmenü, Farbthemen und Tastenkürzel.

Läuft in jedem Terminal unter Linux, macOS und Windows (am besten Windows Terminal).
Die Engine bleibt Quelle der Wahrheit; dieses Modul zeigt nur an und reicht Eingaben weiter.
Installation: pip install -e ".[tui]"
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.rule import Rule
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

BANNER = [
    "╔╦╗╔═╗═╗ ╦╔╦╗",
    " ║ ║╣ ╔╩╦╝ ║ ",
    " ╩ ╚═╝╩ ╚═ ╩ ",
    "╔═╗╔╦╗╦  ╦╔═╗╔╗╔╔╦╗╦ ╦╦═╗╔═╗",
    "╠═╣ ║║╚╗╔╝║╣ ║║║ ║ ║ ║╠╦╝║╣ ",
    "╩ ╩═╩╝ ╚╝ ╚═╝╝╚╝ ╩ ╚═╝╩╚═╚═╝",
]

# Farbthemen: bg Hintergrund, panel Panel-Fläche, fg Text, dim gedämpft, accent Hervorhebung,
# border Rahmen, warn Warnungen (verschlossen, Karte)
THEMES: dict[str, dict[str, str]] = {
    "green":     {"label": "Phosphor-Grün", "bg": "#050805", "panel": "#0a120b", "fg": "#33ff66",
                  "dim": "#1f9940", "accent": "#b6ffcb", "border": "#33ff66", "warn": "#ffcc33"},
    "amber":     {"label": "Bernstein", "bg": "#080600", "panel": "#120d02", "fg": "#ffb000",
                  "dim": "#a06f00", "accent": "#ffe3a3", "border": "#ffb000", "warn": "#ff6a3d"},
    "ice":       {"label": "Eis", "bg": "#050a10", "panel": "#0a131d", "fg": "#7fd4ff",
                  "dim": "#3f7ea3", "accent": "#e3f6ff", "border": "#7fd4ff", "warn": "#ffa86b"},
    "parchment": {"label": "Pergament", "bg": "#17120b", "panel": "#201912", "fg": "#e3cfa0",
                  "dim": "#8d7c58", "accent": "#fff1cf", "border": "#c9a95e", "warn": "#e0684b"},
}
THEME_ORDER = list(THEMES)

CSS = """
Screen { background: $bg; color: $fg; }
Header { background: $panel; color: $accent; text-style: bold; }
Footer { background: $panel; color: $fg; }
FooterKey { background: $panel; }
FooterKey .footer-key--key { color: $accent; background: $panel; text-style: bold; }
FooterKey .footer-key--description { color: $dim; background: $panel; }
FooterKey:hover { background: $dim; }
FooterKey:hover .footer-key--key, FooterKey:hover .footer-key--description { background: $dim; color: $bg; }
#main { height: 1fr; padding: 0 1; }
#log { border: double $border; border-title-color: $accent; border-title-style: bold; background: $bg;
       padding: 0 2; width: 1fr; scrollbar-color: $dim; scrollbar-background: $bg;
       scrollbar-size-vertical: 1; scrollbar-size-horizontal: 0; }
#side { width: 36; margin-left: 1; }
#side.hidden { display: none; }
.panel { border: round $dim; border-title-color: $fg; background: $panel; padding: 0 1; height: auto;
         min-height: 3; margin-bottom: 1; }
#place { border: round $border; color: $accent; text-style: bold; }
#inv { height: 1fr; }
#cmd { dock: bottom; margin: 0 1; border: round $border; background: $panel; color: $accent; }
#cmd.top { dock: top; }
#cmd:focus { border: heavy $accent; }
#cmd > .input--placeholder { color: $dim; }
#cmd > .input--cursor { background: $accent; color: $bg; }
MenuScreen, CheatSheetScreen { align: center middle; background: $bg 80%; }
#sheet { width: 90%; max-width: 100; height: 90%; border: double $border; background: $bg; padding: 0 2; }
#sheet-body { height: 1fr; }
#sheet-hint { dock: bottom; color: $dim; content-align: center middle; width: 100%; }
#menu { width: 52; height: auto; border: double $border; background: $bg; padding: 1 2; }
#logo, #tagline { width: 100%; content-align: center middle; text-align: center; }
#tagline { color: $dim; margin-bottom: 1; }
#menu Label { width: 100%; content-align: center middle; margin-bottom: 1; color: $accent; text-style: bold; }
#menu OptionList { background: $bg; border: none; height: auto; color: $fg; }
#menu OptionList > .option-list--option-highlighted { background: $fg; color: $bg; text-style: bold; }
#menu OptionList:focus > .option-list--option-highlighted { background: $fg; color: $bg; }
"""

ARROWS = {"norden": "↑", "süden": "↓", "osten": "→", "westen": "←", "oben": "⇑", "unten": "⇓"}
MARKS = {"[@]": "[◉]", "[?]": "[·]"}


def lerp_color(a: str, b: str, t: float) -> str:
    """Mischfarbe zwischen zwei '#rrggbb'-Farben (t=0 -> a, t=1 -> b)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def logo_text(theme: dict[str, str]) -> Text:
    """Titelbild mit Farbverlauf von hell (accent) nach gedämpft (dim)."""
    out = Text(justify="center")
    for i, line in enumerate(BANNER):
        color = lerp_color(theme["accent"], theme["fg"], i / (len(BANNER) - 1))
        out.append(line + ("\n" if i < len(BANNER) - 1 else ""), style=f"bold {color}")
    return out


def exit_text(label: str, theme: dict[str, str]) -> Text:
    """'norden' / 'osten (verschlossen)' -> Pfeil + Richtung, Verschlossenes in Warnfarbe."""
    direction = label.split(" ")[0]
    locked = "(verschlossen)" in label
    t = Text()
    t.append(ARROWS.get(direction, "•") + " ", style=theme["warn"] if locked else theme["accent"])
    t.append(direction, style=theme["warn"] if locked else theme["fg"])
    if locked:
        t.append("  ✖ verschlossen", style=theme["warn"])
    return t


def map_text(lines: list[str], theme: dict[str, str]) -> Text:
    """ASCII-Karte (mapview) in Farbe und mit schöneren Zeichen darstellen."""
    out = Text()
    for n, line in enumerate(lines):
        if n:
            out.append("\n")
        if line.startswith(("Ebene", "Treppe")):
            out.append(line, style=theme["dim"])
            continue
        for part in re.split(r"(\[.\])", line):
            if part in MARKS:
                style = f"bold {theme['accent']}" if part == "[@]" else theme["dim"]
                out.append(MARKS[part], style=style)
            elif re.fullmatch(r"\[.\]", part):
                out.append("[ ]", style=theme["fg"])
            else:
                out.append(part.replace("+", "✖").replace("-", "─").replace("|", "│"), style=theme["warn"] if "+" in part else theme["dim"])
    return out


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
        options = [Option("  Neues Spiel", id="new")]
        if self.has_game:
            options.insert(0, Option("  Weiterspielen", id="resume"))
        if self.has_autosave:
            options.append(Option("  Letzten Stand laden", id="load"))
        options.append(Option("  Beenden", id="quit"))
        with Vertical(id="menu"):
            yield Static(logo_text(self.app.theme_colors), id="logo")  # type: ignore[attr-defined]
            yield Static("· ein Text-Adventure fürs Terminal ·", id="tagline")
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
    "  F4             Farbthema wechseln (Grün, Bernstein, Eis, Pergament)",
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
        self.theme_name = THEME_ORDER[0]
        super().__init__()
        self.session = Session(world_file, interpreter=interpreter)
        self.history: list[str] = []
        self.history_pos = 0
        # Alles, was im Log steht, als (Art, Text) – so lässt es sich beim Themenwechsel neu einfärben
        self.entries: list[tuple[str, str]] = [("banner", "")]

    @property
    def game(self) -> Game | None:
        return self.session.game

    @property
    def theme_colors(self) -> dict[str, str]:
        return THEMES[self.theme_name]

    def get_css_variables(self) -> dict[str, str]:
        return {**super().get_css_variables(), **{k: v for k, v in self.theme_colors.items() if k != "label"}}

    # ---------- Aufbau ----------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield RichLog(id="log", wrap=True, min_width=20, markup=False, highlight=False)
            with Vertical(id="side"):
                yield Static("", id="place", classes="panel")
                yield Static("", id="exits", classes="panel")
                yield Static("", id="map", classes="panel")
                yield Static("", id="inv", classes="panel")
        yield Input(placeholder="Was tust du?  (F1 zeigt alle Befehle)", id="cmd", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log").border_title = " ✦ Geschichte ✦ "
        self.query_one("#place").border_title = " ⌂ Ort "
        self.query_one("#exits").border_title = " ➤ Ausgänge "
        self.query_one("#map").border_title = " ▦ Karte "
        self.query_one("#inv").border_title = " ◆ Inventar "
        self.query_one("#cmd").border_title = " ❯ "
        self._render_log()
        self.action_menu()

    # ---------- Ausgabe ----------
    @property
    def log_view(self) -> RichLog:
        return self.query_one("#log", RichLog)

    def _render_entry(self, kind: str, text: str) -> None:
        t = self.theme_colors
        log = self.log_view
        if kind == "banner":
            log.write(Text(""))
            log.write(logo_text(t))
        elif kind == "echo":
            log.write(Text(""))
            log.write(Text("❯ " + text, style=f"italic {t['dim']}"))
        elif kind == "info":
            log.write(Text(text, style=t["dim"]))
        else:
            self._write_game_text(text)

    def _render_log(self) -> None:
        self.log_view.clear()
        for kind, text in self.entries:
            self._render_entry(kind, text)

    def _add(self, kind: str, text: str = "") -> None:
        self.entries.append((kind, text))
        self._render_entry(kind, text)

    def _write_game_text(self, text: str) -> None:
        t = self.theme_colors
        log = self.log_view
        for line in text.split("\n"):
            if line.startswith("== ") and line.endswith(" =="):
                log.write(Text(""))
                log.write(Rule(Text(line.strip("= ").upper(), style=f"bold {t['accent']}"),
                               characters="═", style=t["border"]), expand=True)
            elif line.startswith("[Erfolg]"):
                log.write(Text("★ " + line.removeprefix("[Erfolg]").strip(), style=f"bold {t['warn']}"))
            elif line.startswith("Hier liegt:"):
                log.write(Text("◆ " + line, style=t["accent"]))
            elif line.startswith("Ausgänge:"):
                log.write(Text("➤ " + line, style=t["dim"]))
            else:
                log.write(Text(line, style=t["fg"]))

    def _update_side(self) -> None:
        g = self.game
        t = self.theme_colors
        place = self.query_one("#place", Static)
        exits = self.query_one("#exits", Static)
        inv = self.query_one("#inv", Static)
        map_panel = self.query_one("#map", Static)
        if not g:
            place.update(""), exits.update(""), inv.update(""), map_panel.update("")
            self.sub_title = ""
            return
        map_panel.update(map_text(self.session.map_lines(), t))
        place.update(Text(g.room.name))
        labels = g.exit_labels()
        exits.update(Text("\n").join(exit_text(x, t) for x in labels) if labels else Text("–"))
        names = g.inventory_names()
        if names:
            inv.update(Text("\n").join(Text.assemble(("◇ ", t["accent"]), (n, t["fg"])) for n in names))
        else:
            inv.update(Text("leer", style=t["dim"]))
        self.sub_title = f"{g.room.name} · Zug {g.state.turns}"

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
        self.entries = [("game", res.text)]
        self._render_log()
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
            self._add("echo", "erfolge")
            self._add("game", "\n".join(achievement_lines(self.game)))

    def action_toggle_side(self) -> None:
        self.query_one("#side").toggle_class("hidden")

    def action_toggle_dock(self) -> None:
        self.query_one("#cmd").toggle_class("top")

    def action_toggle_theme(self) -> None:
        self.theme_name = THEME_ORDER[(THEME_ORDER.index(self.theme_name) + 1) % len(THEME_ORDER)]
        for name in THEME_ORDER:                       # Klasse pro Thema, z. B. "amber" (für CSS und Tests)
            self.set_class(name == self.theme_name and name != THEME_ORDER[0], name)
        self.refresh_css()
        self._render_log()
        self._update_side()
        self.notify(self.theme_colors["label"], title="Farbthema", timeout=2, markup=False)

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
        self._add("echo", text)
        res = self.session.submit(text)
        self._add("game", res.text)
        for ev in res.events:
            if isinstance(ev, AchievementUnlocked):
                name = next((a.name for a in self.game.world.achievements if a.id == ev.id), ev.id)
                self.notify(name, title="★ Erfolg freigeschaltet", timeout=6, markup=False)
        self._update_side()
        if not self.session.running:
            self._add("info", "— Spiel beendet. Esc öffnet das Menü. —")
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
