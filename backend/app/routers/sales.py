"""Verkaufs-Endpunkte (Lastenheft 11, 12).

Verkaufen darf ab Bediener. Ein Verkauf ist nach dem Abschluss unveränderlich -
es gibt bewusst keine Änderungs- oder Löschendpunkte, nur Anlegen, Ansehen und
Nachdruck.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import sales
from .. import print_queue
from ..auth import require_bediener
from ..database import get_session
from ..hardware import service as hw
from ..models import Benutzer, Verkauf
from ..schemas import (
    ActionResult,
    BerechnungIn,
    BerechnungOut,
    PositionOut,
    VerkaufIn,
    VerkaufOut,
    ZahlungOut,
)

router = APIRouter(prefix="/api/verkauf", tags=["verkauf"], dependencies=[Depends(require_bediener)])


@router.post("/berechnung", response_model=BerechnungOut)
def berechnung(payload: BerechnungIn, session: Session = Depends(get_session)) -> BerechnungOut:
    """Live-Berechnung des Warenkorbs inkl. automatischem Pfand - ohne zu buchen."""
    calc = sales.berechne(
        session, payload.kassenprofil_id,
        [i.model_dump() for i in payload.artikel],
        [r.model_dump() for r in payload.pfand_rueckgaben],
        payload.veranstaltung_id,
    )
    return BerechnungOut(**calc)


@router.post("", response_model=VerkaufOut, status_code=201)
def abschliessen(payload: VerkaufIn, session: Session = Depends(get_session),
                 benutzer: Benutzer = Depends(require_bediener)) -> VerkaufOut:
    verkauf = sales.finalisiere(
        session, kassenprofil_id=payload.kassenprofil_id, veranstaltung_id=payload.veranstaltung_id,
        artikel_items=[i.model_dump() for i in payload.artikel],
        pfand_rueckgaben=[r.model_dump() for r in payload.pfand_rueckgaben],
        zahlungsmethode_id=payload.zahlungsmethode_id, gegeben_cent=payload.gegeben_cent, benutzer=benutzer,
    )
    return _verkauf_out(verkauf)


@router.get("", response_model=list[VerkaufOut])
def liste(kassenprofil_id: int, limit: int = 50, session: Session = Depends(get_session)) -> list[VerkaufOut]:
    rows = (
        session.query(Verkauf)
        .filter(Verkauf.kassenprofil_id == kassenprofil_id)
        .order_by(Verkauf.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [_verkauf_out(v) for v in rows]


@router.get("/{verkauf_id}", response_model=VerkaufOut)
def detail(verkauf_id: int, session: Session = Depends(get_session)) -> VerkaufOut:
    v = session.get(Verkauf, verkauf_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Beleg nicht gefunden.")
    return _verkauf_out(v)


@router.post("/{verkauf_id}/nachdruck", response_model=ActionResult)
def nachdruck(verkauf_id: int, session: Session = Depends(get_session),
              benutzer: Benutzer = Depends(require_bediener)) -> ActionResult:
    v = session.get(Verkauf, verkauf_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Beleg nicht gefunden.")
    return ActionResult(**print_queue.druck_nachdruck(session, verkauf_id, benutzer=benutzer.name))


def _verkauf_out(v: Verkauf) -> VerkaufOut:
    z = v.zahlungen[0] if v.zahlungen else None
    return VerkaufOut(
        id=v.id, belegnummer=v.belegnummer, kassenprofil_id=v.kassenprofil_id,
        veranstaltung_id=v.veranstaltung_id, benutzer_id=v.benutzer_id, zeitpunkt=v.zeitpunkt,
        waren_cent=v.waren_cent, pfand_cent=v.pfand_cent, gesamt_cent=v.gesamt_cent, status=v.status,
        positionen=[
            PositionOut(typ=p.typ, bezeichnung=p.bezeichnung, einzelpreis_cent=p.einzelpreis_cent,
                        menge=p.menge, gesamt_cent=p.gesamt_cent, artikelticket_modus=p.artikelticket_modus,
                        steuersatz=p.steuersatz)
            for p in v.positionen
        ],
        zahlung=ZahlungOut(zahlungsmethode_id=z.zahlungsmethode_id, bezeichnung=z.bezeichnung,
                           betrag_cent=z.betrag_cent, gegeben_cent=z.gegeben_cent, rueckgeld_cent=z.rueckgeld_cent)
        if z else None,
    )
