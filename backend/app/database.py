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
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.db_url,
    # check_same_thread=False, weil FastAPI Requests aus einem Threadpool bedient.
    # timeout=15.0 hilft gegen "database is locked" bei hoher Parallelität.
    connect_args={"check_same_thread": False, "timeout": 15.0},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Erzwingt Fremdschlüssel und WAL bei jeder Verbindung."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Busy Timeout auf 15000 ms (15s) erhöht, damit Operationen auf gelockte DB warten
    cursor.execute("PRAGMA busy_timeout=15000")
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
    """Legt fehlende Tabellen an und ergänzt fehlende Spalten.

    Die App verwaltet ihr SQLite-Schema damit selbst: ``create_all`` erzeugt neue
    Tabellen, ``_ensure_columns`` fügt bei bestehenden Tabellen neu hinzugekommene
    Spalten nach. So genügt nach einem Update ein Neustart - ohne separate
    Migrationsschritte.
    """
    from . import models  # noqa: F401  (Import registriert die Modelle)
    from sqlalchemy import inspect

    Base.metadata.create_all(bind=engine)
    _ensure_columns(inspect(engine))


def _sql_default(col) -> str | None:
    """Ermittelt einen DEFAULT-Wert für eine nachzurüstende NOT-NULL-Spalte."""
    from sqlalchemy import Boolean, DateTime, Integer, Numeric

    default = getattr(col, "default", None)
    if default is not None and getattr(default, "is_scalar", False):
        val = default.arg
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, str):
            return "'" + val.replace("'", "''") + "'"
    if isinstance(col.type, Boolean):
        return "0"
    if isinstance(col.type, (Integer, Numeric)):
        return "0"
    if isinstance(col.type, DateTime):
        return "CURRENT_TIMESTAMP"
    return "''"


def _ensure_columns(inspector) -> None:
    """Fügt Spalten, die im Modell existieren, in der DB aber (noch) fehlen,
    per ALTER TABLE hinzu. Nur additiv - es wird nie etwas geändert/gelöscht."""
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            vorhanden = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in vorhanden:
                    continue
                typ = col.type.compile(dialect=engine.dialect)
                zusatz = ""
                if not col.nullable:
                    zusatz = f" NOT NULL DEFAULT {_sql_default(col)}"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {typ}{zusatz}'))


def integrity_check() -> str:
    """Führt PRAGMA integrity_check aus (Lastenheft 5.3, 23.3, 21.4)."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA integrity_check")).scalar_one()
    return str(result)