"""ASCII-Karte: Layout aus den Ausgängen (BFS) und Rendering als reine Funktionen.

Nur ASCII-Zeichen (Windows-Konsolen). Beide Frontends nutzen `render`.
  [@] du  [ ] besucht  [?] bekannt, aber unerforscht   - | offener Weg   + verschlossene Tür
"""
from __future__ import annotations

from collections import deque

from .world import World

# Richtung -> (dx, dy, dz); Norden ist oben auf der Karte
DIRS = {"norden": (0, -1, 0), "süden": (0, 1, 0), "osten": (1, 0, 0), "westen": (-1, 0, 0),
        "oben": (0, 0, 1), "unten": (0, 0, -1)}
Pos = tuple[int, int, int]


def layout(world: World) -> dict[str, Pos]:
    """Räume auf ein 3D-Gitter legen (BFS ab dem Startraum). Manuelle `map.pos` hat Vorrang und wird
    nicht gegen die Richtungslogik geprüft; Wege, die ihr widersprechen, ergeben aber einen Fehler.
    Widersprüche (zwei Räume auf einer Zelle, inkonsistente Wege) -> ValueError."""
    pos: dict[str, Pos] = {}
    taken: dict[Pos, str] = {}

    def place(room_id: str, p: Pos) -> None:
        if p in taken and taken[p] != room_id:
            raise ValueError(f"Karte: '{room_id}' und '{taken[p]}' liegen beide auf {p}")
        pos[room_id] = p
        taken[p] = room_id

    for rid, room in world.rooms.items():     # manuelle Positionen zuerst
        if room.pos is not None:
            place(rid, room.pos)
    if world.start not in pos:
        place(world.start, (0, 0, 0))
    # Auch Räume mit manueller Position starten eine Suche (Räume dahinter wären sonst "unerreichbar")
    manual = [rid for rid, room in world.rooms.items() if room.pos is not None]
    queue = deque([world.start, *[r for r in manual if r != world.start]])
    seen = set(queue)
    while queue:
        rid = queue.popleft()
        for direction, ex in world.rooms[rid].exits.items():
            if direction not in DIRS:
                continue
            dx, dy, dz = DIRS[direction]
            x, y, z = pos[rid]
            expected = (x + dx, y + dy, z + dz)
            if ex.to in pos:
                if pos[ex.to] != expected and world.rooms[ex.to].pos is None:
                    raise ValueError(f"Karte: Weg '{direction}' von '{rid}' nach '{ex.to}' passt nicht zum Layout")
            else:
                place(ex.to, expected)
            if ex.to not in seen:
                seen.add(ex.to)
                queue.append(ex.to)
    unreachable = set(world.rooms) - set(pos)
    for rid in sorted(unreachable):           # nicht erreichbare Räume brauchen eine manuelle Position
        raise ValueError(f"Karte: Raum '{rid}' ist nicht erreichbar und hat keine 'map.pos'")
    return pos


def render(world: World, pos: dict[str, Pos], visited: set[str], current: str,
           open_doors: set[str], floor: int | None = None,
           max_width: int = 30, max_height: int = 15) -> list[str]:
    """Karte der Ebene `floor` (Standard: Ebene des aktuellen Raums). Gezeigt werden besuchte Räume
    und die über deren Ausgänge bekannten Nachbarn."""
    z = pos[current][2] if floor is None else floor
    known: dict[str, bool] = {}               # Raum -> besucht?
    for rid in visited:
        known[rid] = True
        for direction, ex in world.rooms[rid].exits.items():
            known.setdefault(ex.to, False)
    cells = {pos[r][:2]: r for r in known if r in pos and pos[r][2] == z}
    if not cells:
        return [f"Ebene {z}: (nichts bekannt)"]
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    x0, y0 = min(xs), min(ys)
    width, height = (max(xs) - x0) * 4 + 3, (max(ys) - y0) * 2 + 1
    canvas = [[" "] * width for _ in range(height)]

    def put(cx: int, cy: int, text: str) -> None:
        for i, ch in enumerate(text):
            canvas[cy][cx + i] = ch

    for (x, y), rid in cells.items():
        mark = "@" if rid == current else (" " if known[rid] else "?")
        put((x - x0) * 4, (y - y0) * 2, f"[{mark}]")
    for (x, y), rid in cells.items():
        if not known[rid]:
            continue
        for direction, ex in world.rooms[rid].exits.items():
            if direction not in ("osten", "süden") or ex.to not in pos:
                continue
            tx, ty, tz = pos[ex.to]
            dx, dy, _ = DIRS[direction]
            if tz != z or (tx, ty) != (x + dx, y + dy) or (tx, ty) not in cells:
                continue
            closed = bool(ex.door) and ex.door not in open_doors
            if direction == "osten":
                put((x - x0) * 4 + 3, (y - y0) * 2, "+" if closed else "-")
            else:
                put((x - x0) * 4 + 1, (y - y0) * 2 + 1, "+" if closed else "|")
    # Verbindungen, die nur von der anderen Seite bekannt sind (Westen/Norden)
    for (x, y), rid in cells.items():
        if not known[rid]:
            continue
        for direction, ex in world.rooms[rid].exits.items():
            if direction not in ("westen", "norden") or ex.to not in pos:
                continue
            tx, ty, tz = pos[ex.to]
            dx, dy, _ = DIRS[direction]
            if tz != z or (tx, ty) != (x + dx, y + dy) or (tx, ty) not in cells:
                continue
            closed = bool(ex.door) and ex.door not in open_doors
            ch = "+" if closed else ("-" if direction == "westen" else "|")
            if direction == "westen":
                put((tx - x0) * 4 + 3, (ty - y0) * 2, ch)
            else:
                put((tx - x0) * 4 + 1, (ty - y0) * 2 + 1, ch)
    rows = ["".join(row).rstrip() for row in canvas]
    # Zu große Karten: Ausschnitt um den aktuellen Raum (Seitenleiste ist schmal)
    if current in pos and pos[current][2] == z and (width > max_width or height > max_height):
        cx, cy = (pos[current][0] - x0) * 4 + 1, (pos[current][1] - y0) * 2
        left = min(max(0, cx - max_width // 2), max(0, width - max_width))
        top = min(max(0, cy - max_height // 2), max(0, height - max_height))
        rows = [r[left:left + max_width].rstrip() for r in rows[top:top + max_height]]
    lines = [f"Ebene {z}"] + rows
    if pos.get(current, (0, 0, None))[2] == z:     # Treppen gehören zum aktuellen Raum, nicht zu fremden Ebenen
        cur = world.rooms[current]
        stairs = [d for d in ("oben", "unten") if d in cur.exits]
        if stairs:
            lines.append("Treppe: " + ", ".join(stairs))
    return lines
