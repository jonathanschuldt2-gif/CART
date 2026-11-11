"""Compare meta decklists with a collection: completion % and wildcard cost."""
from collections import Counter
from dataclasses import dataclass, field

from app.engine.card_score import card_power, roles
from app.engine.cardinfo import CardInfo
from app.engine.deckparse import ParsedDeck
from app.formats import Format, is_legal

RARITIES = ("common", "uncommon", "rare", "mythic")


@dataclass
class MissingCard:
    card: CardInfo
    need: int
    owned: int

    @property
    def missing(self) -> int:
        return self.need - self.owned


@dataclass
class MetaMatch:
    deck_id: int
    name: str
    format: str
    completion: float                      # 0..1, non-basic cards owned / needed
    wildcards: dict[str, int]              # rarity -> count (main + sideboard)
    wildcards_main: dict[str, int]
    missing: list[MissingCard] = field(default_factory=list)
    swaps: dict[str, list[str]] = field(default_factory=dict)
    unknown: list[str] = field(default_factory=list)

    @property
    def total_wildcards(self) -> int:
        return sum(self.wildcards.values())

    @property
    def wildcard_cost(self) -> float:
        """Weighted cost for sorting (mythic wildcards are scarcer)."""
        w = {"common": 0.1, "uncommon": 0.3, "rare": 1.0, "mythic": 2.0}
        return sum(w[r] * n for r, n in self.wildcards.items())


def _rarity(card: CardInfo) -> str:
    return card.rarity if card.rarity in RARITIES else "rare"


def match_deck(deck_id: int, name: str, fmt: Format, parsed: ParsedDeck,
               catalog: dict[str, CardInfo], owned: dict[str, int],
               meta_freq: dict[str, float] | None = None, suggest_swaps: bool = True) -> MetaMatch:
    need_all = parsed.all_cards
    need_main = Counter(parsed.main)
    if parsed.commander:
        need_main[parsed.commander] += 1
    wc = {r: 0 for r in RARITIES}
    wc_main = {r: 0 for r in RARITIES}
    have_total = need_total = 0
    missing = []
    for key, need in need_all.items():
        card = catalog[key]
        if card.is_basic:
            continue
        have = min(owned.get(key, 0), need)
        need_total += need
        have_total += have
        if have < need:
            wc[_rarity(card)] += need - have
            missing.append(MissingCard(card, need, have))
        main_need = need_main.get(key, 0)
        if main_need:
            wc_main[_rarity(card)] += max(0, main_need - min(owned.get(key, 0), main_need))
    missing.sort(key=lambda m: (-RARITIES.index(_rarity(m.card)), m.card.name))
    m = MetaMatch(deck_id, name, fmt.key, have_total / need_total if need_total else 1.0,
                  wc, wc_main, missing, unknown=list(parsed.unknown))
    if suggest_swaps and missing:
        m.swaps = suggest_replacements(missing, need_all, catalog, owned, fmt, meta_freq)
    return m


def suggest_replacements(missing, deck_cards, catalog, owned, fmt, meta_freq=None, per_card=3):
    deck_colors = set()
    for key in deck_cards:
        deck_colors |= set(catalog[key].colors)
    candidates = [catalog[k] for k, n in owned.items()
                  if n > 0 and k in catalog and k not in deck_cards
                  and is_legal(catalog[k].legalities, fmt) and not catalog[k].is_basic
                  and set(catalog[k].colors) <= deck_colors]
    out = {}
    for m in missing:
        target = m.card
        want = roles(target) - {"planeswalker"}
        scored = []
        for c in candidates:
            if c.is_land != target.is_land:
                continue
            if abs(c.cmc - target.cmc) > 1:
                continue
            overlap = len(roles(c) & want)
            if want and not overlap:
                continue
            scored.append((overlap + card_power(c, meta_freq) / 10 - 0.3 * abs(c.cmc - target.cmc), c.name))
        scored.sort(reverse=True)
        if scored:
            out[target.name] = [n for _, n in scored[:per_card]]
    return out
