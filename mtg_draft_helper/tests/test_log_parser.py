from pathlib import Path

from draft_helper.log_parser import LogParser

FIXTURES = Path(__file__).parent / "fixtures"


def feed(name: str) -> LogParser:
    parser = LogParser()
    with open(FIXTURES / name, encoding="utf-8") as f:
        parser.feed_lines(f)
    return parser


def test_premier_draft_full_replay():
    s = feed("sample_draft.log").state
    assert s.event_name == "PremierDraft_TST_20261101"
    assert s.set_code == "TST"
    assert s.format_name == "PremierDraft"
    assert len(s.pool) == 24          # 3 packs x 8 picks
    assert s.pack == []                # last pick made, no pack open
    assert s.max_pack_size == 8


def test_premier_draft_mid_pick_shows_pack():
    parser = LogParser()
    lines = (FIXTURES / "sample_draft.log").read_text(encoding="utf-8").splitlines(keepends=True)
    # Stop right after the P1p3 Draft.Notify (2 header lines + 3 lines per pick).
    parser.feed_lines(lines[: 2 + 3 * 2 + 1])
    s = parser.state
    assert (s.pack_number, s.pick_number) == (1, 3)
    assert len(s.pack) == 6
    assert len(s.pool) == 2
    assert s.pool[0] == 1004


def test_game_state_grpids_are_not_picks():
    parser = LogParser()
    parser.feed_line('[UnityCrossThreadLogger]{"gameStateMessage":{"gameObjects":[{"grpId":1001,"GrpId":1001}]}}\n')
    assert parser.state.pool == []


def test_lobby_event_lists_dont_reset_draft():
    parser = feed("sample_draft.log")
    parser.feed_line('[UnityCrossThreadLogger]<== EventGetCoursesV2 {"Courses":[{"InternalEventName":"PremierDraft_OLD_20250101"}]}\n')
    assert parser.state.event_name == "PremierDraft_TST_20261101"
    assert len(parser.state.pool) == 24


def test_quick_draft_with_multiline_json():
    s = feed("quick_draft.log").state
    assert s.event_name == "QuickDraft_TST_20261105"
    assert s.format_name == "QuickDraft"
    assert (s.pack_number, s.pick_number) == (1, 2)   # 0-based in the log
    assert s.pack == [1001, 1009, 1013, 1021]
    assert s.pool == [1010]


def test_new_draft_resets_pool():
    parser = feed("sample_draft.log")
    parser.feed_line('[UnityCrossThreadLogger]Draft.Notify {"draftId":"d-99","SelfPick":1,"SelfPack":1,"PackCards":"1001,1002"}\n')
    assert parser.state.pool == []
    assert parser.state.pack == [1001, 1002]
