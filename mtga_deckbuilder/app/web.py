from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.formats import FORMATS

BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.globals["FORMATS"] = FORMATS

MANA_CLASS = {"W": "w", "U": "u", "B": "b", "R": "r", "G": "g"}


def color_dots(colors: str) -> str:
    return "".join(f'<span class="dot {MANA_CLASS[c]}" title="{c}"></span>' for c in colors if c in MANA_CLASS) or \
        '<span class="dot c" title="Colorless"></span>'


templates.env.filters["dots"] = color_dots
templates.env.filters["pct"] = lambda v: f"{v * 100:.0f}%"
