"""MTG Arena draft helper.

    python run.py                      watch Arena's log and show the overlay
    python run.py --console            print suggestions in the terminal instead
    python run.py --set DSK            force the set code (if it isn't detected)
    python run.py --replay saved.log   replay a saved log (no Arena needed)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from draft_helper import config
from draft_helper.app import DraftHelper


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pick suggestions for MTG Arena drafts.")
    p.add_argument("--log", type=Path, default=None, help="path to Player.log (default: Arena's standard location)")
    p.add_argument("--set", dest="set_code", default="", help="set code to use for ratings, e.g. DSK")
    p.add_argument("--format", default="", help="17Lands format: PremierDraft, QuickDraft, TradDraft")
    p.add_argument("--ratings-file", type=Path, default=None, help="use a saved 17Lands ratings JSON file")
    p.add_argument("--arena-db-dir", type=Path, action="append", default=None,
                   help="folder containing Raw_CardDatabase_*.mtga (if Arena is installed somewhere unusual)")
    p.add_argument("--offline", action="store_true", help="don't download anything; use cached data only")
    p.add_argument("--replay", type=Path, default=None, help="replay a saved log file instead of watching")
    p.add_argument("--replay-delay", type=float, default=0.0, help="seconds between replayed draft updates")
    p.add_argument("--console", action="store_true", help="print to the terminal instead of opening a window")
    args = p.parse_args(argv)

    helper = DraftHelper(set_override=args.set_code, format_override=args.format,
                         ratings_file=args.ratings_file, arena_db_dirs=args.arena_db_dir,
                         offline=args.offline)
    if helper.db.source != "none":
        print(f"Card data: {helper.db.source}")
    else:
        print("Arena card database not found; card names will come from 17Lands.")

    if args.replay:
        helper.replay(args.replay, args.replay_delay)
    else:
        log = args.log or config.default_log_path()
        print(f"Watching {log}")
        helper.watch(log)

    use_console = args.console
    if not use_console:
        try:
            from draft_helper.overlay import Overlay
        except ImportError:
            print("Tkinter isn't available; falling back to console output.")
            use_console = True
    if use_console:
        from draft_helper.console import run_console
        run_console(helper)
    else:
        Overlay(helper).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
