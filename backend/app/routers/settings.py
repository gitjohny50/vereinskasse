"""Verwaltung der Systemeinstellungen über die Oberfläche (Lastenheft 13.3, 14.6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..hardware.factory import DEFAULT_HW_SETTINGS
from ..models import AuditLog, Benutzer, Systemeinstellung
from ..schemas import SettingOut, SettingUpdateIn

# Hardware-Einstellungen ändern erfordert Administratorrechte (Lastenheft 6.2).
router = APIRouter(prefix="/api/einstellungen", tags=["einstellungen"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[SettingOut])
def liste(session: Session = Depends(get_session)) -> list[SettingOut]:
    rows = session.query(Systemeinstellung).order_by(Systemeinstellung.schluessel).all()
    return [SettingOut(schluessel=r.schluessel, wert=r.wert, beschreibung=r.beschreibung) for r in rows]


@router.put("/{schluessel}", response_model=SettingOut)
def aendern(schluessel: str, payload: SettingUpdateIn, session: Session = Depends(get_session), benutzer: Benutzer = Depends(require_admin)) -> SettingOut:
    if schluessel not in DEFAULT_HW_SETTINGS:
        raise HTTPException(status_code=404, detail="Unbekannter Einstellungsschlüssel")
    row = session.get(Systemeinstellung, schluessel)
    vorher = row.wert if row else ""
    if row is None:
        row = Systemeinstellung(schluessel=schluessel, wert=payload.wert)
        session.add(row)
    else:
        row.wert = payload.wert
    # Änderung protokollieren (Lastenheft 16.3).
    session.add(
        AuditLog(
            benutzer=benutzer.name,
            aktion="einstellung.aendern",
            datensatz=schluessel,
            vorher=vorher,
            nachher=payload.wert,
        )
    )
    session.commit()
    return SettingOut(schluessel=row.schluessel, wert=row.wert, beschreibung=row.beschreibung)
