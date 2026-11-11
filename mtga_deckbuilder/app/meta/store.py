from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.formats import FORMATS
from app.models import MetaDeck


def add_meta_deck(db: Session, fmt: str, name: str, text: str, source: str = "") -> MetaDeck:
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format {fmt}")
    name = name.strip() or "Unnamed deck"
    deck = db.scalar(select(MetaDeck).where(MetaDeck.format == fmt, MetaDeck.name == name))
    if deck is None:
        deck = MetaDeck(format=fmt, name=name)
        db.add(deck)
    deck.text, deck.source = text, source
    db.commit()
    return deck


def load_meta_folder(db: Session, root: Path = config.META_DIR) -> int:
    """Import data/meta/<format>/<Deck Name>.txt files."""
    n = 0
    for fmt in FORMATS:
        folder = root / fmt
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.txt")):
            add_meta_deck(db, fmt, path.stem, path.read_text(encoding="utf-8"), f"file:{path.name}")
            n += 1
    return n
