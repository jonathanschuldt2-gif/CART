"""CSV/TSV collection exports (Untapped.gg, Aetherhub, MTGA Assistant, Moxfield, ...)."""
import csv
import io

from app.importers.rows import ImportRow

ALIASES = {
    "name": {"name", "card", "card name", "cardname", "card title", "title"},
    "quantity": {"quantity", "count", "qty", "amount", "owned", "copies", "number owned",
                 "have", "total", "collected", "num"},
    "set_code": {"set", "set code", "setcode", "edition", "edition code", "expansion", "set id"},
    "collector_number": {"collector number", "collectornumber", "number", "cn", "card number",
                         "collector no", "collector #", "no"},
    "arena_id": {"arena id", "arenaid", "mtga id", "mtgaid", "grpid", "grp id", "id arena", "arena"},
}


def _norm_header(h: str) -> str:
    return " ".join((h or "").strip().lower().replace("_", " ").replace("-", " ").split())


def map_headers(headers: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for idx, h in enumerate(headers):
        key = _norm_header(h)
        for field, names in ALIASES.items():
            if key in names and field not in found:
                found[field] = idx
    return found


def looks_like_csv(text: str) -> bool:
    first = next((l for l in text.splitlines() if l.strip()), "")
    for delim in (",", "\t", ";"):
        if delim in first and "name" in map_headers(next(csv.reader([first], delimiter=delim))):
            return True
    return False


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def parse_csv(text: str) -> list[ImportRow]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        return []
    cols = map_headers(rows[0])
    if "name" not in cols:
        raise ValueError("CSV has no recognisable card-name column")
    out: list[ImportRow] = []
    for i, r in enumerate(rows[1:], 2):
        get = lambda f: r[cols[f]].strip() if f in cols and cols[f] < len(r) else ""
        name = get("name")
        if not name:
            continue
        qty = _int(get("quantity"), 1) if "quantity" in cols else 1
        if qty <= 0:
            continue
        aid = _int(get("arena_id"), 0) or None
        out.append(ImportRow(
            name=name, quantity=qty, set_code=get("set_code").upper(),
            collector_number=get("collector_number"), arena_id=aid, line_no=i,
            raw=",".join(r),
        ))
    return out
