"""Datenbankschicht.

Lastenheft 5.3 fordert für die Einzelkasse SQLite mit:
  * Speicherung auf der internen NVMe-SSD (Pfad aus config)
  * aktivierten Fremdschlüsseln
  * Datenbanktransaktionen
  * WAL-Modus
  * regelmäßiger Integritätsprüfung

Diese Datei richtet Engine und Session ein und erzwingt die PRAGMA-Einstellungen
bei jeder neuen Verbindung.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.db_url,
    # check_same_thread=False, weil FastAPI Requests aus einem Threadpool bedient.
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Erzwingt Fremdschlüssel und WAL bei jeder Verbindung."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session():
    """FastAPI-Dependency: liefert eine Session pro Request und schließt sie sauber."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Legt fehlende Tabellen an. In späteren Phasen übernimmt das Alembic."""
    from . import models  # noqa: F401  (Import registriert die Modelle)

    Base.metadata.create_all(bind=engine)


def integrity_check() -> str:
    """Führt PRAGMA integrity_check aus (Lastenheft 5.3, 23.3, 21.4)."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA integrity_check")).scalar_one()
    return str(result)
