import pytest

from app.catalog.loader import Catalog
from app.config import DATA_DIR


@pytest.fixture(scope="session")
def cat():
    return Catalog(DATA_DIR)
