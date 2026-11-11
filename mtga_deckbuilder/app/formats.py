from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    key: str
    name: str
    legality_keys: tuple[str, ...]
    deck_size: int = 60
    copy_limit: int = 4
    sideboard: int = 15
    singleton: bool = False
    commander: bool = False
    exact_size: bool = False


FORMATS: dict[str, Format] = {f.key: f for f in [
    Format("standard", "Standard", ("standard",)),
    Format("alchemy", "Alchemy", ("alchemy",)),
    Format("explorer", "Explorer", ("explorer", "pioneer")),
    Format("historic", "Historic", ("historic",)),
    Format("timeless", "Timeless", ("timeless",)),
    Format("brawl", "Brawl", ("brawl", "historicbrawl"), deck_size=100, copy_limit=1,
           sideboard=0, singleton=True, commander=True, exact_size=True),
    Format("standardbrawl", "Standard Brawl", ("standardbrawl",), deck_size=60, copy_limit=1,
           sideboard=0, singleton=True, commander=True, exact_size=True),
]}

LEGAL = {"legal", "restricted"}


def is_legal(legalities: dict, fmt: Format) -> bool:
    for key in fmt.legality_keys:
        if key in legalities:
            return legalities[key] in LEGAL
    return False


def get_format(key: str) -> Format:
    try:
        return FORMATS[key]
    except KeyError:
        raise KeyError(f"Unknown format '{key}'. Choose from: {', '.join(FORMATS)}")
