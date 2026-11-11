"""Match parsed import rows to Card printings."""
from collections import defaultdict
from dataclasses import dataclass, field

from app.cards.normalize import front_face, norm_name
from app.importers.rows import ImportRow
from app.models import Card

# Arena uses a few set codes that differ from Scryfall's.
ARENA_SET_ALIASES = {"DAR": "DOM", "CONF": "CON"}


@dataclass
class ResolveResult:
    matched: list[tuple[Card, ImportRow]] = field(default_factory=list)
    unmatched: list[ImportRow] = field(default_factory=list)

    @property
    def total_cards(self) -> int:
        return sum(r.quantity for _, r in self.matched)


class Resolver:
    def __init__(self, cards):
        self.by_arena: dict[int, Card] = {}
        self.by_set_num: dict[tuple[str, str], Card] = {}
        self.by_name: dict[str, list[Card]] = defaultdict(list)
        self.by_front: dict[str, list[Card]] = defaultdict(list)
        for c in cards:
            if c.arena_id:
                self.by_arena[c.arena_id] = c
            self.by_set_num[(c.set_code.upper(), c.collector_number.lstrip("0") or "0")] = c
            self.by_name[c.name_key].append(c)
            self.by_front[c.front_key].append(c)

    @staticmethod
    def _pick(cands: list[Card], set_code: str = "") -> Card:
        if set_code:
            for c in cands:
                if c.set_code == set_code:
                    return c
        return sorted(cands, key=lambda c: (c.arena_id is None, -(c.arena_id or 0)))[0]

    def resolve_one(self, row: ImportRow) -> Card | None:
        if row.arena_id and row.arena_id in self.by_arena:
            return self.by_arena[row.arena_id]
        set_code = ARENA_SET_ALIASES.get(row.set_code, row.set_code)
        if set_code and row.collector_number:
            c = self.by_set_num.get((set_code, row.collector_number.lstrip("0") or "0"))
            if c and front_face(c.name) == front_face(row.name):
                return c
        key = norm_name(row.name)
        if key in self.by_name:
            return self._pick(self.by_name[key], set_code)
        fkey = front_face(row.name)
        if fkey in self.by_front:
            return self._pick(self.by_front[fkey], set_code)
        return None

    def resolve(self, rows: list[ImportRow]) -> ResolveResult:
        res = ResolveResult()
        for r in rows:
            c = self.resolve_one(r)
            if c is None:
                res.unmatched.append(r)
            else:
                res.matched.append((c, r))
        return res
