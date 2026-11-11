"""Follows Player.log as Arena writes to it."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable


class LogWatcher(threading.Thread):
    """Background thread that sends new log lines to `on_lines`.

    Reads the whole existing file first, so a draft already in progress is
    rebuilt. Starts again from the top when Arena restarts and truncates the log.
    """

    def __init__(self, path: Path, on_lines: Callable[[list[str]], None],
                 on_status: Callable[[str], None] | None = None, poll_seconds: float = 0.5):
        super().__init__(daemon=True)
        self.path = Path(path)
        self.on_lines = on_lines
        self.on_status = on_status or (lambda msg: None)
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        position = 0
        partial = b""
        missing_reported = False
        while not self._stop.is_set():
            try:
                size = self.path.stat().st_size
            except OSError:
                if not missing_reported:
                    self.on_status(f"Waiting for log file: {self.path}")
                    missing_reported = True
                time.sleep(2)
                continue
            missing_reported = False

            if size < position:  # Arena restarted and truncated the log
                position, partial = 0, b""
            if size > position:
                try:
                    with self.path.open("rb") as f:
                        f.seek(position)
                        chunk = f.read()
                        position = f.tell()
                except OSError as exc:
                    self.on_status(f"Can't read log: {exc}")
                    time.sleep(2)
                    continue
                pieces = (partial + chunk).split(b"\n")
                partial = pieces.pop()  # last piece may be an unfinished line
                if pieces:
                    self.on_lines([p.decode("utf-8", errors="replace") + "\n" for p in pieces])
            self._stop.wait(self.poll_seconds)
