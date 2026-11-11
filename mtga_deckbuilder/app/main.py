from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import collection, decks, home, meta
from app.web import BASE

app = FastAPI(title="MTGA Deckbuilder")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
for r in (home, collection, meta, decks):
    app.include_router(r.router)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/healthz")
def healthz():
    return {"ok": True}
