"""Maps Arena card IDs (grpIds) to card details.

Sources, in order of preference:
  1. Arena's own card database (Raw_CardDatabase_*.mtga, a SQLite file installed
     with the game). It has every card in the client, including brand-new sets.
  2. 17Lands rating rows, which include mtga_id, name, color, rarity and types.
  3. Scryfall, which fills in mana values by card name when they are missing.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import config

ARENA_COLORS = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}
ARENA_TYPES = {1: "Artifact", 2: "Creature", 3: "Enchantment", 4: "Instant", 5: "Land",
               8: "Planeswalker", 10: "Sorcery", 11: "Kindred", 14: "Battle"}
ARENA_RARITY = {1: "basic", 2: "common", 3: "uncommon", 4: "rare", 5: "mythic"}
WUBRG = "WUBRG"


@dataclass
class Card:
    grp_id: int
    name: str
    colors: str = ""                 # e.g. "WU"; "" = colorless
    mana_value: float | None = None
    types: list[str] = field(default_factory=list)
    rarity: str = ""

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.types

    @property
    def is_land(self) -> bool:
        return "Land" in self.types


def normalize_colors(text: str) -> str:
    return "".join(c for c in WUBRG if c in (text or "").upper())


def mana_value_from_arena_text(text: str | None) -> float | None:
    """'o2oWoW' -> 4, 'o(W/U)o(W/U)' -> 2, 'oXoR' -> 1."""
    if not text:
        return None
    total = 0
    for token in text.split("o"):
        token = token.strip("()")
        if not token:
            continue
        if token.isdigit():
            total += int(token)
        elif token.upper() in ("X", "Y", "Z"):
            continue
        else:
            total += 1
    return float(total)


def _parse_types(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        words = []
        for v in value:
            words.extend(str(v).replace("—", " ").split())
        return words
    return str(value).replace("—", " ").replace("-", " ").split()


class CardDB:
    def __init__(self):
        self.cards: dict[int, Card] = {}
        self.source = "none"

    def get(self, grp_id: int) -> Card:
        card = self.cards.get(grp_id)
        if card is None:
            card = Card(grp_id=grp_id, name=f"Unknown card #{grp_id}")
        return card

    # ---- Arena's local database ---------------------------------------
    def load_arena_db(self, search_dirs: list[Path] | None = None) -> bool:
        dirs = search_dirs if search_dirs is not None else config.default_arena_data_dirs()
        files = sorted((f for d in dirs for f in Path(d).glob("Raw_CardDatabase_*.mtga")),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files:
            try:
                n = self._read_arena_db(f)
            except sqlite3.Error:
                continue
            if n:
                self.source = f"Arena card database ({f.name})"
                return True
        return False

    def _read_arena_db(self, path: Path) -> int:
        uri = "file:" + urllib.parse.quote(str(path.resolve()).replace("\\", "/")) + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "Cards" not in tables:
                return 0
            cols = {r[1] for r in con.execute("PRAGMA table_info(Cards)")}
            names = self._read_localizations(con, tables)

            wanted = [c for c in ("GrpId", "TitleId", "Colors", "Types", "Rarity", "OldSchoolManaText") if c in cols]
            if "GrpId" not in wanted:
                return 0
            count = 0
            for row in con.execute(f"SELECT {', '.join(wanted)} FROM Cards"):
                r = dict(zip(wanted, row))
                grp = int(r["GrpId"])
                found = {ARENA_COLORS.get(int(x), "") for x in str(r.get("Colors") or "").split(",")
                         if x.strip().isdigit()}
                colors = "".join(c for c in WUBRG if c in found)
                types = [ARENA_TYPES[int(x)] for x in str(r.get("Types") or "").split(",")
                         if x.strip().isdigit() and int(x) in ARENA_TYPES]
                self.cards[grp] = Card(
                    grp_id=grp,
                    name=names.get(r.get("TitleId"), f"Unknown card #{grp}"),
                    colors=colors,
                    mana_value=mana_value_from_arena_text(r.get("OldSchoolManaText")),
                    types=types,
                    rarity=ARENA_RARITY.get(r.get("Rarity") or 0, ""),
                )
                count += 1
            return count
        finally:
            con.close()

    @staticmethod
    def _read_localizations(con: sqlite3.Connection, tables: set[str]) -> dict[int, str]:
        table = next((t for t in ("Localizations_enUS", "Localizations") if t in tables), None)
        if table is None:
            return {}
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        text_col = next((c for c in ("Loc", "enUS", "Text") if c in cols), None)
        if "LocId" not in cols or text_col is None:
            return {}
        order = " ORDER BY Formatted DESC" if "Formatted" in cols else ""
        names: dict[int, str] = {}
        # Later rows overwrite earlier ones, so with DESC the least-formatted text wins.
        for loc_id, text in con.execute(f"SELECT LocId, {text_col} FROM {table}{order}"):
            if text:
                names[loc_id] = re.sub(r"<[^>]+>", "", str(text))
        return names

    # ---- 17Lands rows ---------------------------------------------------
    def add_from_ratings(self, rows: list[dict]) -> None:
        """Fill in cards that Arena's DB didn't give us, using 17Lands rating rows."""
        for row in rows:
            grp = row.get("mtga_id")
            if grp is None:
                continue
            grp = int(grp)
            existing = self.cards.get(grp)
            if existing and not existing.name.startswith("Unknown"):
                continue
            self.cards[grp] = Card(
                grp_id=grp,
                name=row.get("name", f"Unknown card #{grp}"),
                colors=normalize_colors(row.get("color", "")),
                types=_parse_types(row.get("types")),
                rarity=str(row.get("rarity", "")).lower(),
            )
        if self.source == "none" and rows:
            self.source = "17Lands card list"

    # ---- Scryfall mana values -------------------------------------------
    def fill_mana_values(self, set_code: str) -> None:
        """Get missing mana values from Scryfall (cached on disk), matched by name."""
        missing = [c for c in self.cards.values() if c.mana_value is None]
        if not missing or not set_code:
            return
        by_name = load_scryfall_mana_values(set_code)
        for card in missing:
            mv = by_name.get(card.name.lower()) or by_name.get(card.name.split(" // ")[0].lower())
            if mv is not None:
                card.mana_value = mv


def load_scryfall_mana_values(set_code: str) -> dict[str, float]:
    cache = config.cache_dir() / f"scryfall_{set_code.lower()}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 7 * 86400:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    result: dict[str, float] = {}
    url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode(
        {"q": f"set:{set_code.lower()}", "unique": "cards"})
    try:
        while url:
            req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                page = json.load(resp)
            for c in page.get("data", []):
                name = c.get("name", "")
                result[name.lower()] = float(c.get("cmc", 0))
                result[name.split(" // ")[0].lower()] = float(c.get("cmc", 0))
            url = page.get("next_page") if page.get("has_more") else None
            time.sleep(0.1)  # Scryfall asks for 50-100ms between requests
    except (OSError, ValueError):
        return result
    if result:
        cache.write_text(json.dumps(result), encoding="utf-8")
    return result
