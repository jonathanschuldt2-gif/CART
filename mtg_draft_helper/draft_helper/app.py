"""Connects the log watcher, parser, card data, ratings and scorer."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .cards import CardDB
from .draft_state import DraftState
from .log_parser import LogParser
from .log_watcher import LogWatcher
from .ratings import Ratings
from .scorer import PoolSummary, ScoredCard, score_pack, summarize_pool


@dataclass
class Snapshot:
    """Everything the UI needs to draw one update."""
    status: str
    set_code: str = ""
    fmt: str = ""
    pack_number: int = 0
    pick_number: int = 0
    ranked: list[ScoredCard] = field(default_factory=list)
    summary: PoolSummary | None = None
    pool_names: list[str] = field(default_factory=list)
    has_ratings: bool = False


class DraftHelper:
    def __init__(self, set_override: str = "", format_override: str = "",
                 ratings_file: Path | None = None, arena_db_dirs: list[Path] | None = None,
                 offline: bool = False):
        self.updates: "queue.Queue[Snapshot]" = queue.Queue()
        self.parser = LogParser()
        self.set_override = set_override.upper()
        self.format_override = format_override
        self.ratings_file = ratings_file
        self.offline = offline
        self.db = CardDB()
        self.db.load_arena_db(arena_db_dirs)
        self.ratings: Ratings | None = None
        self._ratings_key: tuple[str, str] | None = None
        self._lock = threading.Lock()
        self._watcher: LogWatcher | None = None

    # ---- inputs -----------------------------------------------------------
    def watch(self, log_path: Path) -> None:
        self.post_status(f"Watching {log_path}\nWaiting for a draft… (make sure Detailed Logs are on)")
        self._watcher = LogWatcher(log_path, self.on_lines, self.post_status)
        self._watcher.start()

    def replay(self, log_path: Path, delay: float = 0.0) -> None:
        """Feed a saved log through the pipeline (for testing without Arena)."""
        def run():
            lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            for line in lines:
                if self.parser.feed_line(line):
                    self._publish()
                    if delay:
                        time.sleep(delay)
            self._publish()
        threading.Thread(target=run, daemon=True).start()

    def on_lines(self, lines: list[str]) -> None:
        with self._lock:
            changed = self.parser.feed_lines(lines)
        if changed:
            self._publish()

    def post_status(self, message: str) -> None:
        self.updates.put(Snapshot(status=message))

    # ---- processing ---------------------------------------------------------
    def _ensure_ratings(self, state: DraftState) -> None:
        set_code = self.set_override or state.set_code
        fmt = self.format_override or state.format_name
        key = (set_code, fmt)
        if key == self._ratings_key:
            return
        self._ratings_key = key
        if self.ratings_file:
            self.ratings = Ratings.from_file(self.ratings_file, set_code, fmt)
        else:
            self.post_status(f"Loading 17Lands ratings for {set_code or '?'} {fmt}…")
            self.ratings = Ratings(set_code, fmt, offline=self.offline)
        self.db.add_from_ratings(self.ratings.overall.rows)
        if not self.offline:
            self.db.fill_mana_values(set_code)

    def build_snapshot(self) -> Snapshot:
        with self._lock:
            state = self.parser.state
            if not state.pack and not state.pool:
                return Snapshot(status="Waiting for a draft…")
            self._ensure_ratings(state)
            ratings = self.ratings
            if state.pack:
                ranked, summary = score_pack(state, self.db, ratings)
            else:
                ranked, summary = [], summarize_pool(state, self.db, ratings)
            set_code = self.set_override or state.set_code
            fmt = self.format_override or state.format_name
            if state.pack:
                status = "Your pick"
            else:
                status = "Pick made, waiting for the next pack…"
            if not ratings.overall:
                status += f"  (no 17Lands data for {set_code or 'this set'} yet: using rarity only)"
            return Snapshot(
                status=status, set_code=set_code, fmt=fmt,
                pack_number=state.pack_number, pick_number=state.pick_number,
                ranked=ranked, summary=summary,
                pool_names=[self.db.get(g).name for g in state.pool],
                has_ratings=bool(ratings.overall),
            )

    def _publish(self) -> None:
        try:
            self.updates.put(self.build_snapshot())
        except Exception as exc:  # never let a bad log line kill the watcher thread
            self.post_status(f"Error: {exc!r}")
