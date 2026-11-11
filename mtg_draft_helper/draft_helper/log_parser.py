"""Turns MTG Arena Player.log lines into DraftState updates.

Arena only logs draft data when "Detailed Logs (Plugin Support)" is enabled
(Options -> Account). Draft messages are JSON payloads, often with JSON nested
inside string fields such as "request" or "Payload". The exact method names change
between Arena updates, so this parser doesn't depend on them. It decodes every JSON
object it finds, including nested JSON strings, and looks for the field names
Arena uses for draft data:

  Premier / Traditional (human pods)
    Draft.Notify                {"draftId", "SelfPack", "SelfPick", "PackCards": "1,2,3"}   (1-based)
    Event_PlayerDraftMakePick   request: {"DraftId", "GrpId" | "GrpIds", "Pack", "Pick"}   (1-based)
  Quick Draft (bots)
    BotDraft_DraftStatus / BotDraft_DraftPick responses
        Payload: {"EventName", "PackNumber", "PickNumber", "DraftPack": [...], "PickedCards": [...]}  (0-based)
    BotDraft_DraftPick request: {"PickInfo": {"CardId", "PackNumber", "PickNumber"}}               (0-based)
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from .draft_state import DraftState

_DECODER = json.JSONDecoder()
_MAX_BUFFER_LINES = 400

PACK_KEYS = ("PackCards", "DraftPack", "CardsInPack")
POOL_KEYS = ("PickedCards",)
PICK_CARD_KEYS = ("GrpId", "GrpIds", "CardId", "CardIds", "PickGrpId")


def _to_ids(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [v for v in value.replace(" ", "").split(",") if v]
    if isinstance(value, (int, float)):
        value = [value]
    out = []
    for v in value:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _decode_nested(obj: Any, depth: int = 0) -> Any:
    """Recursively turn string fields that hold JSON into objects."""
    if depth > 6:
        return obj
    if isinstance(obj, dict):
        return {k: _decode_nested(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_nested(v, depth + 1) for v in obj]
    if isinstance(obj, str):
        s = obj.strip()
        if s[:1] in ("{", "[") and s[-1:] in ("}", "]"):
            try:
                return _decode_nested(json.loads(s), depth + 1)
            except ValueError:
                return obj
    return obj


def _walk_dicts(obj: Any) -> Iterable[dict]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def _int(d: dict, key: str) -> int | None:
    try:
        return int(d[key])
    except (KeyError, TypeError, ValueError):
        return None


class LogParser:
    """Feed it log lines; it keeps `state` up to date."""

    def __init__(self, state: DraftState | None = None):
        self.state = state or DraftState()
        self._buffer: list[str] = []

    # ---- line handling -------------------------------------------------
    def feed_lines(self, lines: Iterable[str]) -> bool:
        changed = False
        for line in lines:
            changed |= self.feed_line(line)
        return changed

    def feed_line(self, line: str) -> bool:
        if self._buffer:
            self._buffer.append(line)
            text = "".join(self._buffer)
            obj = self._try_decode(text)
            if obj is not None:
                self._buffer = []
                return self._handle(obj, text)
            if len(self._buffer) > _MAX_BUFFER_LINES:
                self._buffer = []
            return False

        if "{" not in line:
            return False
        obj = self._try_decode(line)
        if obj is not None:
            return self._handle(obj, line)
        # A JSON object that starts here but continues on later lines.
        if line.rstrip().endswith("{") or line.strip() == "{":
            self._buffer = [line]
        return False

    @staticmethod
    def _try_decode(text: str) -> Any | None:
        idx = text.find("{")
        while idx != -1:
            try:
                obj, _ = _DECODER.raw_decode(text, idx)
                return obj
            except ValueError:
                idx = text.find("{", idx + 1)
                # Only retry a few times; nested braces are covered by the first attempt.
                if idx > 2000:
                    return None
        return None

    # ---- message handling ----------------------------------------------
    def _handle(self, raw: Any, text: str = "") -> bool:
        obj = _decode_nested(raw)
        is_join = "Event_Join" in text or "EventJoin" in text
        changed = False
        for d in _walk_dicts(obj):
            changed |= self._handle_dict(d, is_join)
        return changed

    def _handle_dict(self, d: dict, is_join: bool = False) -> bool:
        s = self.state
        changed = False

        # Lobby messages list every event you're enrolled in, so the event name
        # is only trusted from a join request or from a message with draft data.
        draft_context = is_join or any(k in d for k in PACK_KEYS + POOL_KEYS + ("PickInfo", "DraftStatus"))
        event = d.get("EventName") or d.get("InternalEventName")
        if draft_context and isinstance(event, str) and "Draft" in event and event != s.event_name:
            s.reset(event_name=event)
            changed = True

        draft_id = d.get("DraftId") or d.get("draftId")
        if isinstance(draft_id, str) and draft_id and draft_id != s.draft_id:
            if s.draft_id:  # a different draft than the one we were tracking
                s.reset(event_name=s.event_name, draft_id=draft_id)
            else:
                s.draft_id = draft_id
            changed = True

        pack_key = next((k for k in PACK_KEYS if k in d), None)
        if pack_key is not None:
            changed |= self._handle_pack(d, pack_key)
        elif any(k in d for k in PICK_CARD_KEYS):
            changed |= self._handle_pick(d)

        for k in POOL_KEYS:
            if k in d and isinstance(d[k], list):
                s.pool_override = _to_ids(d[k])
                changed = True
        return changed

    def _numbers(self, d: dict) -> tuple[int | None, int | None]:
        """Pack and pick numbers from a message, converted to 1-based."""
        for pack_k, pick_k, zero_based in (
            ("SelfPack", "SelfPick", False),
            ("Pack", "Pick", False),
            ("PackNumber", "PickNumber", True),
        ):
            pack, pick = _int(d, pack_k), _int(d, pick_k)
            if pack is not None and pick is not None:
                return (pack + 1, pick + 1) if zero_based else (pack, pick)
        return None, None

    def _handle_pack(self, d: dict, key: str) -> bool:
        s = self.state
        cards = _to_ids(d[key])
        if not cards:
            return False
        pack, pick = self._numbers(d)
        if pack is None:
            # No numbers given: assume it follows the last pick.
            pack, pick = (s.pack_number or 1), (s.pick_number + 1 if s.pack_number else 1)
        if pack == 1 and pick == 1 and (s.picks or s.pool_override):
            s.reset(event_name=s.event_name, draft_id=s.draft_id)
        s.pack_number, s.pick_number, s.pack = pack, pick, cards
        if pick == 1:
            s.max_pack_size = max(s.max_pack_size, len(cards))
        return True

    def _handle_pick(self, d: dict) -> bool:
        s = self.state
        key = next(k for k in PICK_CARD_KEYS if k in d)
        ids = _to_ids(d[key])
        if not ids:
            return False
        pack, pick = self._numbers(d)
        if pack is None:
            if not s.pack:  # an unrelated message that happens to contain a GrpId
                return False
            pack, pick = s.pack_number, s.pick_number
        # Only accept picks of cards from the pack we're showing, when we know it.
        if s.pack and (pack, pick) == (s.pack_number, s.pick_number) and not set(ids) & set(s.pack):
            return False
        for offset, grp in enumerate(ids):  # Pick-two drafts pick two cards at once
            s.picks[(pack, pick * 10 + offset)] = grp
        if s.pool_override is not None:
            s.pool_override = s.pool_override + [i for i in ids]
        if (pack, pick) == (s.pack_number, s.pick_number):
            s.pack = []
        return True
