"""Download Scryfall bulk card data and load the Arena printings into the DB."""
import json
from pathlib import Path
from typing import Iterable, Iterator

import httpx
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app import config
from app.cards.normalize import front_face, norm_name
from app.models import Card

BULK_INDEX = "https://api.scryfall.com/bulk-data/default-cards"
SKIP_LAYOUTS = {"token", "double_faced_token", "art_series", "emblem", "vanguard", "scheme", "planar"}
COLOR_ORDER = "WUBRG"


def _colors(lst) -> str:
    return "".join(c for c in COLOR_ORDER if c in (lst or []))


def download_bulk(dest: Path = config.SCRYFALL_CACHE) -> Path:
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client:
        info = client.get(BULK_INDEX).raise_for_status().json()
        tmp = dest.with_suffix(".part")
        with client.stream("GET", info["download_uri"], timeout=600) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        tmp.replace(dest)
    return dest


def iter_bulk_file(path: Path) -> Iterator[dict]:
    """Scryfall bulk files put one card per line; parse lazily to save memory."""
    with open(path, encoding="utf-8") as fh:
        first = fh.readline()
        if first.strip() not in ("[", ""):
            fh.seek(0)
            yield from json.load(fh)
            return
        for line in fh:
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            yield json.loads(line)


def card_record(raw: dict) -> dict | None:
    if "arena" not in (raw.get("games") or []):
        return None
    if raw.get("layout") in SKIP_LAYOUTS:
        return None
    faces = raw.get("card_faces") or []
    front = faces[0] if faces else {}
    oracle = raw.get("oracle_text")
    if oracle is None:
        oracle = "\n//\n".join(f.get("oracle_text", "") for f in faces)
    colors = raw.get("colors")
    if colors is None:
        colors = sorted({c for f in faces for c in (f.get("colors") or [])})
    return {
        "id": raw["id"],
        "arena_id": raw.get("arena_id"),
        "oracle_id": raw.get("oracle_id") or front.get("oracle_id") or "",
        "name": raw["name"],
        "name_key": norm_name(raw["name"]),
        "front_key": front_face(raw["name"]),
        "set_code": (raw.get("set") or "").upper(),
        "collector_number": str(raw.get("collector_number") or ""),
        "rarity": raw.get("rarity") or "common",
        "cmc": float(raw.get("cmc") or 0),
        "mana_cost": raw.get("mana_cost") if raw.get("mana_cost") is not None else front.get("mana_cost", ""),
        "colors": _colors(colors),
        "color_identity": _colors(raw.get("color_identity")),
        "type_line": raw.get("type_line") or front.get("type_line", ""),
        "oracle_text": oracle or "",
        "power": str(raw.get("power", front.get("power", "")) or ""),
        "toughness": str(raw.get("toughness", front.get("toughness", "")) or ""),
        "keywords_json": json.dumps(raw.get("keywords") or []),
        "legalities_json": json.dumps(raw.get("legalities") or {}),
        "produced_mana": _colors(raw.get("produced_mana")),
        "layout": raw.get("layout") or "normal",
    }


def load_cards(db: Session, raws: Iterable[dict]) -> int:
    records = {}
    for raw in raws:
        rec = card_record(raw)
        if rec:
            records[rec["id"]] = rec
    existing = set(db.scalars(select(Card.id)))
    new = [r for k, r in records.items() if k not in existing]
    old = [r for k, r in records.items() if k in existing]
    if new:
        db.execute(insert(Card), new)
    if old:
        db.execute(update(Card), old)
    db.commit()
    return len(records)


def refresh_card_db(db: Session, download: bool = True) -> int:
    path = config.SCRYFALL_CACHE
    if download or not path.exists():
        download_bulk(path)
    return load_cards(db, iter_bulk_file(path))
