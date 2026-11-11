"""Heuristic card power, roles and synergy themes."""
import re

from app.engine.cardinfo import CardInfo

RARITY_BONUS = {"common": 0.0, "uncommon": 0.25, "rare": 0.5, "mythic": 0.7}

ROLE_PATTERNS = {
    "removal": [r"destroy target (?:creature|permanent|nonland|artifact|enchantment|planeswalker)",
                r"exile target (?:creature|permanent|nonland|artifact|enchantment|planeswalker)",
                r"deals? (?:\d+|x) damage to (?:any target|target creature|target player or planeswalker|"
                r"target creature or planeswalker|each creature)",
                r"target creature (?:gets|an opponent controls gets) -\d", r"\bfights?\b",
                r"target (?:player|opponent) sacrifices"],
    "sweeper": [r"destroy all (?:creatures|nonland)", r"exile all (?:creatures|nonland)",
                r"deals? \d+ damage to each creature", r"all creatures get -"],
    "counter": [r"counter target (?:spell|creature|noncreature|activated|instant)"],
    "draw": [r"draws? (?:a|two|three|x|that many) cards?", r"\binvestigate\b", r"look at the top \w+ cards"],
    "ramp": [r"add \{[wubrgc]\}", r"search your library for (?:a|up to \w+) (?:basic )?land",
             r"\btreasure token"],
    "bounce": [r"return target (?:creature|nonland permanent|permanent)[^.]*to its owner's hand"],
    "discard": [r"target (?:player|opponent) discards", r"each opponent discards"],
}

THEMES = {
    "counters": r"\+1/\+1 counter",
    "tokens": r"create[^.]*token",
    "sacrifice": r"sacrifice (?:a|an|another)|whenever [^.]*dies",
    "lifegain": r"gain[s]? (?:\d+|x|that much) life|whenever you gain life",
    "spells": r"instant (?:or|and) sorcery|noncreature spell|whenever you cast (?:an instant|a sorcery)",
    "graveyard": r"from your graveyard|\bmill\b|\bsurveil\b|cards? in your graveyard",
    "artifacts": r"\bartifacts?\b",
    "enchantments": r"\benchantments?\b",
    "landfall": r"landfall|whenever a land (?:you control )?enters",
    "attack": r"whenever [^.]* attacks",
    "flying": r"creatures? (?:you control )?with flying",
    "discard_self": r"discard a card|whenever you discard",
}
EVASION = {"flying": 0.8, "trample": 0.4, "menace": 0.5, "haste": 0.5, "lifelink": 0.4,
           "deathtouch": 0.6, "vigilance": 0.2, "first strike": 0.4, "double strike": 0.9,
           "hexproof": 0.4, "ward": 0.4, "flash": 0.3, "indestructible": 0.6, "prowess": 0.3}
DRAWBACKS = [r"can't block", r"sacrifice it at", r"you lose \d+ life", r"enters (?:the battlefield )?tapped",
             r"skip your", r"discard your hand"]


def _text(c: CardInfo) -> str:
    return (c.oracle_text or "").lower()


def roles(c: CardInfo) -> set[str]:
    if "roles" in c._cache:
        return c._cache["roles"]
    t = _text(c)
    out = {r for r, pats in ROLE_PATTERNS.items() if any(re.search(p, t) for p in pats)}
    if c.is_creature:
        out.add("creature")
    if "Planeswalker" in c.front_type:
        out.add("planeswalker")
    c._cache["roles"] = out
    return out


def themes(c: CardInfo) -> set[str]:
    if "themes" in c._cache:
        return c._cache["themes"]
    t = _text(c)
    out = {k for k, p in THEMES.items() if re.search(p, t)}
    kws = {k.lower() for k in c.keywords}
    if "lifelink" in kws:
        out.add("lifegain")
    if "flying" in kws and c.is_creature:
        out.add("flying_body")
    if c.is_creature and re.search(r"create[^.]*token", t) is None and "Artifact" in c.front_type:
        out.add("artifacts")
    c._cache["themes"] = out
    return out


def tribal_mentions(c: CardInfo, all_types: set[str]) -> set[str]:
    """Creature types this card cares about (payoff), e.g. 'other Elves you control'."""
    t = c.oracle_text or ""
    found = set()
    for typ in all_types:
        if len(typ) < 3:
            continue
        if re.search(rf"\b{re.escape(typ)}s?\b", t) or (typ.endswith("f") and re.search(rf"\b{typ[:-1]}ves\b", t)):
            found.add(typ)
    return found


def _num(s: str) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return 1.0 if s else 0.0  # '*' etc.


def base_power(c: CardInfo) -> float:
    """Context-free power estimate on a rough 0–10 scale."""
    if "base_power" in c._cache:
        return c._cache["base_power"]
    t = _text(c)
    r = roles(c)
    kws = {k.lower() for k in c.keywords}
    score = 3.0
    if c.is_creature:
        stats = _num(c.power) + _num(c.toughness)
        score += max(-1.5, min(2.0, (stats - 2 * max(c.cmc, 0.5)) * 0.4))
        score += sum(v for k, v in EVASION.items() if k in kws)
        if re.search(r"when [^.]*enters", t):
            score += 0.8
    if "planeswalker" in r:
        score += 2.5
    score += 1.6 * ("removal" in r) + 1.4 * ("sweeper" in r) + 1.0 * ("counter" in r)
    score += 1.0 * ("draw" in r) + 0.6 * ("ramp" in r) + 0.5 * ("bounce" in r) + 0.5 * ("discard" in r)
    if "Instant" in c.front_type or "flash" in kws:
        score += 0.3
    if c.layout in ("modal_dfc", "adventure", "split"):
        score += 0.6  # two cards in one
    score += min(1.0, 0.25 * len(themes(c)))
    score -= 0.6 * sum(bool(re.search(p, t)) for p in DRAWBACKS)
    if c.cmc >= 6:
        score -= 0.5 * (c.cmc - 5)
    if not t and not c.is_creature:
        score -= 1.0
    score += RARITY_BONUS.get(c.rarity, 0.4)
    c._cache["base_power"] = score
    return score


def card_power(c: CardInfo, meta_freq: dict[str, float] | None = None) -> float:
    """Base power plus how often the card shows up in the imported meta decks (0..1)."""
    freq = (meta_freq or {}).get(c.key, 0.0)
    return base_power(c) + 6.0 * freq


def meta_frequency(meta_decks: list[dict[str, int]]) -> dict[str, float]:
    """meta_decks: list of {name_key: copies}. Returns weighted share of decks playing each card."""
    if not meta_decks:
        return {}
    acc: dict[str, float] = {}
    for deck in meta_decks:
        for key, qty in deck.items():
            acc[key] = acc.get(key, 0.0) + min(qty, 4) / 4
    return {k: v / len(meta_decks) for k, v in acc.items()}
