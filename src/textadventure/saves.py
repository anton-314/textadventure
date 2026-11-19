"""Spielstände: Slots als JSON-Dateien, versioniert, atomar geschrieben, plattformunabhängiger Ort."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .state import SAVE_VERSION, GameState
from .world import World

SLOT_RE = re.compile(r"[a-z0-9_-]{1,32}")
# Unter Windows reservierte Gerätenamen (auch als "con.json" unbrauchbar)
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
WORLD_ID = "burg"
MIGRATIONS: dict[int, Callable[[dict], dict]] = {}   # {1: v1_nach_v2, ...}; jede hebt "version" um 1


class SaveError(Exception):
    pass


def data_dir() -> Path:
    """TEXTADVENTURE_HOME > Windows %APPDATA% > XDG_DATA_HOME > ~/.local/share (macOS: Application Support)."""
    if env := os.environ.get("TEXTADVENTURE_HOME"):
        return Path(env).expanduser().resolve()
    if sys.platform == "win32" and (appdata := os.environ.get("APPDATA")):
        base = Path(appdata)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "textadventure"


def migrate(envelope: dict) -> dict:
    if not isinstance(envelope, dict) or not isinstance(envelope.get("version", 0), int):
        raise SaveError("Spielstand hat ein ungültiges Format.")
    version = envelope.get("version", 0)
    if version > SAVE_VERSION:
        raise SaveError(f"Spielstand stammt aus einer neueren Version ({version} > {SAVE_VERSION}).")
    while version < SAVE_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise SaveError(f"Keine Migration von Version {version}.")
        envelope = step(envelope)
        version = envelope["version"]
    return envelope


@dataclass(frozen=True)
class SlotInfo:
    slot: str
    saved_at: str
    meta: dict


class SaveStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or data_dir()) / "saves"

    def _path(self, slot: str) -> Path:
        if not SLOT_RE.fullmatch(slot) or slot in RESERVED:
            raise SaveError("Ungültiger Slot-Name (erlaubt: a-z, 0-9, _ und -, max. 32 Zeichen).")
        return self.root / f"{slot}.json"

    def save(self, slot: str, state: GameState, world: World, world_id: str = WORLD_ID) -> None:
        path = self._path(slot)
        self.root.mkdir(parents=True, exist_ok=True)
        envelope = {
            "version": SAVE_VERSION,
            "world": world_id,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "meta": {"room": world.rooms[state.location].name, "turns": state.turns},
            "state": state.to_dict(),
        }
        try:
            payload = json.dumps(envelope, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            raise SaveError(f"Zustand ist nicht speicherbar ({e}).") from e
        # Eindeutige Temp-Datei im selben Ordner, auf Platte geschrieben, dann atomar ersetzt
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=f".{slot}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            for attempt in range(3):    # Windows: Ziel kann kurz gesperrt sein (Virenscanner o. Ä.)
                try:
                    os.replace(tmp_name, path)
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
                    time.sleep(0.05)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def load(self, slot: str, world: World, world_id: str = WORLD_ID) -> GameState:
        path = self._path(slot)
        if not path.exists():
            raise SaveError(f"Spielstand '{slot}' gibt es nicht.")
        try:
            envelope = migrate(json.loads(path.read_text(encoding="utf-8")))
            if envelope.get("world", world_id) != world_id:
                raise SaveError(f"Spielstand '{slot}' gehört zu einer anderen Welt ('{envelope['world']}').")
            return GameState.from_dict(envelope["state"], world)
        except SaveError:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            raise SaveError(f"Spielstand '{slot}' ist beschädigt oder nicht lesbar ({e!r}).") from e

    def slots(self) -> list[SlotInfo]:
        infos = []
        for path in sorted(self.root.glob("*.json")) if self.root.exists() else []:
            try:
                env = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(env, dict) or not SLOT_RE.fullmatch(path.stem):
                    continue
                meta = env.get("meta")
                infos.append(SlotInfo(path.stem, str(env.get("saved_at", "?")),
                                      meta if isinstance(meta, dict) else {}))
            except (OSError, ValueError):
                continue
        return infos
