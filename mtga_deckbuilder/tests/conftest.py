import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MTGA_DATA_DIR", tempfile.mkdtemp(prefix="mtga_test_"))

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.cards.scryfall import load_cards  # noqa: E402
from app.database import init_db, make_engine  # noqa: E402
from app.engine.cardinfo import build_catalog  # noqa: E402
from app.models import Card  # noqa: E402
from tests.fixture_cards import make_cards  # noqa: E402


@pytest.fixture
def db():
    eng = make_engine("sqlite://")
    init_db(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    load_cards(s, make_cards())
    yield s
    s.close()


@pytest.fixture
def cards(db):
    return list(db.scalars(select(Card)))


@pytest.fixture
def catalog(cards):
    return build_catalog(cards)
