"""17Lands card ratings: download, cache and look up.

Uses the same public data that powers https://www.17lands.com/card_ratings.
Results are cached for a day so each set is downloaded about once a day.
"""
from __future__ import annotations

import json
import statistics
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import config

URL = "https://www.17lands.com/card_ratings/data"
COLOR_PAIRS = ["WU", "WB", "WR", "WG", "UB", "UR", "UG", "BR", "BG", "RG"]


@dataclass
class Rating:
    grp_id: int
    name: str
    gih_wr: float | None      # games-in-hand win rate (0-1)
    alsa: float | None        # average last seen at (pick number)
    iwd: float | None         # improvement when drawn
    games: int


def fetch_rows(set_code: str, fmt: str, colors: str | None = None, cache_only: bool = False) -> list[dict]:
    params = {"expansion": set_code.upper(), "format": fmt}
    if colors:
        params["colors"] = colors
    cache = config.cache_dir() / f"17l_{set_code.upper()}_{fmt}_{colors or 'all'}.json"
    fresh = cache.exists() and time.time() - cache.stat().st_mtime < config.RATINGS_CACHE_HOURS * 3600
    if fresh or (cache_only and cache.exists()):
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    if cache_only:
        return []
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.load(resp)
    except (OSError, ValueError):
        # Offline or 17Lands is down: use an old cache file if there is one.
        if cache.exists():
            try:
                return json.loads(cache.read_text(encoding="utf-8"))
            except ValueError:
                return []
        return []
    if isinstance(rows, list) and rows:
        cache.write_text(json.dumps(rows), encoding="utf-8")
        return rows
    return []


def _parse(rows: list[dict]) -> dict[int, Rating]:
    out = {}
    for r in rows:
        if r.get("mtga_id") is None:
            continue
        games = int(r.get("ever_drawn_game_count") or 0)
        gih = r.get("ever_drawn_win_rate")
        out[int(r["mtga_id"])] = Rating(
            grp_id=int(r["mtga_id"]),
            name=r.get("name", ""),
            gih_wr=float(gih) if gih is not None and games >= config.MIN_GAMES else None,
            alsa=float(r["avg_seen"]) if r.get("avg_seen") is not None else None,
            iwd=float(r["drawn_improvement_win_rate"]) if r.get("drawn_improvement_win_rate") is not None else None,
            games=games,
        )
    return out


class RatingTable:
    """GIH WR for one set/format, with z-scores relative to the set."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.by_id = _parse(rows)
        # Scryfall/Arena sometimes uses different grpIds than 17Lands for the same
        # card (alternate art etc.), so also index by name.
        self.by_name = {r.name.lower(): r for r in self.by_id.values() if r.name}
        values = [r.gih_wr for r in self.by_id.values() if r.gih_wr is not None]
        self.mean = statistics.fmean(values) if values else 0.55
        self.std = statistics.pstdev(values) if len(values) > 1 else 0.03
        if self.std <= 0:
            self.std = 0.03

    def __bool__(self) -> bool:
        return bool(self.by_id)

    def get(self, grp_id: int, name: str = "") -> Rating | None:
        return self.by_id.get(grp_id) or (self.by_name.get(name.lower()) if name else None)

    def z(self, rating: Rating | None) -> float | None:
        if rating is None or rating.gih_wr is None:
            return None
        return (rating.gih_wr - self.mean) / self.std


class Ratings:
    """All ratings for the current set: overall plus lazily-loaded color pairs."""

    def __init__(self, set_code: str, fmt: str, rows: list[dict] | None = None, offline: bool = False):
        self.set_code = set_code.upper()
        self.fmt = fmt
        self.offline = offline
        if rows is None:
            rows = fetch_rows(self.set_code, fmt, cache_only=offline) if self.set_code else []
            if not rows and fmt != "PremierDraft" and self.set_code:
                # Smaller formats may not have data yet; Premier Draft is the closest substitute.
                rows = fetch_rows(self.set_code, "PremierDraft", cache_only=offline)
        self.overall = RatingTable(rows)
        self._pairs: dict[str, RatingTable] = {}

    @classmethod
    def from_file(cls, path: Path, set_code: str = "", fmt: str = "PremierDraft") -> "Ratings":
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(set_code, fmt, rows=rows, offline=True)

    def pair(self, colors: str) -> RatingTable | None:
        if colors not in COLOR_PAIRS or not self.set_code or not self.overall:
            return None
        if colors not in self._pairs:
            self._pairs[colors] = RatingTable(fetch_rows(self.set_code, self.fmt, colors, cache_only=self.offline))
        table = self._pairs[colors]
        return table if table else None
