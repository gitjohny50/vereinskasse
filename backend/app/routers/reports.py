"""Kassenabschluss- und Berichts-Endpunkte (Phase 5).

Der Kassenabschluss ist eine Leitungsfunktion (Kassensturz, Umsatzzahlen) und
daher Administratoren vorbehalten. Ein Z-Abschluss ist nach dem Erstellen
unveränderlich - es gibt nur Erstellen, Ansehen und Nachdruck.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import print_queue, reports
from ..auth import require_admin
from ..database import get_session
from ..models import Benutzer, Kassenabschluss
from ..schemas import ActionResult, BerichtOut, KassenabschlussKopfOut, ZAbschlussIn

router = APIRouter(prefix="/api/abschluss", tags=["kassenabschluss"],
                   dependencies=[Depends(require_admin)])


@router.get("/x", response_model=BerichtOut)
def x_bericht(kassenprofil_id: int, anfangsbestand_cent: int = 0, gezaehlt_cent: int | None = None,
              session: Session = Depends(get_session)) -> BerichtOut:
    """Zwischenstand über die noch nicht abgeschlossenen Verkäufe - ohne zu buchen."""
    return BerichtOut(**reports.x_bericht(session, kassenprofil_id, anfangsbestand_cent, gezaehlt_cent))


@router.post("/z", response_model=BerichtOut, status_code=201)
def z_abschluss(payload: ZAbschlussIn, session: Session = Depends(get_session),
                benutzer: Benutzer = Depends(require_admin)) -> BerichtOut:
    """Tagesabschluss: schließt die offenen Verkäufe ab, speichert und druckt ihn."""
    abschluss = reports.erstelle_z(
        session, payload.kassenprofil_id, benutzer,
        anfangsbestand_cent=payload.anfangsbestand_cent, gezaehlt_cent=payload.gezaehlt_cent,
    )
    return BerichtOut(**reports.abschluss_bericht(session, abschluss))


@router.get("", response_model=list[KassenabschlussKopfOut])
def liste(kassenprofil_id: int, limit: int = 100, session: Session = Depends(get_session)) -> list[Kassenabschluss]:
    return (
        session.query(Kassenabschluss)
        .filter(Kassenabschluss.kassenprofil_id == kassenprofil_id)
        .order_by(Kassenabschluss.id.desc())
        .limit(min(limit, 300))
        .all()
    )


@router.get("/{abschluss_id}", response_model=BerichtOut)
def detail(abschluss_id: int, session: Session = Depends(get_session)) -> BerichtOut:
    abschluss = session.get(Kassenabschluss, abschluss_id)
    if abschluss is None:
        raise HTTPException(status_code=404, detail="Kassenabschluss nicht gefunden.")
    return BerichtOut(**reports.abschluss_bericht(session, abschluss))


@router.post("/{abschluss_id}/nachdruck", response_model=ActionResult)
def nachdruck(abschluss_id: int, session: Session = Depends(get_session)) -> ActionResult:
    abschluss = session.get(Kassenabschluss, abschluss_id)
    if abschluss is None:
        raise HTTPException(status_code=404, detail="Kassenabschluss nicht gefunden.")
    return ActionResult(**reports.druck_bericht(session, abschluss_id))
