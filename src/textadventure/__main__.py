from __future__ import annotations

import sys

from .session import Session


def main() -> None:
    for stream in (sys.stdout, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")   # Windows-Konsolen
    session = Session()
    print(session.new_game().text)
    while session.running:
        try:
            text = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        print(session.submit(text).text)


if __name__ == "__main__":
    main()
