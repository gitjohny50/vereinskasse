"""Zeit-Helfer für Speicherung in UTC und Anzeige in lokaler Kassenzeit."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def local_tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("VK_TIMEZONE") or os.environ.get("TZ") or "Europe/Berlin")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return now_utc().astimezone(local_tz())


def as_utc(dt: datetime) -> datetime:
    """SQLite liefert UTC-Zeitstempel ohne tzinfo zurück; wieder als UTC markieren."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def to_local(dt: datetime) -> datetime:
    return as_utc(dt).astimezone(local_tz())
