import re
import unicodedata

_WS = re.compile(r"\s+")


def norm_name(name: str) -> str:
    """Case/accent/punctuation-insensitive key for matching card names."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'").replace("‘", "'").replace("///", "//")
    s = s.lower().strip()
    s = re.sub(r"\s*//\s*", " // ", s)
    return _WS.sub(" ", s)


def front_face(name: str) -> str:
    return norm_name(name).split(" // ")[0]


def strip_alchemy(name: str) -> str:
    """'A-Card Name' (Alchemy rebalanced) -> 'Card Name'."""
    return name[2:] if name.startswith("A-") else name
