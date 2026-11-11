import json

from app.importers.arena_text import parse_arena_text
from app.importers.csv_generic import looks_like_csv, parse_csv
from app.importers.rows import ImportRow


def parse_json(text: str) -> list[ImportRow]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("cards") or data.get("collection") or []
    rows = []
    for i, d in enumerate(data, 1):
        name = d.get("name") or d.get("card") or ""
        if not name:
            continue
        rows.append(ImportRow(
            name=name, quantity=int(d.get("quantity", d.get("count", 1)) or 1),
            set_code=str(d.get("set", d.get("set_code", "")) or "").upper(),
            collector_number=str(d.get("collector_number", "") or ""),
            arena_id=d.get("arena_id") or None, line_no=i, raw=json.dumps(d),
        ))
    return rows


def detect_format(text: str) -> str:
    s = text.lstrip()
    if s.startswith(("[", "{")):
        return "json"
    if looks_like_csv(text):
        return "csv"
    return "arena"


def parse_any(text: str) -> tuple[str, list[ImportRow]]:
    text = text.lstrip("﻿")
    kind = detect_format(text)
    parser = {"json": parse_json, "csv": parse_csv, "arena": parse_arena_text}[kind]
    return kind, parser(text)
