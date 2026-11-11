from pathlib import Path

from draft_helper.cards import CardDB, mana_value_from_arena_text
from draft_helper.draft_state import DraftState
from draft_helper.ratings import Ratings
from draft_helper.scorer import score_pack, summarize_pool

FIXTURES = Path(__file__).parent / "fixtures"


def setup():
    ratings = Ratings.from_file(FIXTURES / "tst_ratings.json", "TST")
    db = CardDB()
    db.add_from_ratings(ratings.overall.rows)
    return db, ratings


def state_with(pool, pack, pack_no, pick_no):
    s = DraftState(event_name="PremierDraft_TST_1", pack_number=pack_no, pick_number=pick_no,
                   pack=list(pack), max_pack_size=14)
    for i, grp in enumerate(pool):
        s.picks[(1, i)] = grp
    return s


def names(ranked):
    return [r.card.name for r in ranked]


def test_p1p1_takes_raw_power():
    db, ratings = setup()
    # Choir of Banners (W, 61.0%) vs Tidecaller Adept (U, 56.0%)
    ranked, _ = score_pack(state_with([], [1005, 1004], 1, 1), db, ratings)
    assert names(ranked)[0] == "Choir of Banners"


def test_committed_pool_prefers_on_color():
    db, ratings = setup()
    ub_pool = [1005, 1006, 1007, 1009, 1010, 1012, 1021, 1023, 1024, 1011]
    # Pack 2 pick 5: Sunlit Rebuke (W, 57.5%) vs Gravebloom Rat (B, 55.5%)
    ranked, summary = score_pack(state_with(ub_pool, [1002, 1009], 2, 5), db, ratings)
    assert summary.main_colors == "UB"
    assert summary.commitment > 0.6
    assert names(ranked)[0] == "Gravebloom Rat"
    assert "on-color (UB)" in ranked[0].reason


def test_bomb_still_beats_weak_on_color_early():
    db, ratings = setup()
    # Two blue picks only, P1p3: a mythic-level off-color card should still win.
    ranked, _ = score_pack(state_with([1005, 1006], [1019, 1023], 1, 3), db, ratings)
    assert names(ranked)[0] == "Canopy Titan"


def test_gold_card_scored_against_both_colors():
    db, ratings = setup()
    ub_pool = [1005, 1006, 1007, 1009, 1010, 1012, 1023, 1024]
    s = state_with(ub_pool, [1021], 2, 3)
    ranked, _ = score_pack(s, db, ratings)
    assert "on-color (UB)" in ranked[0].reason
    w_pool = [1001, 1002, 1003, 1022, 1014, 1013, 1015, 1016]
    ranked2, _ = score_pack(state_with(w_pool, [1021], 2, 3), db, ratings)
    assert ranked2[0].score < ranked[0].score


def test_signal_bonus_for_late_good_card():
    db, ratings = setup()
    # Deathless Edict has ALSA 2.6; seeing it at pick 8 is a signal.
    ranked, _ = score_pack(state_with([], [1010], 1, 8), db, ratings)
    assert "open signal" in ranked[0].reason


def test_pool_summary_counts():
    db, ratings = setup()
    summary = summarize_pool(state_with([1005, 1007, 1009], [], 1, 4), db, ratings)
    assert summary.creatures == 2
    assert summary.size == 3


def test_mana_value_parsing():
    assert mana_value_from_arena_text("o2oWoW") == 4
    assert mana_value_from_arena_text("o(W/U)o(W/U)") == 2
    assert mana_value_from_arena_text("oXoR") == 1
    assert mana_value_from_arena_text("") is None
