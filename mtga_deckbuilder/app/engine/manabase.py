"""Land count and mana base construction."""
import re

from app.engine.cardinfo import BASIC_NAMES, CardInfo

BASIC_FOR = {v: k for k, v in BASIC_NAMES.items() if v}


def land_count(avg_cmc: float, deck_size: int = 60, archetype: str = "midrange") -> int:
    if deck_size >= 100:
        return max(36, min(42, round(33 + 2.0 * avg_cmc)))
    base = 16 + 2.6 * avg_cmc  # avg 2.0 -> ~21, 3.0 -> ~24
    base += {"aggro": -0.5, "midrange": 0, "control": 1}.get(archetype, 0)
    return max(20, min(27, round(base)))


def colored_pips(spells: list[tuple[CardInfo, int]]) -> dict[str, float]:
    tot = {c: 0.0 for c in "WUBRG"}
    for card, n in spells:
        for col, v in card.pips().items():
            tot[col] += v * n
    return tot


def _land_quality(land: CardInfo, colors: str) -> float:
    produced = set(land.produced_mana) & set(colors)
    t = (land.oracle_text or "").lower()
    q = 2.0 * len(produced)
    if re.search(r"enters (?:the battlefield )?tapped\.", t) and "unless" not in t:
        q -= 0.8
    if "becomes a" in t or "creature" in t:
        q += 0.3  # creature lands / utility
    if "pay 1 life" in t or "deals 1 damage to you" in t:
        q -= 0.2
    return q


def build_manabase(spells: list[tuple[CardInfo, int]], colors: str, n_lands: int,
                   owned_lands: list[tuple[CardInfo, int]], basics: dict[str, CardInfo],
                   copy_limit: int = 4) -> list[tuple[CardInfo, int]]:
    """Pick owned dual/utility lands, then fill with basics proportional to colored pips."""
    colors = "".join(c for c in "WUBRG" if c in colors)
    lands: list[tuple[CardInfo, int]] = []
    if len(colors) >= 2:
        max_nonbasic = int(n_lands * (0.5 if len(colors) == 2 else 0.65))
        cands = []
        for land, owned in owned_lands:
            if land.is_basic:
                continue
            if len(set(land.produced_mana) & set(colors)) < 2:
                continue  # must fix at least two of the deck's colours
            cands.append((_land_quality(land, colors), land, min(owned, copy_limit)))
        cands.sort(key=lambda x: -x[0])
        used = 0
        for _, land, n in cands:
            n = min(n, max_nonbasic - used)
            if n <= 0:
                break
            lands.append((land, n))
            used += n
    remaining = n_lands - sum(n for _, n in lands)
    if remaining <= 0:
        return lands
    pips = colored_pips(spells)
    weights = {c: pips[c] for c in colors}
    if not colors:
        wastes = basics.get("C")
        return lands + ([(wastes, remaining)] if wastes else [])
    if sum(weights.values()) == 0:
        weights = {c: 1.0 for c in colors}
    total = sum(weights.values())
    alloc = {c: max(1 if weights[c] > 0 else 0, int(remaining * weights[c] / total)) for c in colors}
    # fix rounding so the sum matches
    while sum(alloc.values()) < remaining:
        c = max(colors, key=lambda c: weights[c] / total * remaining - alloc[c])
        alloc[c] += 1
    while sum(alloc.values()) > remaining:
        c = max((c for c in colors if alloc[c] > 1), key=lambda c: alloc[c] - weights[c] / total * remaining)
        alloc[c] -= 1
    for c in colors:
        if alloc[c] > 0 and c in basics:
            lands.append((basics[c], alloc[c]))
    return lands


def basics_from_catalog(catalog: dict[str, CardInfo]) -> dict[str, CardInfo]:
    out = {}
    for name, col in BASIC_NAMES.items():
        if name in catalog:
            out[col or "C"] = catalog[name]
    return out
