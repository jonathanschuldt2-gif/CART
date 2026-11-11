# MTGA Deckbuilder: catalog your Arena collection and build the best decks

A local web app (plus a small CLI) that:

1. **Catalogs** your MTG Arena collection: import it from a tracker export, browse and filter it, see set completion, and export it as CSV, JSON or Arena text.
2. **Ranks meta decks** for each Arena format by how much of each you already own and how many wildcards (common/uncommon/rare/mythic) you'd need to finish it. It also suggests substitutes from your collection.
3. **Builds the best decks it can from cards you own** (0 wildcards) for Standard, Alchemy, Explorer, Historic, Timeless, Brawl and Standard Brawl. Each deck has an explanation, a mana curve, and a one-click "Copy for Arena import".

## Quick start

```bash
cd mtga_deckbuilder
pip install -r requirements.txt
python run.py            # http://127.0.0.1:8000
```

Then, in the app:

1. **Home → Update card database.** This downloads Scryfall's bulk card data (about 500 MB, takes a few minutes) and keeps only the cards on Arena. Re-run it whenever a new set releases.
2. **Import:** upload or paste your collection export.
3. **Meta decks:** paste current top decklists for the formats you play (Arena export text). You can also save them as `data/meta/<format>/<Archetype>.txt` and click **Load meta folder**.
4. **Build decks:** see the best decks per format.

### Getting your collection out of Arena

Arena has no collection export and hasn't written the collection to its log file since 2021. Export it from a tracker instead:

- **Untapped.gg** companion → Collection → Export
- **Aetherhub** / **MTGA Assistant** tracker → Collection → Export
- **Moxfield** / **Deckstats** collection → Export CSV

The importer auto-detects the format. CSV/TSV/semicolon files work as long as they have a name column (`Name`, `Card`…), and ideally quantity (`Count`, `Quantity`, `Qty`…), `Set` + `Collector Number`, or an Arena ID column. Arena deck text (`4 Lightning Strike (M19) 152`) and the app's own JSON export work too. Rows that don't match a card on Arena are listed so you can fix them.

## CLI

```bash
python cli.py update-cards                       # or: --file default-cards.json (a Scryfall bulk file you downloaded)
python cli.py import my_collection.csv           # --add to add instead of replace
python cli.py load-meta                          # import data/meta/<format>/*.txt
python cli.py build standard --top 3             # best decks, printed as Arena import text
python cli.py export collection.csv              # .csv / .json / .txt
```

## How decks are built

- **Card power** = text heuristics (removal, counterspells, card draw, evasion, enter-the-battlefield value, stats for the mana value, planeswalkers, drawbacks) + **how often the card appears in the meta decks you imported for that format** + a small rarity tiebreak. Adding current meta decklists makes the builder noticeably smarter.
- For every color combination (mono, two- and three-color) and each plan (aggro / midrange / control), a greedy builder fills the deck slot by slot. It balances card power, synergy with what's already in the deck (+1/+1 counters, tokens, sacrifice, lifegain, spells, graveyard, artifacts, landfall, tribal types…), mana-curve targets, a creature count, and enough interaction. A second pass leans into the synergies the first pass found.
- **Mana base:** the land count comes from the average mana value. Owned dual lands for the deck's colors are added first, then basics split by colored-pip share.
- **Brawl / Standard Brawl:** owned legendary creatures and planeswalkers are tried as commanders. The deck is a singleton within the commander's color identity, steered towards the commander's themes.
- Every deck is checked for legality, size, copy limits and color identity. Near-duplicate decks are dropped, and the rest are ranked by power, synergy, curve fit and mana-base strain.
- **Meta matching:** a card's wildcard rarity is the lowest rarity it was printed at on Arena (the cheapest craft). Basic lands are free.

"Best" for your own builds is a heuristic, not a simulation. Treat the results as strong starting points to tweak in Arena.

## Files

```
app/cards/        Scryfall download + loader, name normalization
app/importers/    CSV / Arena text / JSON parsers, matching rows to cards
app/engine/       card scoring, deck builder, mana base, meta matching, validation
app/meta/         meta decklist storage, optional plain-text URL fetch
app/routers/      web pages; templates/ + static/ for the UI
cli.py            command-line interface
tests/            pytest suite with an offline synthetic card set
data/             (gitignored) mtga.db, Scryfall cache, meta/ folder
```

Settings (optional `.env`, see `.env.example`): `MTGA_DATA_DIR`, `HOST`, `PORT`, `DATABASE_URL`.

## Tests

```bash
cd mtga_deckbuilder && python -m pytest -q
```
