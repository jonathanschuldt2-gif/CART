from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.engine.meta_match import match_deck
from app.formats import get_format
from app.meta.fetch import fetch_deck_text
from app.meta.store import add_meta_deck, load_meta_folder
from app.models import MetaDeck
from app.web import templates

router = APIRouter()


def _page(request, db, fmt, **extra):
    decks = services.meta_decks(db, fmt or None)
    return templates.TemplateResponse(request, "meta.html", {"decks": decks, "fmt": fmt, **extra})


@router.get("/meta")
def meta(request: Request, fmt: str = "", db: Session = Depends(get_db)):
    return _page(request, db, fmt)


@router.post("/meta/add")
async def add(request: Request, fmt: str = Form(...), name: str = Form(""), text: str = Form(""),
              url: str = Form(""), file: UploadFile | None = File(None), db: Session = Depends(get_db)):
    source = ""
    try:
        if file is not None and file.filename:
            text = (await file.read()).decode("utf-8", errors="replace")
            name = name or file.filename.rsplit(".", 1)[0]
            source = f"upload:{file.filename}"
        elif url.strip():
            text, source = fetch_deck_text(url.strip()), url.strip()
        if not text.strip():
            raise ValueError("Paste a decklist, upload a file, or give a URL.")
        add_meta_deck(db, fmt, name, text, source)
    except Exception as exc:
        return _page(request, db, fmt, error=str(exc))
    return RedirectResponse(f"/meta?fmt={fmt}", status_code=303)


@router.post("/meta/load-folder")
def load_folder(request: Request, db: Session = Depends(get_db)):
    n = load_meta_folder(db)
    return _page(request, db, "", message=f"Loaded {n} decklists from the meta folder.")


@router.post("/meta/{deck_id}/delete")
def remove(deck_id: int, db: Session = Depends(get_db)):
    d = db.get(MetaDeck, deck_id)
    fmt = d.format if d else ""
    if d:
        db.delete(d)
        db.commit()
    return RedirectResponse(f"/meta?fmt={fmt}", status_code=303)


@router.get("/meta/{deck_id}")
def view(request: Request, deck_id: int, db: Session = Depends(get_db)):
    d = db.get(MetaDeck, deck_id)
    if d is None:
        return RedirectResponse("/meta", status_code=303)
    cat, own = services.catalog(db), services.owned(db)
    parsed = next(p for m, p in services.meta_decks(db, d.format) if m.id == deck_id)
    match = match_deck(d.id, d.name, get_format(d.format), parsed, cat, own, services.meta_freq(db, d.format))
    rows = []
    for section, counter in (("Main", parsed.main), ("Sideboard", parsed.sideboard)):
        for key, n in sorted(counter.items(), key=lambda kv: (cat[kv[0]].cmc, kv[0])):
            rows.append((section, cat[key], n, min(own.get(key, 0), n)))
    if parsed.commander:
        rows.insert(0, ("Commander", cat[parsed.commander], 1, min(own.get(parsed.commander, 0), 1)))
    return templates.TemplateResponse(request, "meta_deck.html", {"d": d, "m": match, "rows": rows})
