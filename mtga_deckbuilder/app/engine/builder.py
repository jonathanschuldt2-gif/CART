"""Build the best decks possible from the cards a player owns."""
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from app.engine.card_score import card_power, roles, themes, tribal_mentions
from app.engine.cardinfo import CardInfo
from app.engine.manabase import basics_from_catalog, build_manabase, land_count
from app.formats import Format, is_legal

COLOR_NAMES = {
    "W": "Mono-White", "U": "Mono-Blue", "B": "Mono-Black", "R": "Mono-Red", "G": "Mono-Green",
    "WU": "Azorius", "UB": "Dimir", "BR": "Rakdos", "RG": "Gruul", "WG": "Selesnya",
    "WB": "Orzhov", "UR": "Izzet", "BG": "Golgari", "WR": "Boros", "UG": "Simic",
    "WUB": "Esper", "UBR": "Grixis", "BRG": "Jund", "WRG": "Naya", "WUG": "Bant",
    "WBG": "Abzan", "WUR": "Jeskai", "UBG": "Sultai", "WBR": "Mardu", "URG": "Temur",
    "": "Colorless",
}
THEME_LABELS = {
    "counters": "Counters", "tokens": "Tokens", "sacrifice": "Sacrifice", "lifegain": "Lifegain",
    "spells": "Spells", "graveyard": "Graveyard", "artifacts": "Artifacts", "enchantments": "Enchantments",
    "landfall": "Landfall", "attack": "Attackers", "flying": "Fliers", "discard_self": "Madness",
}
# curve targets (spell slots by mana value, before scaling), creature range, interaction target
ARCHETYPES = {
    "aggro": {"curve": {1: 6, 2: 10, 3: 8, 4: 4, 5: 2, 6: 0}, "creatures": (0.45, 0.70), "interaction": 0.12, "lands": 22},
    "midrange": {"curve": {1: 3, 2: 9, 3: 9, 4: 7, 5: 4, 6: 2}, "creatures": (0.33, 0.55), "interaction": 0.18, "lands": 24},
    "control": {"curve": {1: 3, 2: 8, 3: 8, 4: 6, 5: 4, 6: 3}, "creatures": (0.10, 0.35), "interaction": 0.30, "lands": 25},
}
INTERACTION = {"removal", "counter", "sweeper"}


@dataclass
class DeckResult:
    name: str
    format: str
    colors: str
    archetype: str
    main: list[tuple[CardInfo, int]]
    lands: list[tuple[CardInfo, int]]
    commander: CardInfo | None = None
    score: float = 0.0
    notes: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)

    @property
    def cards(self) -> list[tuple[CardInfo, int]]:
        return self.main + self.lands

    @property
    def size(self) -> int:
        return sum(n for _, n in self.cards) + (1 if self.commander else 0)

    @property
    def curve(self) -> dict[int, int]:
        out = {i: 0 for i in range(0, 7)}
        for c, n in self.main:
            out[min(int(c.cmc), 6)] += n
        return out

    @property
    def keys(self) -> set[str]:
        return {c.key for c, _ in self.main}


def _bucket(card: CardInfo) -> int:
    return max(1, min(int(card.cmc), 6))


class _Builder:
    def __init__(self, pool, fmt, archetype, spells, meta_freq, payoffs, prior=None, commander=None):
        self.pool = pool  # list[(CardInfo, available copies)]
        self.fmt = fmt
        self.arch = ARCHETYPES[archetype]
        self.archetype = archetype
        self.spells = spells
        self.meta_freq = meta_freq
        self.payoffs = payoffs  # card key -> creature types it pays off
        total = sum(self.arch["curve"].values())
        self.curve_target = {b: v * spells / total for b, v in self.arch["curve"].items()}
        self.prior = prior or Counter()
        self.commander = commander
        self.limit = 1 if fmt.singleton else fmt.copy_limit

    def _synergy(self, card, theme_counts, type_counts, payoff_counts) -> float:
        s = 0.0
        for t in themes(card):
            s += 0.12 * min(theme_counts[t] + 0.5 * self.prior[t], 14)
        if card.is_creature:
            for st in card.subtypes:
                s += 0.3 * min(payoff_counts[st] + 0.5 * self.prior["payoff:" + st], 4)
        for st in self.payoffs.get(card.key, ()):
            s += 0.08 * min(type_counts[st] + 0.5 * self.prior["type:" + st], 16)
        return s

    def _arch_adjust(self, card) -> float:
        r = roles(card)
        if self.archetype == "aggro":
            adj = 0.4 * (3 - card.cmc) if card.is_creature else (-0.4 if not r & {"removal"} else 0.2)
            if card.cmc >= 5:
                adj -= 1.0
            if "haste" in {k.lower() for k in card.keywords}:
                adj += 0.3
            return adj
        if self.archetype == "control":
            adj = 0.8 * bool(r & (INTERACTION | {"draw"}))
            if card.is_creature and card.cmc <= 2 and not r - {"creature"}:
                adj -= 0.5
            return adj
        return 0.0

    def build(self):
        chosen: Counter = Counter()
        bucket = Counter()
        theme_counts, type_counts, payoff_counts = Counter(), Counter(), Counter()
        creatures = interaction = 0
        total = 0
        cmin, cmax = (x * self.spells for x in self.arch["creatures"])
        inter_target = self.arch["interaction"] * self.spells
        avail = {c.key: (c, n) for c, n in self.pool}
        base = {k: card_power(c, self.meta_freq) + self._arch_adjust(c) for k, (c, _) in avail.items()}
        while total < self.spells:
            best = None
            for key, (card, n_avail) in avail.items():
                have = chosen[key]
                cap = min(n_avail, self.limit)
                if have >= cap:
                    continue
                pref = 4 if card.cmc <= 3 else 3 if card.cmc <= 4 else 2
                if card.is_legendary:
                    pref = min(pref, 3)
                n = 1 if have else max(1, min(cap, pref))
                n = min(n, self.spells - total)
                val = base[key] + self._synergy(card, theme_counts, type_counts, payoff_counts)
                if have:
                    val -= 0.4 * max(0, have + 1 - pref)
                b = _bucket(card)
                over = max(0.0, bucket[b] + n - self.curve_target[b])
                val -= 1.2 * min(over, n) / n * (1 + over / 4)
                r = roles(card)
                if r & INTERACTION and interaction < inter_target:
                    val += 1.0
                if card.is_creature:
                    if creatures < cmin:
                        val += 0.8
                    elif creatures + n > cmax:
                        val -= 1.0
                if best is None or val > best[0]:
                    best = (val, key, card, n)
            if best is None:
                break
            _, key, card, n = best
            chosen[key] += n
            total += n
            bucket[_bucket(card)] += n
            for t in themes(card):
                theme_counts[t] += n
            if card.is_creature:
                creatures += n
                for st in card.subtypes:
                    type_counts[st] += n
            for st in self.payoffs.get(card.key, ()):
                payoff_counts[st] += n
            if roles(card) & INTERACTION:
                interaction += n
        main = [(avail[k][0], n) for k, n in chosen.items()]
        profile = Counter()
        for t, v in theme_counts.items():
            profile[t] = v
        for t, v in type_counts.items():
            profile["type:" + t] = v
        for t, v in payoff_counts.items():
            profile["payoff:" + t] = v
        return main, profile


def _avg_cmc(main) -> float:
    n = sum(k for _, k in main)
    return sum(c.cmc * k for c, k in main) / n if n else 0.0


def _score_deck(main, lands, colors, curve_target, meta_freq, commander=None) -> float:
    n = sum(k for _, k in main)
    if not n:
        return 0.0
    power = sum(card_power(c, meta_freq) * k for c, k in main) / n
    theme_counts = Counter()
    for c, k in main:
        for t in themes(c):
            theme_counts[t] += k
    top_themes = sorted(theme_counts.values(), reverse=True)[:2]
    synergy = sum(min(v / n, 0.5) for v in top_themes)
    curve = Counter()
    for c, k in main:
        curve[_bucket(c)] += k
    curve_err = sum(abs(curve[b] - t) for b, t in curve_target.items()) / n
    ncol = len(colors)
    strain = 0.35 * max(0, ncol - 2)
    if ncol >= 2:
        duals = sum(k for l, k in lands if not l.is_basic)
        total_lands = sum(k for _, k in lands) or 1
        strain += 0.4 * (ncol - 1) * max(0.0, 0.35 - duals / total_lands)
    cmd = 0.3 * card_power(commander, meta_freq) / 10 if commander else 0.0
    return round(power + 2.0 * synergy - 2.0 * curve_err - strain + cmd, 3)


def _deck_name(colors, archetype, profile, commander=None) -> tuple[str, list[str]]:
    theme_items = [(t, v) for t, v in profile.items() if t in THEME_LABELS]
    theme_items.sort(key=lambda x: -x[1])
    tribes = [(t[5:], v) for t, v in profile.items() if t.startswith("payoff:") and v >= 3]
    tribes.sort(key=lambda x: -x[1])
    labels = []
    if tribes and profile.get("type:" + tribes[0][0], 0) >= 8:
        labels.append(tribes[0][0] + "s")
    labels += [THEME_LABELS[t] for t, v in theme_items[:2] if v >= 8]
    color_name = COLOR_NAMES.get(colors, colors)
    if commander:
        name = f"{commander.export_name} ({color_name}{' ' + labels[0] if labels else ''})"
    else:
        name = f"{color_name} {labels[0] + ' ' if labels else ''}{archetype.title()}"
    return name, labels


def classify(main) -> str:
    """Label a finished deck from what is actually in it."""
    n = sum(k for _, k in main) or 1
    creatures = sum(k for c, k in main if c.is_creature) / n
    inter = sum(k for c, k in main if roles(c) & (INTERACTION | {"draw"})) / n
    avg = _avg_cmc(main)
    if avg <= 2.7 and creatures >= 0.45:
        return "aggro"
    if creatures <= 0.35 and inter >= 0.25:
        return "control"
    return "midrange"


def _color_check(main, colors, spells) -> bool:
    if len(colors) <= 1:
        return True
    per = Counter()
    for c, k in main:
        for col in c.colors:
            per[col] += k
    return all(per[col] >= max(4, 0.1 * spells) for col in colors)


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def owned_pool(catalog, owned, fmt: Format):
    pool = []
    for key, qty in owned.items():
        card = catalog.get(key)
        if card and qty > 0 and is_legal(card.legalities, fmt):
            pool.append((card, qty))
    return pool


def build_decks(catalog: dict[str, CardInfo], owned: dict[str, int], fmt: Format,
                meta_freq: dict[str, float] | None = None, top_n: int = 5,
                archetypes=("aggro", "midrange", "control")) -> list[DeckResult]:
    """Return the best `top_n` decks buildable from `owned` in format `fmt`."""
    meta_freq = meta_freq or {}
    pool = owned_pool(catalog, owned, fmt)
    basics = basics_from_catalog(catalog)
    spells_pool = [(c, n) for c, n in pool if not c.is_land]
    land_pool = [(c, n) for c, n in pool if c.is_land and not c.is_basic]
    all_types = {st for c, _ in spells_pool if c.is_creature for st in c.subtypes}
    payoffs = {c.key: tribal_mentions(c, all_types) for c, _ in spells_pool}
    results: list[DeckResult] = []

    if fmt.commander:
        jobs = _commander_jobs(spells_pool, fmt, meta_freq)
    else:
        jobs = [(None, "".join(combo)) for k in (1, 2, 3) for combo in combinations("WUBRG", k)]

    for commander, colors in jobs:
        colset = set(colors)
        if commander:
            cpool = [(c, n) for c, n in spells_pool
                     if c.key != commander.key and set(c.color_identity) <= colset]
        else:
            cpool = [(c, n) for c, n in spells_pool if set(c.colors) <= colset]
        # prune to the strongest candidates: the greedy fill never reaches deep into the pool
        keep = 220 if fmt.singleton else 140
        if len(cpool) > keep:
            cpool.sort(key=lambda x: -(card_power(x[0], meta_freq) + 0.3 * len(themes(x[0]))
                                      + 0.5 * bool(payoffs.get(x[0].key))))
            cpool = cpool[:keep]
        lpool = [(l, n) for l, n in land_pool if set(l.color_identity) <= colset or not fmt.commander]
        limit = 1 if fmt.singleton else fmt.copy_limit
        playable = sum(min(n, limit) for _, n in cpool)
        for arch in archetypes:
            n_lands = ARCHETYPES[arch]["lands"] if fmt.deck_size == 60 else 39
            if fmt.commander and fmt.deck_size == 60:
                n_lands = 24
            spells = fmt.deck_size - n_lands - (1 if commander else 0)
            if playable < spells:
                continue
            prior = Counter()
            if commander:
                for t in themes(commander):
                    prior[t] += 12
                for st in commander.subtypes:
                    prior["type:" + st] += 6
                for st in payoffs.get(commander.key, ()):
                    prior["payoff:" + st] += 6
            builder = _Builder(cpool, fmt, arch, spells, meta_freq, payoffs, prior, commander)
            main, profile = builder.build()
            # second pass: steer towards the synergies the first pass found
            builder.prior = prior + Counter({k: v for k, v in profile.items()})
            new_lands = land_count(_avg_cmc(main), fmt.deck_size, arch)
            if fmt.commander and fmt.deck_size == 60:
                new_lands = max(22, min(26, new_lands))
            builder.spells = fmt.deck_size - new_lands - (1 if commander else 0)
            builder.curve_target = {b: v * builder.spells / sum(builder.arch["curve"].values())
                                    for b, v in builder.arch["curve"].items()}
            main, profile = builder.build()
            n_main = sum(n for _, n in main)
            if n_main < builder.spells or not _color_check(main, colors, n_main):
                continue
            n_lands = fmt.deck_size - n_main - (1 if commander else 0)
            lands = build_manabase(main + ([(commander, 1)] if commander else []), colors, n_lands,
                                   lpool, basics, limit)
            if sum(n for _, n in lands) < n_lands:
                continue
            label = classify(main)
            name, labels = _deck_name(colors, label, profile, commander)
            deck = DeckResult(name=name, format=fmt.key, colors=colors, archetype=label, main=main,
                              lands=lands, commander=commander, themes=labels)
            deck.score = _score_deck(main, lands, colors, builder.curve_target, meta_freq, commander)
            deck.notes = _explain(deck, meta_freq)
            results.append(deck)

    results.sort(key=lambda d: -d.score)
    kept: list[DeckResult] = []
    for d in results:
        if all(_jaccard(d.keys, k.keys) < 0.7 for k in kept):
            same = sum(1 for k in kept if k.name == d.name or k.name.startswith(d.name + " #"))
            if same:
                d.name = f"{d.name} #{same + 1}"
            kept.append(d)
        if len(kept) >= top_n:
            break
    return kept


def _commander_jobs(spells_pool, fmt, meta_freq, max_commanders: int = 8):
    cands = []
    for c, _ in spells_pool:
        if not c.can_be_commander or not c.color_identity:
            continue
        support = sum(1 for o, _ in spells_pool if set(o.color_identity) <= set(c.color_identity))
        cands.append((card_power(c, meta_freq) + 0.02 * support, c))
    cands.sort(key=lambda x: -x[0])
    return [(c, c.color_identity) for _, c in cands[:max_commanders]]


def _explain(deck: DeckResult, meta_freq) -> list[str]:
    main = sorted(deck.main, key=lambda x: -card_power(x[0], meta_freq))
    notes = []
    key_cards = ", ".join(c.export_name for c, _ in main[:5])
    notes.append(f"Key cards: {key_cards}.")
    creatures = sum(n for c, n in deck.main if c.is_creature)
    inter = sum(n for c, n in deck.main if roles(c) & INTERACTION)
    draw = sum(n for c, n in deck.main if "draw" in roles(c))
    n_lands = sum(n for _, n in deck.lands)
    duals = sum(n for l, n in deck.lands if not l.is_basic)
    notes.append(f"{creatures} creatures, {inter} removal/counterspells, {draw} card-advantage spells.")
    notes.append(f"{n_lands} lands ({duals} non-basic); average mana value {_avg_cmc(deck.main):.2f}.")
    if deck.themes:
        notes.append("Synergy: " + ", ".join(deck.themes) + ".")
    in_meta = [c.export_name for c, _ in main if meta_freq.get(c.key, 0) >= 0.2]
    if in_meta:
        notes.append("Meta staples included: " + ", ".join(in_meta[:6]) + ".")
    return notes
