from collections import Counter

from app import exporters, services
from app.engine.builder import build_decks
from app.engine.deckparse import CatalogIndex, parse_deck_text
from app.formats import get_format
from app.importers.detect import parse_any


def test_import_and_collection_roundtrip(db):
    services.invalidate()
    text = "Name,Quantity,Set,Collector Number\nRed Removal,4,,\nFire // Ice,2,,\nIsland,3,,\nUnknown Thing,1,,\n"
    rep = services.import_collection(db, text, "replace")
    assert rep.kind == "csv" and rep.matched_rows == 3 and len(rep.unmatched) == 1
    assert services.owned(db) == {"red removal": 4, "fire // ice": 2, "island": 3}
    services.import_collection(db, "2 Red Removal", "add")
    assert services.owned(db)["red removal"] == 6
    entries = services.collection_entries(db)
    for export in (exporters.collection_csv, exporters.collection_json, exporters.collection_arena_text):
        services.import_collection(db, export(entries), "replace")
        assert services.owned(db) == {"red removal": 6, "fire // ice": 2, "island": 3}, export.__name__


def test_deck_export_reimports_identically(catalog):
    owned = {k: 4 for k, c in catalog.items() if not c.is_basic}
    fmt = get_format("standard")
    deck = build_decks(catalog, owned, fmt, top_n=1)[0]
    text = exporters.deck_arena_text(deck)
    assert text.startswith("Deck\n")
    parsed = parse_deck_text(text, CatalogIndex(catalog))
    expect = Counter()
    for c, n in deck.cards:
        expect[c.key] += n
    assert parsed.main == expect and not parsed.unknown
    kind, rows = parse_any(exporters.deck_arena_text(deck, with_set=True))
    assert kind == "arena" and all(r.set_code for r in rows)
