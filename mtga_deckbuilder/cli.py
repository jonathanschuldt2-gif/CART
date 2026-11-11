"""Command-line helpers.

  python cli.py update-cards [--file default-cards.json]   download/load Scryfall data
  python cli.py import collection.csv [--add]               import a collection export
  python cli.py load-meta                                    import data/meta/<format>/*.txt
  python cli.py build standard [--top 5]                     print best decks (Arena text)
  python cli.py export collection.csv                        export collection (.csv/.json/.txt)
"""
import argparse
from pathlib import Path

from app import exporters, services
from app.cards.scryfall import download_bulk, iter_bulk_file, load_cards
from app.database import SessionLocal, init_db
from app.engine.builder import build_decks
from app.formats import get_format
from app.meta.store import load_meta_folder


def main():
    ap = argparse.ArgumentParser(description="MTG Arena collection & deck builder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update-cards"); u.add_argument("--file", type=Path)
    i = sub.add_parser("import"); i.add_argument("path", type=Path); i.add_argument("--add", action="store_true")
    sub.add_parser("load-meta")
    b = sub.add_parser("build"); b.add_argument("format"); b.add_argument("--top", type=int, default=3)
    e = sub.add_parser("export"); e.add_argument("path", type=Path)
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    if args.cmd == "update-cards":
        path = args.file or download_bulk()
        print(f"Loaded {load_cards(db, iter_bulk_file(path)):,} Arena printings.")
    elif args.cmd == "import":
        r = services.import_collection(db, args.path.read_text(encoding="utf-8"), "add" if args.add else "replace")
        print(f"{r.kind}: {r.matched_rows}/{r.rows} rows matched, {r.cards_added} copies.")
        for row in r.unmatched[:50]:
            print(f"  unmatched line {row.line_no}: {row.name}")
    elif args.cmd == "load-meta":
        print(f"Loaded {load_meta_folder(db)} meta decks.")
    elif args.cmd == "build":
        fmt = get_format(args.format)
        decks = build_decks(services.catalog(db), services.owned(db), fmt, services.meta_freq(db, fmt.key), args.top)
        if not decks:
            print("Not enough legal cards for a full deck.")
        for d in decks:
            print(f"## {d.name}  (score {d.score})")
            print("\n".join(d.notes))
            print(exporters.deck_arena_text(d))
        for m in services.meta_matches(db, fmt.key)[:args.top]:
            print(f"meta: {m.name}: {m.completion:.0%} owned, wildcards {m.wildcards}")
    elif args.cmd == "export":
        entries = services.collection_entries(db)
        fn = {".csv": exporters.collection_csv, ".json": exporters.collection_json}.get(args.path.suffix,
                                                                                       exporters.collection_arena_text)
        args.path.write_text(fn(entries), encoding="utf-8")
        print(f"Wrote {len(entries)} printings to {args.path}")


if __name__ == "__main__":
    main()
