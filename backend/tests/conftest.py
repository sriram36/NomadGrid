import copy
import warnings

import pytest

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient   # noqa: E402

from app.api.app import create_app           # noqa: E402
from app.catalog.loader import Catalog       # noqa: E402
from app.config import DATA_DIR              # noqa: E402

MENON = {"departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}


@pytest.fixture(scope="session")
def cat():
    return Catalog(DATA_DIR)


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test.sqlite"


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(db_path=db_path))


@pytest.fixture(scope="session")
def menon():
    return copy.deepcopy(MENON)


@pytest.fixture(scope="session")
def golden(cat):
    """The Menon package built once for the whole session (read-only: deep-copy before mutating)."""
    import tempfile
    from pathlib import Path
    c = TestClient(create_app(db_path=Path(tempfile.mkdtemp()) / "g.sqlite"))
    j = c.post("/api/packages", json=MENON).json()
    assert j["outcome"] == "PACKAGE", j
    return j["package"]
