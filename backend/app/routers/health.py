"""System- und Gesundheitsstatus."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..database import integrity_check
from ..schemas import HealthOut

router = APIRouter(tags=["system"])


@router.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    """Liefert Version und Ergebnis der SQLite-Integritätsprüfung (Lastenheft 5.3, 23.3)."""
    return HealthOut(
        status="ok",
        version=settings.app_version,
        db_integrity=integrity_check(),
    )
