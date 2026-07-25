"""Benutzer- und Rollenverwaltung (nur Administrator)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..models import AuditLog, Benutzer, Kassenabschluss, Rolle, Sitzung, Verkauf
from ..schemas import BenutzerCreateIn, BenutzerOut, BenutzerUpdateIn, RolleOut
from ..security import hash_pin

router = APIRouter(prefix="/api", tags=["benutzer"], dependencies=[Depends(require_admin)])


def _out(b: Benutzer) -> BenutzerOut:
    return BenutzerOut(id=b.id, name=b.name, rolle_id=b.rolle_id, rolle=b.rolle.name, stufe=b.rolle.stufe, aktiv=b.aktiv)


@router.get("/rollen", response_model=list[RolleOut])
def rollen(session: Session = Depends(get_session)) -> list[RolleOut]:
    rows = session.query(Rolle).order_by(Rolle.stufe).all()
    return [RolleOut(id=r.id, name=r.name, stufe=r.stufe, beschreibung=r.beschreibung) for r in rows]


@router.get("/benutzer", response_model=list[BenutzerOut])
def liste(session: Session = Depends(get_session)) -> list[BenutzerOut]:
    return [_out(b) for b in session.query(Benutzer).order_by(Benutzer.name).all()]


@router.post("/benutzer", response_model=BenutzerOut, status_code=201)
def anlegen(payload: BenutzerCreateIn, session: Session = Depends(get_session)) -> BenutzerOut:
    if session.get(Rolle, payload.rolle_id) is None:
        raise HTTPException(status_code=422, detail="Unbekannte Rolle")
    b = Benutzer(name=payload.name, pin_hash=hash_pin(payload.pin), rolle_id=payload.rolle_id)
    session.add(b)
    session.add(AuditLog(benutzer="administrator", aktion="benutzer.anlegen", datensatz=payload.name))
    session.commit()
    session.refresh(b)
    return _out(b)


@router.put("/benutzer/{benutzer_id}", response_model=BenutzerOut)
def aendern(benutzer_id: int, payload: BenutzerUpdateIn, session: Session = Depends(get_session)) -> BenutzerOut:
    b = session.get(Benutzer, benutzer_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if payload.name is not None:
        b.name = payload.name
    if payload.rolle_id is not None:
        if session.get(Rolle, payload.rolle_id) is None:
            raise HTTPException(status_code=422, detail="Unbekannte Rolle")
        b.rolle_id = payload.rolle_id
    if payload.aktiv is not None:
        b.aktiv = payload.aktiv
    if payload.pin is not None:
        b.pin_hash = hash_pin(payload.pin)
        b.fehlversuche = 0  # Sperre nach PIN-Reset aufheben
    session.add(AuditLog(benutzer="administrator", aktion="benutzer.aendern", datensatz=str(benutzer_id)))
    session.commit()
    session.refresh(b)
    return _out(b)


@router.delete("/benutzer/{benutzer_id}", status_code=204)
def loeschen(
    benutzer_id: int,
    session: Session = Depends(get_session),
    aktueller_benutzer: Benutzer = Depends(require_admin),
) -> Response:
    b = session.get(Benutzer, benutzer_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if b.id == aktueller_benutzer.id:
        raise HTTPException(status_code=409, detail="Der aktuell angemeldete Benutzer kann nicht gelöscht werden.")

    hat_verkaeufe = session.query(Verkauf.id).filter(Verkauf.benutzer_id == benutzer_id).first() is not None
    hat_abschluesse = session.query(Kassenabschluss.id).filter(Kassenabschluss.benutzer_id == benutzer_id).first() is not None
    if hat_verkaeufe or hat_abschluesse:
        raise HTTPException(
            status_code=409,
            detail="Dieser Benutzer hat bereits Kassendaten. Bitte stattdessen deaktivieren, damit Belege und Auswertungen nachvollziehbar bleiben.",
        )

    if b.aktiv and b.rolle.stufe >= 20:
        aktive_admins = (
            session.query(Benutzer)
            .join(Rolle)
            .filter(Benutzer.aktiv.is_(True), Rolle.stufe >= 20, Benutzer.id != benutzer_id)
            .count()
        )
        if aktive_admins == 0:
            raise HTTPException(status_code=409, detail="Der letzte aktive Administrator kann nicht gelöscht werden.")

    session.query(Sitzung).filter(Sitzung.benutzer_id == benutzer_id).delete(synchronize_session=False)
    session.add(AuditLog(benutzer=aktueller_benutzer.name, aktion="benutzer.loeschen", datensatz=f"{b.id}:{b.name}"))
    session.delete(b)
    session.commit()
    return Response(status_code=204)
