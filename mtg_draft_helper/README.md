# MTG Arena Draft Helper

A small always-on-top window that sits next to MTG Arena while you draft. It
ranks the cards in your current pack, taking into account what you've already
picked.

- **Early in pack 1** it recommends the strongest card, using 17Lands
  games-in-hand win rate.
- **As your colors settle** it gives on-color cards more weight and penalises
  off-color ones. Once you're committed to a color pair, it uses that pair's own
  17Lands win rates.
- **In pack 3** it gives extra weight to creatures and 2-drops if your pool is
  short on them.
- **Signals:** it flags a strong card that is still in the pack well after its
  usual last-seen pick, because that color may be open.

Each card shows a short reason, for example `59.0% GIH, on-color (UB), late (ALSA 2.6) - open signal`.

The helper never touches the game process. It only reads the log file that
Arena writes for companion apps, which is the same approach the 17Lands client
uses.

## Setup (Windows)

1. **Install Python 3.11+** from <https://www.python.org/downloads/> and tick
   "Add python.exe to PATH". Tkinter, which draws the window, is included.
2. **Turn on detailed logs in Arena:** Options → Account → check
   **Detailed Logs (Plugin Support)**, then restart Arena. Without this, Arena
   doesn't log draft packs.
3. **Set Arena to Windowed or Borderless** (Options → Graphics). An
   always-on-top window can't show over exclusive fullscreen.
4. Download this folder and run the helper:
   ```bash
   cd mtg_draft_helper
   python run.py
   ```
5. Start a draft. The window updates on every pick.

## Options

| Command | What it does |
|---|---|
| `python run.py` | Watch Arena's log and show the overlay |
| `python run.py --console` | Print suggestions in the terminal instead |
| `python run.py --set DSK` | Force the set code if it isn't detected |
| `python run.py --format QuickDraft` | Force the 17Lands format (`PremierDraft`, `QuickDraft`, `TradDraft`) |
| `python run.py --log "D:\path\Player.log"` | Use a log in a non-standard location |
| `python run.py --arena-db-dir "D:\Games\MTGA\MTGA_Data\Downloads\Raw"` | Point at Arena's card database if Arena is installed somewhere unusual |
| `python run.py --offline` | Don't download anything; use cached ratings only |
| `python run.py --replay saved.log` | Replay a saved Player.log, so you can review a past draft |

The default log location is
`%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log`.

## Where the data comes from

- **Card names, colors, types and mana values:** Arena's own card database
  (`Raw_CardDatabase_*.mtga`), found automatically in the usual install folders
  (standard, Steam, Epic). If it isn't found, the helper uses 17Lands card data
  and Scryfall mana values instead.
- **Card strength:** [17Lands](https://www.17lands.com/card_ratings) public
  card ratings for the set and format you're drafting. These are downloaded once
  and cached for 24 hours in `%LOCALAPPDATA%\mtg_draft_helper`. A brand-new set
  may have no 17Lands data for the first day or two. Until then the helper falls
  back to rarity, and the window says so.

## Tuning

All scoring weights are in `draft_helper/config.py`, for example
`ON_COLOR_BONUS`, `OFF_COLOR_PENALTY`, how quickly you commit to colors
(`COMMIT_START_PICK`, `COMMIT_RAMP_PICKS`) and deck-shape targets
(`TARGET_CREATURES`, `TARGET_TWO_DROPS`). Scores are measured in standard
deviations of win rate within the set. A difference of 1.0 is a big gap, about
3 percentage points of GIH WR.

## How it works

```
Player.log ──► log_watcher ──► log_parser ──► DraftState (pack, picks)
                                                  │
           Arena card DB / 17Lands / Scryfall ──► scorer ──► overlay (Tkinter)
```

- `log_parser.py` doesn't depend on Arena's message names, which change between
  updates. It decodes every JSON payload, including JSON nested inside strings,
  and looks for draft fields: `PackCards`/`DraftPack`, `SelfPack`/`SelfPick`,
  `PackNumber`/`PickNumber`, `PickedCards`, and `GrpId(s)`/`CardId` picks. It
  supports Premier, Traditional and Quick (bot) drafts.
- At startup the helper reads the whole log, so starting it mid-draft still
  rebuilds your pool.

## Troubleshooting

- **The window says "Waiting for a draft…" during a draft:** check that
  Detailed Logs is on, then restart Arena.
- **Cards show as "Unknown card #12345":** the card database wasn't found and
  17Lands has no data for that card. Pass `--arena-db-dir`.
- **The window isn't visible over the game:** switch Arena to Windowed or
  Borderless.

## Tests

```bash
pip install pytest
python -m pytest tests
```

The tests use a small fictional set and synthetic logs in `tests/fixtures/`, so
they run offline. To see the overlay without Arena, run:
```bash
python run.py --replay tests/fixtures/sample_draft.log --ratings-file tests/fixtures/tst_ratings.json --offline --replay-delay 0.5
```
