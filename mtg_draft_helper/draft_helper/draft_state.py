"""The current draft as seen in the log."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DraftState:
    event_name: str = ""
    draft_id: str = ""
    pack_number: int = 0          # 1-based; 0 = no pack seen yet
    pick_number: int = 0          # 1-based
    pack: list[int] = field(default_factory=list)      # grpIds in the pack you're looking at
    picks: dict[tuple[int, int], int] = field(default_factory=dict)  # (pack, pick) -> grpId
    pool_override: list[int] | None = None             # full pool, when the log provides it
    max_pack_size: int = 0

    @property
    def set_code(self) -> str:
        """'PremierDraft_DSK_20240924' -> 'DSK'."""
        parts = self.event_name.split("_")
        return parts[1].upper() if len(parts) >= 2 else ""

    @property
    def format_name(self) -> str:
        """17Lands format name for this event."""
        name = self.event_name.split("_")[0] if self.event_name else ""
        if name.startswith("QuickDraft") or name.startswith("BotDraft"):
            return "QuickDraft"
        if name.startswith("TradDraft") or name.startswith("TraditionalDraft"):
            return "TradDraft"
        if name.startswith("PickTwo"):
            return "PickTwoDraft"
        return "PremierDraft"

    @property
    def pool(self) -> list[int]:
        if self.pool_override is not None:
            return list(self.pool_override)
        return [self.picks[k] for k in sorted(self.picks)]

    @property
    def overall_pick(self) -> int:
        """1-based pick index across the whole draft."""
        per_pack = max(self.max_pack_size, 13)
        return (max(self.pack_number, 1) - 1) * per_pack + max(self.pick_number, 1)

    def reset(self, event_name: str = "", draft_id: str = "") -> None:
        self.__init__(event_name=event_name, draft_id=draft_id)
