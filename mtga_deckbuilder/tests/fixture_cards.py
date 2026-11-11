"""Synthetic Scryfall-shaped card records for offline tests and demos."""
import re
import uuid

ALL_LEGAL = {k: "legal" for k in ("standard", "alchemy", "explorer", "pioneer", "historic", "timeless",
                                    "brawl", "standardbrawl")}
_n = [0]


def sf(name, cost="", type_line="", text="", p=None, t=None, rarity="common", set_code="tst",
       keywords=(), legal=None, layout="normal", produced=None, games=("arena", "paper"), faces=None):
    _n[0] += 1
    pips = re.findall(r"\{([^}]+)\}", cost)
    cmc = 0
    colors = set()
    for s in pips:
        if s.isdigit():
            cmc += int(s)
        elif s != "X":
            cmc += 1
            colors |= {c for c in s.split("/") if c in "WUBRG"}
    order = [c for c in "WUBRG" if c in colors]
    rec = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + set_code)), "oracle_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, name)),
        "arena_id": 70000 + _n[0], "name": name, "set": set_code, "collector_number": str(_n[0]),
        "rarity": rarity, "cmc": float(cmc), "mana_cost": cost, "colors": order, "color_identity": order,
        "type_line": type_line, "oracle_text": text, "keywords": list(keywords),
        "legalities": legal or dict(ALL_LEGAL), "games": list(games), "layout": layout,
    }
    if p is not None:
        rec["power"], rec["toughness"] = str(p), str(t)
    if produced:
        rec["produced_mana"] = produced
        rec["color_identity"] = sorted(set(produced) - {"C"}, key="WUBRG".index)
    if faces:
        rec["card_faces"] = faces
        del rec["oracle_text"]
    return rec


def creature(name, cost, p, t, color_word="", kw=(), text="", rarity="common", sub="Human Warrior", legendary=False):
    tl = ("Legendary " if legendary else "") + f"Creature — {sub}"
    kt = ", ".join(k.title() for k in kw)
    return sf(name, cost, tl, (kt + "\n" + text).strip(), p, t, rarity, keywords=[k.title() for k in kw])


def make_cards():
    cards = []
    for land, col in (("Plains", "W"), ("Island", "U"), ("Swamp", "B"), ("Mountain", "R"), ("Forest", "G")):
        cards.append(sf(land, "", f"Basic Land — {land}", f"({{T}}: Add {{{col}}}.)", produced=[col]))
    sym = {"W": "W", "U": "U", "B": "B", "R": "R", "G": "G"}
    for c, word in (("W", "White"), ("U", "Blue"), ("B", "Black"), ("R", "Red"), ("G", "Green")):
        s = sym[c]
        kw = {"W": ("flying",), "U": ("flying",), "B": ("deathtouch",), "R": ("haste",), "G": ("trample",)}[c]
        for i, (cost, p, t) in enumerate([(f"{{{s}}}", 1, 1), (f"{{{s}}}", 2, 1), (f"{{1}}{{{s}}}", 2, 2),
                                           (f"{{1}}{{{s}}}", 2, 3), (f"{{{s}}}{{{s}}}", 3, 2),
                                           (f"{{2}}{{{s}}}", 3, 3), (f"{{2}}{{{s}}}", 2, 4),
                                           (f"{{3}}{{{s}}}", 4, 4), (f"{{3}}{{{s}}}", 3, 5),
                                           (f"{{4}}{{{s}}}", 5, 5), (f"{{4}}{{{s}}}{{{s}}}", 6, 6)]):
            k = kw if i % 2 else ()
            text = "When this creature enters, put a +1/+1 counter on target creature you control." if i % 3 == 0 else ""
            cards.append(creature(f"{word} Soldier {i}", cost, p, t, kw=k, text=text,
                                  rarity=["common", "uncommon", "rare", "mythic"][i % 4],
                                  sub=f"{'Elf' if c == 'G' else 'Human'} Soldier"))
        cards.append(sf(f"{word} Removal", f"{{1}}{{{s}}}", "Instant",
                        "Destroy target creature an opponent controls." if c in "WB" else
                        "Lightning deals 3 damage to any target." if c == "R" else
                        "Counter target spell." if c == "U" else "Target creature you control fights target creature you don't control.",
                        rarity="uncommon"))
        cards.append(sf(f"{word} Big Removal", f"{{3}}{{{s}}}", "Sorcery", "Exile target creature or planeswalker.", rarity="rare"))
        cards.append(sf(f"{word} Insight", f"{{2}}{{{s}}}", "Sorcery", "Draw two cards.", rarity="common"))
        cards.append(sf(f"{word} Charm", f"{{{s}}}", "Instant", "Target creature gets +2/+2 until end of turn. Scry 1.", rarity="common"))
        cards.append(sf(f"{word} Walker", f"{{2}}{{{s}}}{{{s}}}", f"Legendary Planeswalker — {word}",
                        "+1: Create a 1/1 Soldier creature token.\n−3: Destroy target creature.", rarity="mythic"))
    cards.append(creature("Elvish Chieftain", "{1}{G}", 2, 2, text="Other Elves you control get +1/+1.",
                          rarity="rare", sub="Elf Warrior", legendary=True))
    cards.append(creature("Boros Captain", "{1}{R}{W}", 3, 3, kw=("first strike",), text="Whenever another creature you control attacks, it gets +1/+0.",
                          rarity="rare", sub="Human Soldier", legendary=True))
    cards.append(sf("Sacred Foundry", "", "Land — Mountain Plains", "({T}: Add {R} or {W}.) As this land enters, you may pay 2 life.",
                    rarity="rare", produced=["R", "W"]))
    cards.append(sf("Inspiring Vantage", "", "Land", "This land enters tapped unless you control two or fewer other lands.",
                    rarity="rare", produced=["R", "W"]))
    cards.append(sf("Watery Grave", "", "Land — Island Swamp", "As this land enters, you may pay 2 life.", rarity="rare", produced=["U", "B"]))
    cards.append(sf("Fire // Ice", "{1}{R}", "Instant // Instant", None, rarity="uncommon", layout="split",
                    faces=[{"name": "Fire", "mana_cost": "{1}{R}", "type_line": "Instant", "oracle_text": "Fire deals 2 damage divided as you choose among one or two targets."},
                           {"name": "Ice", "mana_cost": "{1}{U}", "type_line": "Instant", "oracle_text": "Tap target permanent. Draw a card."}]))
    cards.append(sf("Brutal Cathar // Moonrage Brute", "{2}{W}", "Creature — Human Soldier // Creature — Werewolf", None,
                    rarity="rare", layout="transform",
                    faces=[{"name": "Brutal Cathar", "mana_cost": "{2}{W}", "type_line": "Creature — Human Soldier",
                            "oracle_text": "When this creature enters, exile target creature an opponent controls until this creature leaves the battlefield.",
                            "power": "3", "toughness": "3"},
                           {"name": "Moonrage Brute", "mana_cost": "", "type_line": "Creature — Werewolf", "oracle_text": "First strike"}]))
    cards.append(sf("Lim-Dûl's Vault", "{U}{B}", "Instant", "Look at the top five cards of your library.", rarity="uncommon",
                    legal={**ALL_LEGAL, "standard": "not_legal", "explorer": "not_legal", "pioneer": "not_legal"}))
    cards.append(sf("A-Red Removal", "{R}", "Instant", "A-Red Removal deals 3 damage to any target.", rarity="uncommon",
                    games=("arena",), legal={"alchemy": "legal", "historic": "legal", "brawl": "legal", "timeless": "legal"}))
    cards.append(sf("Paper Only Card", "{R}", "Instant", "Deals 1 damage.", games=("paper",)))
    cards.append(sf("Banned Thing", "{G}", "Creature — Beast", "", 5, 5, rarity="rare",
                    legal={**ALL_LEGAL, "standard": "banned"}))
    cards += singleton_filler()
    return cards


def singleton_filler():
    """Enough distinct green / white / red cards to fill singleton Brawl decks."""
    out = []
    for word, s, sub in (("Green", "G", "Elf Druid"), ("White", "W", "Human Cleric"), ("Red", "R", "Goblin Shaman")):
        for i in range(36):
            cmc = 1 + i % 5
            cost = (f"{{{cmc - 1}}}" if cmc > 1 else "") + f"{{{s}}}"
            if i % 4 == 3:
                out.append(sf(f"{word} Trick {i}", cost, "Instant",
                              "Draw a card." if i % 8 == 3 else "Target creature gets -2/-2 until end of turn."))
            else:
                out.append(creature(f"{word} Filler {i}", cost, cmc, cmc, sub=sub,
                                    text="Other Elves you control get +1/+1." if s == "G" and i % 6 == 0 else ""))
    return out
