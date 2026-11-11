from collections import Counter

from app.engine.cardinfo import CardInfo
from app.formats import Format, is_legal


def validate_deck(main: Counter, catalog: dict[str, CardInfo], fmt: Format,
                  sideboard: Counter | None = None, commander: str | None = None) -> list[str]:
    """Return a list of problems ('' list = legal)."""
    problems = []
    sideboard = sideboard or Counter()
    size = sum(main.values()) + (1 if commander else 0)
    if fmt.exact_size and size != fmt.deck_size:
        problems.append(f"Deck has {size} cards; {fmt.name} needs exactly {fmt.deck_size}.")
    elif size < fmt.deck_size:
        problems.append(f"Deck has {size} cards; {fmt.name} needs at least {fmt.deck_size}.")
    if sum(sideboard.values()) > fmt.sideboard:
        problems.append(f"Sideboard has {sum(sideboard.values())} cards; max is {fmt.sideboard}.")
    if fmt.commander:
        if not commander:
            problems.append(f"{fmt.name} needs a commander.")
        elif commander in catalog and not catalog[commander].can_be_commander:
            problems.append(f"{catalog[commander].name} can't be a commander.")
    identity = set(catalog[commander].color_identity) if commander in catalog else None
    total = Counter(main)
    total.update(sideboard)
    if commander:
        total[commander] += 1
    for key, n in total.items():
        card = catalog.get(key)
        if card is None:
            problems.append(f"Unknown card: {key}")
            continue
        if not is_legal(card.legalities, fmt):
            problems.append(f"{card.name} is not legal in {fmt.name}.")
        limit = 1 if fmt.singleton else fmt.copy_limit
        if n > limit and not card.is_basic and not card.any_number:
            problems.append(f"{n} copies of {card.name} (limit {limit}).")
        if identity is not None and not set(card.color_identity) <= identity:
            problems.append(f"{card.name} is outside the commander's color identity.")
    return problems
