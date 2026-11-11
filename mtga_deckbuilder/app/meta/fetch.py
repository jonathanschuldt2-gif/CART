"""Opt-in fetch of plain-text decklists from URLs the user supplies.

Point it at a page that returns Arena/MTGO deck text (most deck sites have a
"download .txt" / "export" link). Responses are cached on disk and requests
are spaced at least a couple of seconds apart.
"""
import hashlib
import time
from urllib.parse import urlparse

import httpx

from app import config
from app.importers.arena_text import parse_arena_text

CACHE = config.DATA_DIR / "meta_cache"
MIN_INTERVAL = 2.0
_last = 0.0


def fetch_deck_text(url: str, use_cache: bool = True) -> str:
    global _last
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("Only http(s) URLs are supported")
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".txt")
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")
    wait = MIN_INTERVAL - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    r = httpx.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=30, follow_redirects=True)
    r.raise_for_status()
    text = r.text
    if "<html" in text[:500].lower() or sum(row.quantity for row in parse_arena_text(text)) < 20:
        raise ValueError("That URL didn't return a plain-text decklist. Use the site's text export/download link.")
    path.write_text(text, encoding="utf-8")
    return text
