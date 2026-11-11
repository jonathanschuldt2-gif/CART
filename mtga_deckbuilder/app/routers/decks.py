from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import exporters, services
from app.database import get_db
from app.engine.builder import DeckResult, build_decks
from app.formats import FORMATS, get_format
from app.models import BuiltDeck, CollectionEntry, MetaDeck
from app.web import templates

router = APIRouter()
_built: dict = {}


def _state_key(db: Session, fmt: str):
    coll = db.execute(select(func.count(), func.coalesce(func.sum(CollectionEntry.quantity), 0))).one()
    meta = db.execute(select(func.count(), func.coalesce(func.max(MetaDeck.id), 0))
                      .where(MetaDeck.format == fmt)).one()
    return (fmt, services.card_count(db), tuple(coll), tuple(meta))


def built_for(db: Session, fmt: str, top_n: int = 6) -> list[DeckResult]:
    key = _state_key(db, fmt)
    if _built.get(fmt, (None,))[0] != key:
        decks = build_decks(services.catalog(db), services.owned(db), get_format(fmt),
                            services.meta_freq(db, fmt), top_n=top_n)
        _built[fmt] = (key, decks)
    return _built[fmt][1]


@router.get("/decks")
def decks_index(request: Request, db: Session = Depends(get_db)):
    summary = []
    for fmt in FORMATS.values():
        built = built_for(db, fmt.key)
        matches = services.meta_matches(db, fmt.key)
        summary.append((fmt, built[0] if built else None, matches[0] if matches else None))
    return templates.TemplateResponse(request, "decks_index.html", {"summary": summary})


@router.get("/decks/{fmt}")
def decks(request: Request, fmt: str, db: Session = Depends(get_db)):
    f = get_format(fmt)
    return templates.TemplateResponse(request, "decks.html", {
        "f": f, "built": built_for(db, fmt), "matches": services.meta_matches(db, fmt),
        "has_collection": bool(services.owned(db)),
    })


def _get(db, fmt, idx) -> DeckResult | None:
    decks = built_for(db, fmt)
    return decks[idx] if 0 <= idx < len(decks) else None


@router.get("/decks/{fmt}/{idx}")
def deck_detail(request: Request, fmt: str, idx: int, db: Session = Depends(get_db)):
    d = _get(db, fmt, idx)
    if d is None:
        return RedirectResponse(f"/decks/{fmt}", status_code=303)
    groups = {}
    for c, n in sorted(d.main, key=lambda x: (x[0].cmc, x[0].name)):
        t = "Creatures" if c.is_creature else "Planeswalkers" if "Planeswalker" in c.front_type else \
            "Instants & Sorceries" if ("Instant" in c.front_type or "Sorcery" in c.front_type) else "Other spells"
        groups.setdefault(t, []).append((c, n))
    groups["Lands"] = d.lands
    curve = d.curve
    return templates.TemplateResponse(request, "deck_detail.html", {
        "d": d, "f": get_format(fmt), "idx": idx, "groups": groups, "curve": curve,
        "curve_max": max(curve.values()) or 1, "arena_text": exporters.deck_arena_text(d),
    })


@router.get("/decks/{fmt}/{idx}/export.{ext}")
def deck_export(fmt: str, idx: int, ext: str, db: Session = Depends(get_db)):
    d = _get(db, fmt, idx)
    if d is None:
        return Response("not found", status_code=404)
    body = exporters.deck_csv(d) if ext == "csv" else exporters.deck_arena_text(d)
    fname = "".join(ch for ch in d.name if ch.isalnum() or ch in " -_").strip().replace(" ", "_")
    return Response(body, media_type="text/csv" if ext == "csv" else "text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.{ext}"'})


@router.post("/decks/{fmt}/{idx}/save")
def deck_save(fmt: str, idx: int, db: Session = Depends(get_db)):
    d = _get(db, fmt, idx)
    if d:
        db.add(BuiltDeck(format=fmt, name=d.name, text=exporters.deck_arena_text(d), notes="\n".join(d.notes)))
        db.commit()
    return RedirectResponse("/saved", status_code=303)


@router.get("/saved")
def saved(request: Request, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(BuiltDeck).order_by(BuiltDeck.created_at.desc())))
    return templates.TemplateResponse(request, "saved.html", {"rows": rows})


@router.post("/saved/{deck_id}/delete")
def saved_delete(deck_id: int, db: Session = Depends(get_db)):
    d = db.get(BuiltDeck, deck_id)
    if d:
        db.delete(d)
        db.commit()
    return RedirectResponse("/saved", status_code=303)
