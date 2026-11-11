from app.importers.arena_text import parse_arena_text
from app.importers.csv_generic import parse_csv
from app.importers.detect import detect_format, parse_any
from app.importers.resolve import Resolver
from app.importers.rows import ImportRow


def test_arena_text_sections():
    rows = parse_arena_text("""Commander
1 Elvish Chieftain (TST) 1

Deck
4 Red Soldier 1 (TST) 40
2x White Removal
Island

Sideboard
3 Blue Insight
""")
    assert [(r.name, r.quantity, r.section) for r in rows] == [
        ("Elvish Chieftain", 1, "commander"), ("Red Soldier 1", 4, "deck"), ("White Removal", 2, "deck"),
        ("Island", 1, "deck"), ("Blue Insight", 3, "sideboard")]
    assert rows[1].set_code == "TST" and rows[1].collector_number == "40"


def test_arena_text_blank_line_sideboard():
    rows = parse_arena_text("4 Red Removal\n20 Mountain\n\n2 Red Insight\n")
    assert rows[-1].section == "sideboard" and rows[0].section == "deck"


def test_csv_untapped_style():
    text = "Name,Count,Set,Collector Number,Rarity\nRed Removal,4,TST,10,uncommon\nIsland,0,TST,2,common\n"
    rows = parse_csv(text)
    assert len(rows) == 1 and rows[0].quantity == 4 and rows[0].set_code == "TST"


def test_csv_semicolon_and_arena_id():
    rows = parse_csv("Card;Qty;MTGA ID\nFire // Ice;2;12345\n")
    assert rows[0].name == "Fire // Ice" and rows[0].arena_id == 12345 and rows[0].quantity == 2


def test_detect():
    assert detect_format("name,quantity\nX,1") == "csv"
    assert detect_format("4 Lightning Strike (M19) 152") == "arena"
    assert detect_format('[{"name": "X", "quantity": 2}]') == "json"
    kind, rows = parse_any('﻿[{"name": "Island", "quantity": 3}]')
    assert kind == "json" and rows[0].quantity == 3


def test_resolve_edge_cases(cards):
    r = Resolver(cards)
    by = lambda **kw: r.resolve_one(ImportRow(**kw))
    assert by(name="fire /// ice").name == "Fire // Ice"            # Arena's triple slash
    assert by(name="Fire").name == "Fire // Ice"                     # front face
    assert by(name="Brutal Cathar").name.startswith("Brutal Cathar")  # DFC front face
    assert by(name="Lim-Dul's Vault").name == "Lim-Dûl's Vault"      # accents
    assert by(name="A-Red Removal").name == "A-Red Removal"          # alchemy kept distinct
    assert by(name="Red Removal").name == "Red Removal"
    assert by(name="Paper Only Card") is None                        # not on Arena
    island = next(c for c in cards if c.name == "Island")
    assert by(name="whatever", arena_id=island.arena_id).name == "Island"
    red = next(c for c in cards if c.name == "Red Removal")
    assert by(name="Red Removal", set_code=red.set_code, collector_number=red.collector_number).id == red.id
