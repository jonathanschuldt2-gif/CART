import csv
import io
import json

from app.engine.builder import DeckResult
from app.importers.arena_text import to_arena_line


def _sorted_entries(entries):
    return sorted(entries, key=lambda e: (e[0].name.lower(), e[0].set_code))


def collection_csv(entries) -> str:
    """entries: iterable of (Card, quantity)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Count", "Name", "Set", "Collector Number", "Rarity", "Arena ID", "Type", "Colors", "Mana Value"])
    for c, q in _sorted_entries(entries):
        w.writerow([q, c.name, c.set_code, c.collector_number, c.rarity, c.arena_id or "",
                    c.type_line, c.colors, c.cmc])
    return buf.getvalue()


def collection_json(entries) -> str:
    return json.dumps([
        {"name": c.name, "quantity": q, "set": c.set_code, "collector_number": c.collector_number,
         "rarity": c.rarity, "arena_id": c.arena_id}
        for c, q in _sorted_entries(entries)], indent=2)


def collection_arena_text(entries) -> str:
    return "\n".join(to_arena_line(q, c.name, c.set_code, c.collector_number)
                     for c, q in _sorted_entries(entries)) + "\n"


def deck_arena_text(deck: DeckResult, with_set: bool = False) -> str:
    def line(card, n):
        if with_set and card.set_code and card.collector_number:
            return to_arena_line(n, card.export_name, card.set_code, card.collector_number)
        return to_arena_line(n, card.export_name)

    out = []
    if deck.commander:
        out += ["Commander", line(deck.commander, 1), ""]
    out.append("Deck")
    main = sorted(deck.main, key=lambda x: (x[0].cmc, x[0].name))
    out += [line(c, n) for c, n in main]
    out += [line(c, n) for c, n in sorted(deck.lands, key=lambda x: (x[0].is_basic, x[0].name))]
    return "\n".join(out) + "\n"


def deck_csv(deck: DeckResult) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Count", "Name", "Section", "Mana Value", "Type", "Rarity"])
    if deck.commander:
        c = deck.commander
        w.writerow([1, c.export_name, "Commander", c.cmc, c.type_line, c.rarity])
    for c, n in deck.cards:
        w.writerow([n, c.export_name, "Deck", c.cmc, c.type_line, c.rarity])
    return buf.getvalue()
