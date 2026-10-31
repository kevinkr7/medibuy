"""SQLite engine and session configuration."""

import os
from pathlib import Path

from sqlalchemy import Engine, URL, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(
    os.getenv("MEDIBUY_DATABASE_PATH", str(PROJECT_ROOT / "medibuy.db"))
).resolve()

class Base(DeclarativeBase):
    pass


def create_sqlite_engine(database_path: str | Path) -> Engine:
    """Create a SQLite engine with foreign-key enforcement enabled."""

    sqlite_engine = create_engine(
        URL.create("sqlite", database=str(database_path)),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(sqlite_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sqlite_engine


engine = create_sqlite_engine(DATABASE_PATH)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db():
    """Provide one SQLAlchemy session per API request."""

    with SessionLocal() as session:
        yield session
