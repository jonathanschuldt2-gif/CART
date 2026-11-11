from collections import Counter
from dataclasses import dataclass, field

from app.cards.normalize import front_face, norm_name
from app.engine.cardinfo import CardInfo
from app.importers.arena_text import parse_arena_text


@dataclass
class ParsedDeck:
    main: Counter = field(default_factory=Counter)        # name_key -> copies
    sideboard: Counter = field(default_factory=Counter)
    commander: str | None = None
    companion: str | None = None
    unknown: list[str] = field(default_factory=list)

    @property
    def all_cards(self) -> Counter:
        c = Counter(self.main)
        c.update(self.sideboard)
        for extra in (self.commander, self.companion):
            if extra:
                c[extra] += 1
        return c


class CatalogIndex:
    def __init__(self, catalog: dict[str, CardInfo]):
        self.catalog = catalog
        self.front = {}
        for key, c in catalog.items():
            self.front.setdefault(front_face(c.name), key)

    def lookup(self, name: str) -> str | None:
        key = norm_name(name)
        if key in self.catalog:
            return key
        return self.front.get(front_face(name))


def parse_deck_text(text: str, index: CatalogIndex) -> ParsedDeck:
    deck = ParsedDeck()
    for row in parse_arena_text(text):
        key = index.lookup(row.name)
        if key is None:
            deck.unknown.append(row.name)
            continue
        if row.section == "commander":
            deck.commander = key
        elif row.section == "companion":
            deck.companion = key
            deck.sideboard[key] += row.quantity  # companions live in the sideboard
        elif row.section == "sideboard":
            deck.sideboard[key] += row.quantity
        else:
            deck.main[key] += row.quantity
    return deck
