import threading
from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.cards.scryfall import refresh_card_db
from app.database import SessionLocal, get_db
from app.models import Card
from app.web import templates

router = APIRouter()
STATUS = {"running": False, "message": ""}


def _refresh_job(download: bool):
    STATUS.update(running=True, message="Downloading Scryfall card data… (this takes a few minutes)")
    db = SessionLocal()
    try:
        n = refresh_card_db(db, download=download)
        services.invalidate()
        STATUS["message"] = f"Card database updated: {n:,} Arena printings."
    except Exception as exc:  # surfaced on the page
        STATUS["message"] = f"Update failed: {exc}"
    finally:
        db.close()
        STATUS["running"] = False


@router.post("/cards/refresh")
def refresh(download: bool = True):
    if not STATUS["running"]:
        threading.Thread(target=_refresh_job, args=(download,), daemon=True).start()
    return RedirectResponse("/", status_code=303)


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    n_cards = services.card_count(db)
    entries = services.collection_entries(db)
    owned = services.owned(db)
    set_stats = []
    if n_cards and entries:
        names_by_set = defaultdict(set)
        for c in db.scalars(select(Card)):
            names_by_set[c.set_code].add(c.name_key)
        owned_by_set = defaultdict(set)
        for c, _ in entries:
            owned_by_set[c.set_code].add(c.name_key)
        for code, names in names_by_set.items():
            have = len(names & set(owned))
            if have:
                set_stats.append((code, have, len(names), have / len(names)))
        set_stats.sort(key=lambda s: -s[3])
    rarity = defaultdict(int)
    for c, q in entries:
        rarity[c.rarity] += q
    return templates.TemplateResponse(request, "home.html", {
        "n_cards": n_cards, "unique": len(owned), "total": sum(q for _, q in entries),
        "rarity": rarity, "set_stats": set_stats[:40], "status": STATUS,
    })
