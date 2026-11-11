"""Paths and tunable weights for the draft helper."""
from __future__ import annotations

import os
from pathlib import Path


def default_log_path() -> Path:
    """Location of MTG Arena's Player.log on Windows (with a macOS fallback)."""
    profile = os.environ.get("USERPROFILE")
    if profile:
        return Path(profile) / "AppData" / "LocalLow" / "Wizards Of The Coast" / "MTGA" / "Player.log"
    return Path.home() / "Library" / "Logs" / "Wizards Of The Coast" / "MTGA" / "Player.log"


def default_arena_data_dirs() -> list[Path]:
    """Folders where Arena keeps its Raw_CardDatabase_*.mtga file."""
    candidates = [
        Path(r"C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw"),
        Path(r"C:\Program Files (x86)\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Raw"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\MTGA\MTGA_Data\Downloads\Raw"),
        Path(r"C:\Program Files\Epic Games\MagicTheGathering\MTGA_Data\Downloads\Raw"),
        Path.home() / "Library" / "Application Support" / "com.wizards.mtga" / "Downloads" / "Raw",
    ]
    return [p for p in candidates if p.is_dir()]


def cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    path = Path(base) / "mtg_draft_helper"
    path.mkdir(parents=True, exist_ok=True)
    return path


# How long downloaded 17Lands ratings are reused before re-fetching.
RATINGS_CACHE_HOURS = 24
USER_AGENT = "mtg-draft-helper/1.0 (personal draft overlay)"

# Ignore win rates computed from fewer games than this (too noisy).
MIN_GAMES = 200

# ---- Scoring weights (all in units of "standard deviations of GIH WR") ----
# Bonus for a card fully in your two main colors, at full commitment.
ON_COLOR_BONUS = 0.6
# Penalty for a card fully outside your colors, at full commitment.
OFF_COLOR_PENALTY = 1.4
# Colorless cards fit any deck.
COLORLESS_BONUS = 0.15
# Commitment ramps from 0 at this overall pick number...
COMMIT_START_PICK = 3
# ...up to 1.0 this many picks later (about pack 2, pick 4).
COMMIT_RAMP_PICKS = 15

# Deck-shape targets for a 40-card limited deck.
TARGET_CREATURES = 15
TARGET_TWO_DROPS = 5
CURVE_BONUS = 0.3

# Signal: a good card still here well after it is usually taken.
SIGNAL_BONUS = 0.25
SIGNAL_MIN_PICKS_LATE = 2.0

# Blend toward color-pair-specific ratings once committed.
PAIR_RATING_BLEND = 0.5

# Default base score by rarity when 17Lands has no data for a card.
RARITY_DEFAULT_Z = {"mythic": 0.4, "rare": 0.3, "uncommon": 0.0, "common": -0.3, "basic": -3.0}
