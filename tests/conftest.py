import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["CAMPUSFEST_LOCAL_DB"] = ":memory:"
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("GEMINI_API_KEY", None)

import pytest

from core import database as db


@pytest.fixture(autouse=True)
def fresh_workspace():
    """Every test starts from the seeded week-4 demo scenario in an in-memory database."""
    db.use_store(db.SQLiteStore(":memory:"))
    yield
