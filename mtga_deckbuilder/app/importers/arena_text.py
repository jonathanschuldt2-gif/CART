"""Parse Arena deck/collection text, e.g. '4 Lightning Strike (M19) 152'."""
import re

from app.importers.rows import ImportRow

LINE = re.compile(
    r"^\s*(?:(\d+)\s*[xX]?\s+)?"          # quantity (optional, '4' or '4x')
    r"(.+?)"                              # name
    r"(?:\s+\(([A-Za-z0-9_]{2,8})\)"      # (SET)
    r"(?:\s+([A-Za-z0-9\-★\*]+))?)?"  # collector number
    r"\s*$"
)
SECTIONS = {
    "deck": "deck", "main": "deck", "maindeck": "deck", "main deck": "deck",
    "sideboard": "sideboard", "side": "sideboard",
    "commander": "commander", "companion": "companion",
}
SKIP_HEADERS = {"about"}


def parse_arena_text(text: str) -> list[ImportRow]:
    rows: list[ImportRow] = []
    section = "deck"
    explicit_sections = False
    saw_blank_after_cards = False
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            if rows and not explicit_sections:
                saw_blank_after_cards = True
            continue
        if line.startswith(("#", "//")):
            continue
        low = line.lower().rstrip(":")
        if low in SECTIONS:
            section, explicit_sections = SECTIONS[low], True
            continue
        if low in SKIP_HEADERS or low.startswith("name "):
            continue
        m = LINE.match(line)
        if not m or not m.group(2):
            continue
        qty, name, set_code, number = m.groups()
        sec = section
        if saw_blank_after_cards and not explicit_sections and section == "deck":
            sec = "sideboard"  # old Arena format: blank line separates the sideboard
        rows.append(ImportRow(
            name=name.strip(), quantity=int(qty) if qty else 1,
            set_code=(set_code or "").upper(), collector_number=number or "",
            section=sec, line_no=i, raw=raw,
        ))
    return rows


def to_arena_line(qty: int, name: str, set_code: str = "", number: str = "") -> str:
    if set_code and number:
        return f"{qty} {name} ({set_code.upper()}) {number}"
    return f"{qty} {name}"
