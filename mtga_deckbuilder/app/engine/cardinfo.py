"""Oracle-level view of cards: printings of the same card merged by name."""
import re
from dataclasses import dataclass, field

from app.cards.normalize import norm_name

BASIC_NAMES = {"plains": "W", "island": "U", "swamp": "B", "mountain": "R", "forest": "G", "wastes": ""}
RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "mythic": 3, "special": 2, "bonus": 2}
FRONT_FACE_LAYOUTS = {"transform", "modal_dfc", "adventure", "flip", "meld", "reversible_card", "prototype"}
_PIP = re.compile(r"\{([^}]+)\}")


@dataclass
class CardInfo:
    key: str
    name: str
    cmc: float
    mana_cost: str
    colors: str
    color_identity: str
    type_line: str
    oracle_text: str
    power: str
    toughness: str
    keywords: list[str]
    rarity: str            # lowest rarity among Arena printings (= wildcard cost)
    legalities: dict
    produced_mana: str
    layout: str = "normal"
    set_code: str = ""
    collector_number: str = ""
    arena_id: int | None = None
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def front_type(self) -> str:
        return self.type_line.split(" // ")[0]

    @property
    def is_land(self) -> bool:
        return "Land" in self.front_type

    @property
    def is_basic(self) -> bool:
        return self.key in BASIC_NAMES or "Basic" in self.front_type

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.front_type

    @property
    def is_legendary(self) -> bool:
        return "Legendary" in self.front_type

    @property
    def can_be_commander(self) -> bool:
        t = self.front_type
        return ("Legendary" in t and ("Creature" in t or "Planeswalker" in t)) or \
            "can be your commander" in self.oracle_text.lower()

    @property
    def any_number(self) -> bool:
        return "a deck can have any number of cards named" in self.oracle_text.lower()

    @property
    def export_name(self) -> str:
        if self.layout in FRONT_FACE_LAYOUTS:
            return self.name.split(" // ")[0]
        return self.name

    @property
    def subtypes(self) -> list[str]:
        if "subtypes" not in self._cache:
            t = self.front_type
            self._cache["subtypes"] = t.split("—", 1)[1].split() if "—" in t else []
        return self._cache["subtypes"]

    def pips(self) -> dict[str, float]:
        out = {c: 0.0 for c in "WUBRG"}
        for sym in _PIP.findall(self.mana_cost or ""):
            parts = [p for p in sym.split("/") if p in out]
            for p in parts:
                out[p] += 1 / len(parts)
        return out


def _from_card(c) -> CardInfo:
    return CardInfo(
        key=c.name_key, name=c.name, cmc=c.cmc, mana_cost=c.mana_cost or "", colors=c.colors or "",
        color_identity=c.color_identity or "", type_line=c.type_line or "", oracle_text=c.oracle_text or "",
        power=c.power or "", toughness=c.toughness or "", keywords=list(c.keywords), rarity=c.rarity,
        legalities=dict(c.legalities), produced_mana=c.produced_mana or "", layout=getattr(c, "layout", "normal") or "normal",
        set_code=c.set_code, collector_number=c.collector_number, arena_id=c.arena_id,
    )


def build_catalog(cards) -> dict[str, CardInfo]:
    """Merge printings by name. Rarity = lowest printing rarity (cheapest wildcard)."""
    cat: dict[str, CardInfo] = {}
    for c in cards:
        info = cat.get(c.name_key)
        if info is None:
            cat[c.name_key] = _from_card(c)
            continue
        if RARITY_ORDER.get(c.rarity, 2) < RARITY_ORDER.get(info.rarity, 2):
            info.rarity = c.rarity
        if c.arena_id and (info.arena_id is None or c.arena_id > info.arena_id):
            info.arena_id, info.set_code, info.collector_number = c.arena_id, c.set_code, c.collector_number
    return cat


def owned_counts(entries) -> dict[str, int]:
    """entries: iterable of (Card, quantity)."""
    out: dict[str, int] = {}
    for card, qty in entries:
        out[card.name_key] = out.get(card.name_key, 0) + qty
    return out


def key_for(name: str) -> str:
    return norm_name(name)
