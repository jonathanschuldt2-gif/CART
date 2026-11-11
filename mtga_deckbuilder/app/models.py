import json
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Card(Base):
    """One Arena printing of a card (from Scryfall)."""

    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # scryfall id
    arena_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    oracle_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    name: Mapped[str] = mapped_column(String(255), index=True)
    name_key: Mapped[str] = mapped_column(String(255), index=True)
    front_key: Mapped[str] = mapped_column(String(255), index=True)
    set_code: Mapped[str] = mapped_column(String(16), index=True)
    collector_number: Mapped[str] = mapped_column(String(16))
    rarity: Mapped[str] = mapped_column(String(16))
    cmc: Mapped[float] = mapped_column(Float, default=0)
    mana_cost: Mapped[str] = mapped_column(String(128), default="")
    colors: Mapped[str] = mapped_column(String(8), default="")
    color_identity: Mapped[str] = mapped_column(String(8), default="")
    type_line: Mapped[str] = mapped_column(String(255), default="")
    oracle_text: Mapped[str] = mapped_column(Text, default="")
    power: Mapped[str] = mapped_column(String(8), default="")
    toughness: Mapped[str] = mapped_column(String(8), default="")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    legalities_json: Mapped[str] = mapped_column(Text, default="{}")
    produced_mana: Mapped[str] = mapped_column(String(16), default="")
    layout: Mapped[str] = mapped_column(String(32), default="normal")

    @property
    def keywords(self) -> list[str]:
        return json.loads(self.keywords_json or "[]")

    @property
    def legalities(self) -> dict:
        return json.loads(self.legalities_json or "{}")


class CollectionEntry(Base):
    __tablename__ = "collection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), unique=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    card: Mapped[Card] = relationship(lazy="joined")


class MetaDeck(Base):
    __tablename__ = "meta_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    format: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(512), default="")
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    text: Mapped[str] = mapped_column(Text)


class BuiltDeck(Base):
    __tablename__ = "built_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    format: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    text: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
