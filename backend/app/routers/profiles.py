"""Vereine, Kassenprofile und Veranstaltungen (Lastenheft 7).

Lesen ab Bediener (der Verkauf braucht Profil/Veranstaltung), Schreiben nur
Administrator.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin, require_bediener
from ..database import get_session
from ..models import AuditLog, Kassenprofil, Veranstaltung, Verein
from ..schemas import (
    KassenprofilIn,
    KassenprofilOut,
    VeranstaltungIn,
    VeranstaltungOut,
    VereinIn,
    VereinOut,
)

router = APIRouter(prefix="/api", tags=["profile"])

STATUS_ERLAUBT = {"geplant", "aktiv", "abgeschlossen", "archiviert"}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Ungültiges Datum: {value}") from exc


# -- Verein -------------------------------------------------------------
@router.get("/vereine", response_model=list[VereinOut], dependencies=[Depends(require_bediener)])
def vereine(session: Session = Depends(get_session)) -> list[VereinOut]:
    rows = session.query(Verein).order_by(Verein.name).all()
    return [VereinOut(id=v.id, name=v.name, anschrift=v.anschrift, kontakt=v.kontakt, aktiv=v.aktiv) for v in rows]


@router.post("/vereine", response_model=VereinOut, status_code=201, dependencies=[Depends(require_admin)])
def verein_anlegen(payload: VereinIn, session: Session = Depends(get_session)) -> VereinOut:
    v = Verein(name=payload.name, anschrift=payload.anschrift, kontakt=payload.kontakt)
    session.add(v)
    session.add(AuditLog(benutzer="administrator", aktion="verein.anlegen", datensatz=payload.name))
    session.commit()
    session.refresh(v)
    return VereinOut(id=v.id, name=v.name, anschrift=v.anschrift, kontakt=v.kontakt, aktiv=v.aktiv)


# -- Kassenprofil -------------------------------------------------------
@router.get("/kassenprofile", response_model=list[KassenprofilOut], dependencies=[Depends(require_bediener)])
def profile(session: Session = Depends(get_session)) -> list[KassenprofilOut]:
    rows = session.query(Kassenprofil).order_by(Kassenprofil.name).all()
    return [
        KassenprofilOut(id=p.id, name=p.name, verein_id=p.verein_id, bonkopf=p.bonkopf,
                        bonfuss=p.bonfuss, waehrung=p.waehrung, aktiv=p.aktiv)
        for p in rows
    ]


@router.post("/kassenprofile", response_model=KassenprofilOut, status_code=201, dependencies=[Depends(require_admin)])
def profil_anlegen(payload: KassenprofilIn, session: Session = Depends(get_session)) -> KassenprofilOut:
    if session.get(Verein, payload.verein_id) is None:
        raise HTTPException(status_code=422, detail="Unbekannter Verein")
    p = Kassenprofil(name=payload.name, verein_id=payload.verein_id, bonkopf=payload.bonkopf,
                     bonfuss=payload.bonfuss, waehrung=payload.waehrung)
    session.add(p)
    session.add(AuditLog(benutzer="administrator", aktion="kassenprofil.anlegen", datensatz=payload.name))
    session.commit()
    session.refresh(p)
    return KassenprofilOut(id=p.id, name=p.name, verein_id=p.verein_id, bonkopf=p.bonkopf,
                           bonfuss=p.bonfuss, waehrung=p.waehrung, aktiv=p.aktiv)


# -- Veranstaltung ------------------------------------------------------
@router.get("/veranstaltungen", response_model=list[VeranstaltungOut], dependencies=[Depends(require_bediener)])
def veranstaltungen(kassenprofil_id: int | None = None, session: Session = Depends(get_session)) -> list[VeranstaltungOut]:
    q = session.query(Veranstaltung)
    if kassenprofil_id is not None:
        q = q.filter(Veranstaltung.kassenprofil_id == kassenprofil_id)
    rows = q.order_by(Veranstaltung.erstellt_am.desc()).all()
    return [_v_out(v) for v in rows]


@router.post("/veranstaltungen", response_model=VeranstaltungOut, status_code=201, dependencies=[Depends(require_admin)])
def veranstaltung_anlegen(payload: VeranstaltungIn, session: Session = Depends(get_session)) -> VeranstaltungOut:
    if session.get(Kassenprofil, payload.kassenprofil_id) is None:
        raise HTTPException(status_code=422, detail="Unbekanntes Kassenprofil")
    if payload.status not in STATUS_ERLAUBT:
        raise HTTPException(status_code=422, detail="Ungültiger Status")
    v = Veranstaltung(
        kassenprofil_id=payload.kassenprofil_id, name=payload.name, beschreibung=payload.beschreibung,
        beginn=_parse_dt(payload.beginn), ende=_parse_dt(payload.ende), ort=payload.ort,
        pfand_aktiv=payload.pfand_aktiv, bonkopf=payload.bonkopf, status=payload.status,
    )
    session.add(v)
    session.add(AuditLog(benutzer="administrator", aktion="veranstaltung.anlegen", datensatz=payload.name))
    session.commit()
    session.refresh(v)
    return _v_out(v)


@router.put("/veranstaltungen/{vid}/status", response_model=VeranstaltungOut, dependencies=[Depends(require_admin)])
def veranstaltung_status(vid: int, status: str, session: Session = Depends(get_session)) -> VeranstaltungOut:
    v = session.get(Veranstaltung, vid)
    if v is None:
        raise HTTPException(status_code=404, detail="Veranstaltung nicht gefunden")
    if status not in STATUS_ERLAUBT:
        raise HTTPException(status_code=422, detail="Ungültiger Status")
    v.status = status
    session.add(AuditLog(benutzer="administrator", aktion="veranstaltung.status", datensatz=str(vid), nachher=status))
    session.commit()
    session.refresh(v)
    return _v_out(v)


def _v_out(v: Veranstaltung) -> VeranstaltungOut:
    return VeranstaltungOut(id=v.id, kassenprofil_id=v.kassenprofil_id, name=v.name,
                            beschreibung=v.beschreibung, ort=v.ort, pfand_aktiv=v.pfand_aktiv, status=v.status)
