from __future__ import annotations

import argparse
import sys

from app.config import get_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the Werewolf Textual TUI.")
    parser.add_argument("--game-id", default=None)
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="UI language, default: zh")
    args = parser.parse_args()
    try:
        from app.ui.app import WerewolfApp
    except ModuleNotFoundError as exc:
        if exc.name == "textual":
            print("Textual is not installed. Install dependencies first, then run the TUI.", file=sys.stderr)
            raise SystemExit(1) from exc
        raise
    paths = get_paths()
    app = WerewolfApp(database=paths.database, game_id=args.game_id, language=args.lang)
    app.run()


if __name__ == "__main__":
    main()
