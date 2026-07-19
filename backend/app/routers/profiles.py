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
from ..models import AuditLog, Kassenprofil, Systemeinstellung, Veranstaltung, Verein
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


def _profil_pfand_key(profil_id: int) -> str:
    return f"kassenprofil.{profil_id}.pfand_aktiv"


def _profil_pfand_aktiv(session: Session, profil_id: int) -> bool:
    row = session.get(Systemeinstellung, _profil_pfand_key(profil_id))
    return row is None or row.wert != "0"


def _set_profil_pfand(session: Session, profil_id: int, aktiv: bool) -> None:
    key = _profil_pfand_key(profil_id)
    row = session.get(Systemeinstellung, key)
    if row is None:
        row = Systemeinstellung(schluessel=key, wert="1" if aktiv else "0", beschreibung="Pfand im Kassenprofil aktiv")
        session.add(row)
    else:
        row.wert = "1" if aktiv else "0"


def _profil_out(session: Session, p: Kassenprofil) -> KassenprofilOut:
    return KassenprofilOut(
        id=p.id, name=p.name, verein_id=p.verein_id, bonkopf=p.bonkopf,
        bonfuss=p.bonfuss, waehrung=p.waehrung, aktiv=p.aktiv,
        pfand_aktiv=_profil_pfand_aktiv(session, p.id),
    )


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


@router.put("/vereine/{verein_id}", response_model=VereinOut, dependencies=[Depends(require_admin)])
def verein_aendern(verein_id: int, payload: VereinIn, session: Session = Depends(get_session)) -> VereinOut:
    v = session.get(Verein, verein_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Verein nicht gefunden")
    vorher = v.name
    v.name = payload.name
    v.anschrift = payload.anschrift
    v.kontakt = payload.kontakt
    session.add(AuditLog(benutzer="administrator", aktion="verein.aendern", datensatz=str(verein_id), vorher=vorher, nachher=v.name))
    session.commit()
    session.refresh(v)
    return VereinOut(id=v.id, name=v.name, anschrift=v.anschrift, kontakt=v.kontakt, aktiv=v.aktiv)


# -- Kassenprofil -------------------------------------------------------
@router.get("/kassenprofile", response_model=list[KassenprofilOut], dependencies=[Depends(require_bediener)])
def profile(mit_inaktiv: bool = False, session: Session = Depends(get_session)) -> list[KassenprofilOut]:
    q = session.query(Kassenprofil)
    if not mit_inaktiv:
        q = q.filter(Kassenprofil.aktiv.is_(True))
    rows = q.order_by(Kassenprofil.name).all()
    return [_profil_out(session, p) for p in rows]


@router.post("/kassenprofile", response_model=KassenprofilOut, status_code=201, dependencies=[Depends(require_admin)])
def profil_anlegen(payload: KassenprofilIn, session: Session = Depends(get_session)) -> KassenprofilOut:
    if session.get(Verein, payload.verein_id) is None:
        raise HTTPException(status_code=422, detail="Unbekannter Verein")
    p = Kassenprofil(name=payload.name, verein_id=payload.verein_id, bonkopf=payload.bonkopf,
                     bonfuss=payload.bonfuss, waehrung=payload.waehrung)
    session.add(p)
    session.flush()
    _set_profil_pfand(session, p.id, payload.pfand_aktiv)
    session.add(AuditLog(benutzer="administrator", aktion="kassenprofil.anlegen", datensatz=payload.name))
    session.commit()
    session.refresh(p)
    return _profil_out(session, p)


@router.put("/kassenprofile/{profil_id}", response_model=KassenprofilOut, dependencies=[Depends(require_admin)])
def profil_aendern(profil_id: int, payload: KassenprofilIn, session: Session = Depends(get_session)) -> KassenprofilOut:
    p = session.get(Kassenprofil, profil_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Kassenprofil nicht gefunden")
    if session.get(Verein, payload.verein_id) is None:
        raise HTTPException(status_code=422, detail="Unbekannter Verein")
    vorher = f"{p.name}, pfand={_profil_pfand_aktiv(session, p.id)}"
    p.name = payload.name
    p.verein_id = payload.verein_id
    p.bonkopf = payload.bonkopf
    p.bonfuss = payload.bonfuss
    p.waehrung = payload.waehrung
    _set_profil_pfand(session, p.id, payload.pfand_aktiv)
    session.add(AuditLog(
        benutzer="administrator", aktion="kassenprofil.aendern", datensatz=str(profil_id),
        vorher=vorher, nachher=f"{p.name}, pfand={payload.pfand_aktiv}",
    ))
    session.commit()
    session.refresh(p)
    return _profil_out(session, p)


@router.delete("/kassenprofile/{profil_id}", response_model=KassenprofilOut, dependencies=[Depends(require_admin)])
def profil_deaktivieren(profil_id: int, session: Session = Depends(get_session)) -> KassenprofilOut:
    p = session.get(Kassenprofil, profil_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Kassenprofil nicht gefunden")
    p.aktiv = False
    session.add(AuditLog(
        benutzer="administrator", aktion="kassenprofil.deaktivieren", datensatz=str(profil_id),
        vorher=p.name, nachher="inaktiv",
    ))
    session.commit()
    session.refresh(p)
    return _profil_out(session, p)


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
