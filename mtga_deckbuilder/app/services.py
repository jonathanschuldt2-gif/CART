"""Glue between the database and the pure engine."""
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.engine.card_score import meta_frequency
from app.engine.cardinfo import CardInfo, build_catalog, owned_counts
from app.engine.deckparse import CatalogIndex, ParsedDeck, parse_deck_text
from app.engine.meta_match import MetaMatch, match_deck
from app.formats import get_format
from app.importers.detect import parse_any
from app.importers.resolve import Resolver
from app.importers.rows import ImportRow
from app.models import Card, CollectionEntry, MetaDeck

_cache: dict = {}


def card_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Card)) or 0


def invalidate():
    _cache.clear()


def catalog(db: Session) -> dict[str, CardInfo]:
    n = card_count(db)
    if _cache.get("n") != n:
        cards = list(db.scalars(select(Card)))
        _cache.update(n=n, catalog=build_catalog(cards), resolver=Resolver(cards))
        _cache["index"] = CatalogIndex(_cache["catalog"])
    return _cache["catalog"]


def resolver(db: Session) -> Resolver:
    catalog(db)
    return _cache["resolver"]


def index(db: Session) -> CatalogIndex:
    catalog(db)
    return _cache["index"]


def collection_entries(db: Session) -> list[tuple[Card, int]]:
    return [(e.card, e.quantity) for e in db.scalars(select(CollectionEntry)) if e.quantity > 0]


def owned(db: Session) -> dict[str, int]:
    return owned_counts(collection_entries(db))


@dataclass
class ImportReport:
    kind: str
    rows: int = 0
    matched_rows: int = 0
    cards_added: int = 0
    unique: int = 0
    unmatched: list[ImportRow] = field(default_factory=list)


def import_collection(db: Session, text: str, mode: str = "replace") -> ImportReport:
    kind, rows = parse_any(text)
    res = resolver(db).resolve(rows)
    totals: Counter = Counter()
    for card, row in res.matched:
        totals[card.id] += row.quantity
    if mode == "replace":
        db.execute(delete(CollectionEntry))
    existing = {e.card_id: e for e in db.scalars(select(CollectionEntry))}
    for card_id, qty in totals.items():
        e = existing.get(card_id)
        if e is None:
            db.add(CollectionEntry(card_id=card_id, quantity=qty))
        else:
            e.quantity = qty if mode == "set" else e.quantity + qty
    db.commit()
    return ImportReport(kind, len(rows), len(res.matched), res.total_cards, len(totals), res.unmatched)


def set_quantity(db: Session, card_id: str, qty: int):
    e = db.scalar(select(CollectionEntry).where(CollectionEntry.card_id == card_id))
    if qty <= 0:
        if e:
            db.delete(e)
    elif e:
        e.quantity = qty
    else:
        db.add(CollectionEntry(card_id=card_id, quantity=qty))
    db.commit()


def meta_decks(db: Session, fmt: str | None = None) -> list[tuple[MetaDeck, ParsedDeck]]:
    q = select(MetaDeck).order_by(MetaDeck.format, MetaDeck.name)
    if fmt:
        q = q.where(MetaDeck.format == fmt)
    idx = index(db)
    return [(d, parse_deck_text(d.text, idx)) for d in db.scalars(q)]


def meta_freq(db: Session, fmt: str) -> dict[str, float]:
    return meta_frequency([p.all_cards for _, p in meta_decks(db, fmt)])


def meta_matches(db: Session, fmt: str) -> list[MetaMatch]:
    cat, own, f = catalog(db), owned(db), get_format(fmt)
    freq = meta_freq(db, fmt)
    out = [match_deck(d.id, d.name, f, p, cat, own, freq) for d, p in meta_decks(db, fmt)]
    out.sort(key=lambda m: (m.wildcard_cost, -m.completion))
    return out
