"""Ranks the cards in a pack, taking the picks so far into account.

    score = base + color_fit + curve_fit + signal

base       How strong the card is: its 17Lands GIH win rate as a z-score within
           the set. Once you're committed to two colors, this blends toward the
           card's win rate in decks of that exact pair.
color_fit  How well it fits your colors. Each pick adds weight to its colors.
           Commitment ramps from 0 (early pack 1, take the best card) to 1
           (around pack 2), and on/off-color bonuses scale with it.
curve_fit  Late in the draft, extra value for creatures and 2-drops when the
           pool is short on them.
signal     A good card that's still in the pack well after its average
           last-seen pick suggests its color is open.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .cards import WUBRG, Card, CardDB
from .draft_state import DraftState
from .ratings import Ratings


@dataclass
class PoolSummary:
    color_weights: dict[str, float]
    main_colors: str              # e.g. "UB" (may be "" or 1 color early)
    commitment: float             # 0..1
    creatures: int
    two_drops: int
    curve: dict[int, int]         # mana value (capped at 6) -> count among nonland cards
    size: int


@dataclass
class ScoredCard:
    card: Card
    score: float
    gih_wr: float | None
    alsa: float | None
    reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return ", ".join(self.reasons)


def _card_z(card: Card, ratings: Ratings) -> float:
    z = ratings.overall.z(ratings.overall.get(card.grp_id, card.name))
    if z is None:
        if card.is_land and not card.colors and card.rarity in ("basic", ""):
            return config.RARITY_DEFAULT_Z["basic"]
        z = config.RARITY_DEFAULT_Z.get(card.rarity, -0.3)
    return z


def summarize_pool(state: DraftState, db: CardDB, ratings: Ratings) -> PoolSummary:
    pool = [db.get(g) for g in state.pool]
    weights = {c: 0.0 for c in WUBRG}
    creatures = two_drops = 0
    curve: dict[int, int] = {}
    for card in pool:
        if card.colors:
            # Better cards pull harder toward their colors; gold cards split their pull.
            pull = max(0.2, _card_z(card, ratings) + 1.0) / len(card.colors)
            for c in card.colors:
                weights[c] += pull
        if card.is_creature:
            creatures += 1
        if card.mana_value is not None and not card.is_land:
            mv = int(min(card.mana_value, 6))
            curve[mv] = curve.get(mv, 0) + 1
            if card.mana_value == 2 and card.is_creature:
                two_drops += 1

    ranked = sorted((c for c in WUBRG if weights[c] > 0), key=lambda c: -weights[c])
    main = "".join(c for c in WUBRG if c in ranked[:2])

    # Commitment grows with the pick number, and faster when the pool is concentrated.
    progress = (state.overall_pick - config.COMMIT_START_PICK) / config.COMMIT_RAMP_PICKS
    total = sum(weights.values())
    concentration = (sum(weights[c] for c in ranked[:2]) / total) if total else 0.0
    commitment = max(0.0, min(1.0, progress)) * (0.5 + 0.5 * concentration)
    return PoolSummary(weights, main, commitment, creatures, two_drops, curve, len(pool))


def _color_affinity(colors: str, summary: PoolSummary) -> float:
    """1.0 if every color of the card is one of your main colors, down to 0.0."""
    w = summary.color_weights
    main = summary.main_colors
    if not main:
        return 1.0
    second = min(w[c] for c in main) or 1.0
    affinities = [1.0 if c in main else min(1.0, w[c] / second) for c in colors]
    return min(affinities)


def score_pack(state: DraftState, db: CardDB, ratings: Ratings) -> tuple[list[ScoredCard], PoolSummary]:
    summary = summarize_pool(state, db, ratings)
    c = summary.commitment
    pair_table = ratings.pair(summary.main_colors) if c >= 0.5 and len(summary.main_colors) == 2 else None
    late = max(0.0, (state.overall_pick - 2 * max(state.max_pack_size, 13)) / max(state.max_pack_size, 13))
    picks_left_frac = max(0.0, 1.0 - state.overall_pick / (3 * max(state.max_pack_size, 13)))

    results = []
    for grp in state.pack:
        card = db.get(grp)
        rating = ratings.overall.get(card.grp_id, card.name)
        reasons: list[str] = []

        base = _card_z(card, ratings)
        if rating and rating.gih_wr is not None:
            reasons.append(f"{rating.gih_wr * 100:.1f}% GIH")
        else:
            reasons.append("no 17Lands data")

        # Color fit
        if not card.colors:
            fit = c * config.COLORLESS_BONUS if not card.is_land else 0.0
            if c > 0.3 and not card.is_land:
                reasons.append("colorless, fits any deck")
        else:
            a = _color_affinity(card.colors, summary)
            fit = c * (config.ON_COLOR_BONUS * a - config.OFF_COLOR_PENALTY * (1 - a))
            if c > 0.2 and summary.main_colors:
                if a >= 0.999:
                    reasons.append(f"on-color ({summary.main_colors})")
                elif a < 0.35:
                    reasons.append(f"off-color for {summary.main_colors}")
                else:
                    reasons.append("splash/secondary color")
            if pair_table and a >= 0.999:
                pz = pair_table.z(pair_table.get(card.grp_id, card.name))
                if pz is not None:
                    base = (1 - config.PAIR_RATING_BLEND * c) * base + config.PAIR_RATING_BLEND * c * pz
                    pr = pair_table.get(card.grp_id, card.name)
                    reasons.append(f"{pr.gih_wr * 100:.1f}% in {summary.main_colors}")

        # Curve / deck shape (pack 3 mostly)
        curve = 0.0
        if late > 0 and not card.is_land:
            need_creatures = max(0, config.TARGET_CREATURES * (1 - picks_left_frac) - summary.creatures)
            if card.is_creature and need_creatures > 0:
                curve += config.CURVE_BONUS * min(1.0, need_creatures / 4) * late
                reasons.append(f"need creatures ({summary.creatures})")
            if card.is_creature and card.mana_value == 2 and summary.two_drops < config.TARGET_TWO_DROPS:
                curve += config.CURVE_BONUS * 0.5 * late
                reasons.append(f"fills 2-drop ({summary.two_drops})")

        # Signal: still here well after its usual last-seen pick
        signal = 0.0
        if rating and rating.alsa is not None and state.pack_number < 3 and base > 0.3:
            lateness = state.pick_number - rating.alsa
            if lateness >= config.SIGNAL_MIN_PICKS_LATE:
                signal = config.SIGNAL_BONUS * min(1.0, lateness / 4)
                reasons.append(f"late (ALSA {rating.alsa:.1f}) - open signal")

        results.append(ScoredCard(card, base + fit + curve + signal,
                                  rating.gih_wr if rating else None,
                                  rating.alsa if rating else None, reasons))

    results.sort(key=lambda s: -s.score)
    return results, summary
