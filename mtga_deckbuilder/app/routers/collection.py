from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app import exporters, services
from app.database import get_db
from app.formats import FORMATS, is_legal
from app.web import templates

router = APIRouter()
PAGE = 100


@router.get("/import")
def import_form(request: Request):
    return templates.TemplateResponse(request, "import.html", {})


@router.post("/import")
async def do_import(request: Request, text: str = Form(""), mode: str = Form("replace"),
                    file: UploadFile | None = File(None), db: Session = Depends(get_db)):
    if file is not None and file.filename:
        text = (await file.read()).decode("utf-8", errors="replace")
    if not services.card_count(db):
        return templates.TemplateResponse(request, "import.html", {
            "error": "The card database is empty. Click 'Update card database' on the home page first."})
    if not text.strip():
        return templates.TemplateResponse(request, "import.html", {"error": "Nothing to import."})
    try:
        report = services.import_collection(db, text, mode)
    except ValueError as exc:
        return templates.TemplateResponse(request, "import.html", {"error": str(exc)})
    return templates.TemplateResponse(request, "import_result.html", {"r": report})


@router.get("/collection")
def collection(request: Request, q: str = "", fmt: str = "", color: str = "", rarity: str = "",
               set_code: str = "", ctype: str = "", page: int = 1, db: Session = Depends(get_db)):
    entries = services.collection_entries(db)
    ql = q.lower().strip()
    f = FORMATS.get(fmt)
    out = []
    for c, n in entries:
        if ql and ql not in c.name.lower() and ql not in (c.oracle_text or "").lower():
            continue
        if f and not is_legal(c.legalities, f):
            continue
        if color == "C" and c.colors:
            continue
        if color == "M" and len(c.colors) < 2:
            continue
        if color and color not in "CM" and color not in c.colors:
            continue
        if rarity and c.rarity != rarity:
            continue
        if set_code and c.set_code != set_code.upper():
            continue
        if ctype and ctype.lower() not in c.type_line.lower():
            continue
        out.append((c, n))
    out.sort(key=lambda e: (e[0].name.lower(), e[0].set_code))
    pages = max(1, (len(out) + PAGE - 1) // PAGE)
    page = max(1, min(page, pages))
    return templates.TemplateResponse(request, "collection.html", {
        "rows": out[(page - 1) * PAGE: page * PAGE], "count": len(out), "copies": sum(n for _, n in out),
        "page": page, "pages": pages,
        "f": {"q": q, "fmt": fmt, "color": color, "rarity": rarity, "set_code": set_code, "ctype": ctype},
    })


@router.post("/collection/set")
def set_qty(card_id: str = Form(...), qty: int = Form(...), back: str = Form("/collection"),
            db: Session = Depends(get_db)):
    services.set_quantity(db, card_id, qty)
    return RedirectResponse(back if back.startswith("/") else "/collection", status_code=303)


@router.get("/collection/export.{ext}")
def export(ext: str, db: Session = Depends(get_db)):
    entries = services.collection_entries(db)
    if ext == "csv":
        body, mt = exporters.collection_csv(entries), "text/csv"
    elif ext == "json":
        body, mt = exporters.collection_json(entries), "application/json"
    elif ext == "txt":
        body, mt = exporters.collection_arena_text(entries), "text/plain"
    else:
        return Response("unknown export type", status_code=404)
    return Response(body, media_type=mt,
                    headers={"Content-Disposition": f'attachment; filename="mtga_collection.{ext}"'})
