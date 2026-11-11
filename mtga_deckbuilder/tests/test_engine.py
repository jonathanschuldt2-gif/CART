from collections import Counter

from app.engine.builder import build_decks
from app.engine.card_score import base_power, meta_frequency, roles
from app.engine.deckparse import CatalogIndex, parse_deck_text
from app.engine.meta_match import match_deck
from app.engine.validate import validate_deck
from app.formats import FORMATS, get_format, is_legal


def own_everything(catalog, n=4):
    return {k: n for k, c in catalog.items() if not c.is_basic}


def test_legality(catalog):
    std, hist = get_format("standard"), get_format("historic")
    assert not is_legal(catalog["banned thing"].legalities, std)
    assert is_legal(catalog["banned thing"].legalities, hist)
    assert not is_legal(catalog["a-red removal"].legalities, std)
    assert is_legal(catalog["a-red removal"].legalities, get_format("alchemy"))
    assert is_legal(catalog["red removal"].legalities, get_format("explorer"))


def test_roles_and_power(catalog):
    assert "removal" in roles(catalog["red removal"])
    assert "counter" in roles(catalog["blue removal"])
    assert "draw" in roles(catalog["blue insight"])
    assert base_power(catalog["white walker"]) > base_power(catalog["white soldier 0"])


def test_validate(catalog):
    std = get_format("standard")
    deck = Counter({"red removal": 4, "red soldier 1": 4, "red soldier 2": 5, "mountain": 47})
    problems = validate_deck(deck, catalog, std)
    assert any("5 copies" in p for p in problems)
    assert not any("Mountain" in p for p in problems)
    deck["red soldier 2"] = 4
    deck["banned thing"] = 1
    assert any("not legal" in p for p in validate_deck(deck, catalog, std))
    brawl = get_format("brawl")
    assert any("commander" in p for p in validate_deck(Counter({"forest": 99}), catalog, brawl))
    bad = validate_deck(Counter({"forest": 98, "red removal": 1}), catalog, brawl, commander="elvish chieftain")
    assert any("color identity" in p for p in bad)


def _check_built(deck, catalog, fmt):
    main = Counter()
    for c, n in deck.cards:
        main[c.key] += n
    problems = validate_deck(main, catalog, fmt, commander=deck.commander.key if deck.commander else None)
    assert problems == [], problems
    assert deck.size == fmt.deck_size


def test_builder_standard(catalog):
    fmt = get_format("standard")
    decks = build_decks(catalog, own_everything(catalog), fmt, top_n=5)
    assert decks
    for d in decks:
        _check_built(d, catalog, fmt)
        lands = sum(n for _, n in d.lands)
        assert 20 <= lands <= 27
        assert set("".join(c.colors for c, _ in d.main)) <= set(d.colors)
        assert "banned thing" not in d.keys
        creatures = sum(n for c, n in d.main if c.is_creature)
        if d.archetype == "control":
            assert creatures <= 0.35 * sum(n for _, n in d.main)
    # Boros owner of both duals should get them in a Boros build
    boros = [d for d in decks if d.colors == "WR"]
    if boros:
        assert any(l.name == "Sacred Foundry" for l, _ in boros[0].lands)


def test_builder_respects_owned_counts(catalog):
    owned = {k: 1 for k, c in catalog.items() if not c.is_basic}
    for d in build_decks(catalog, owned, get_format("historic"), top_n=3):
        assert all(n <= 1 for c, n in d.main)


def test_builder_empty_collection(catalog):
    assert build_decks(catalog, {}, get_format("standard")) == []


def test_builder_brawl(catalog):
    for key in ("brawl", "standardbrawl"):
        fmt = FORMATS[key]
        owned = own_everything(catalog, 1)
        decks = build_decks(catalog, owned, fmt, top_n=2)
        assert decks, key
        for d in decks:
            assert d.commander is not None
            _check_built(d, catalog, fmt)


def test_meta_match_and_frequency(catalog):
    idx = CatalogIndex(catalog)
    text = "Deck\n4 Red Soldier 1\n4 Red Removal\n4 Red Walker\n20 Mountain\n\nSideboard\n2 Red Big Removal\n1 Nonexistent Card\n"
    parsed = parse_deck_text(text, idx)
    assert parsed.unknown == ["Nonexistent Card"]
    owned = {"red soldier 1": 4, "red removal": 2}
    m = match_deck(1, "Mono-Red", get_format("standard"), parsed, catalog, owned)
    # red soldier 1 is uncommon (i=1), removal uncommon, walker mythic, big removal rare
    assert m.wildcards == {"common": 0, "uncommon": 2, "rare": 2, "mythic": 4}
    assert m.wildcards_main == {"common": 0, "uncommon": 2, "rare": 0, "mythic": 4}
    assert abs(m.completion - 6 / 14) < 1e-9
    freq = meta_frequency([parsed.all_cards])
    assert freq["red removal"] == 1.0 and freq["red big removal"] == 0.5
