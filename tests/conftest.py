from pathlib import Path

import pytest
from sqlalchemy import Engine

from app.database import create_sqlite_engine


@pytest.fixture
def test_engine(tmp_path: Path) -> Engine:
    engine = create_sqlite_engine(tmp_path / "test_medibuy.db")
    yield engine
    engine.dispose()
