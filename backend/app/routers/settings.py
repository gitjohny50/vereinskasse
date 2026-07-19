"""Verwaltung der Systemeinstellungen über die Oberfläche (Lastenheft 13.3, 14.6)."""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..hardware.factory import DEFAULT_HW_SETTINGS
from ..models import AuditLog, Benutzer, Systemeinstellung
from ..schemas import BonLogoIn, BonLogoOut, SettingOut, SettingUpdateIn

# Hardware-Einstellungen ändern erfordert Administratorrechte (Lastenheft 6.2).
router = APIRouter(prefix="/api/einstellungen", tags=["einstellungen"], dependencies=[Depends(require_admin)])


def _setting(session: Session, key: str, value: str = "") -> Systemeinstellung:
    row = session.get(Systemeinstellung, key)
    if row is None:
        row = Systemeinstellung(schluessel=key, wert=value)
        session.add(row)
    return row


def _logo_out(session: Session) -> BonLogoOut:
    aktiv = session.get(Systemeinstellung, "bon.logo.aktiv")
    breite = session.get(Systemeinstellung, "bon.logo.breite_px")
    hoehe = session.get(Systemeinstellung, "bon.logo.hoehe_px")
    raster = session.get(Systemeinstellung, "bon.logo.raster_b64")
    raster_wert = raster.wert if raster else ""
    return BonLogoOut(
        aktiv=(aktiv.wert if aktiv else "0") == "1",
        breite_px=int((breite.wert if breite else "0") or "0"),
        hoehe_px=int((hoehe.wert if hoehe else "0") or "0"),
        bytes=len(raster_wert),
    )


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


@router.get("/bon-logo/status", response_model=BonLogoOut)
def bon_logo(session: Session = Depends(get_session)) -> BonLogoOut:
    return _logo_out(session)


@router.put("/bon-logo/datei", response_model=BonLogoOut)
def bon_logo_speichern(payload: BonLogoIn, session: Session = Depends(get_session), benutzer: Benutzer = Depends(require_admin)) -> BonLogoOut:
    if payload.breite_px % 8 != 0:
        raise HTTPException(status_code=422, detail="Logo-Breite muss durch 8 teilbar sein.")
    try:
        raster = base64.b64decode(payload.raster_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="Logo-Raster ist kein gültiges Base64.") from None
    expected = (payload.breite_px // 8) * payload.hoehe_px
    if len(raster) != expected:
        raise HTTPException(status_code=422, detail=f"Logo-Raster passt nicht zur Größe ({len(raster)} statt {expected} Bytes).")

    vorher = _logo_out(session).model_dump_json()
    _setting(session, "bon.logo.aktiv").wert = "1"
    _setting(session, "bon.logo.breite_px").wert = str(payload.breite_px)
    _setting(session, "bon.logo.hoehe_px").wert = str(payload.hoehe_px)
    _setting(session, "bon.logo.raster_b64").wert = payload.raster_b64
    session.add(AuditLog(benutzer=benutzer.name, aktion="einstellung.bon_logo", datensatz="bon.logo", vorher=vorher, nachher="aktiv"))
    session.commit()
    return _logo_out(session)


@router.delete("/bon-logo/datei", response_model=BonLogoOut)
def bon_logo_loeschen(session: Session = Depends(get_session), benutzer: Benutzer = Depends(require_admin)) -> BonLogoOut:
    vorher = _logo_out(session).model_dump_json()
    _setting(session, "bon.logo.aktiv").wert = "0"
    _setting(session, "bon.logo.breite_px").wert = "0"
    _setting(session, "bon.logo.hoehe_px").wert = "0"
    _setting(session, "bon.logo.raster_b64").wert = ""
    session.add(AuditLog(benutzer=benutzer.name, aktion="einstellung.bon_logo_loeschen", datensatz="bon.logo", vorher=vorher, nachher="inaktiv"))
    session.commit()
    return _logo_out(session)
