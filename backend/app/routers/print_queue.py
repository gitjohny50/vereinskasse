"""Endpunkte der Druckwarteschlange (Phase 4).

Bediener können die Warteschlange sehen, offene Aufträge verarbeiten und einzelne
Aufträge wiederholen (um einen fehlgeschlagenen Bon nachzuholen). Das Abbrechen
eines Auftrags ist Administratoren vorbehalten.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import print_queue
from ..auth import require_admin, require_bediener
from ..database import get_session
from ..models import Benutzer, Druckauftrag
from ..schemas import DruckauftragOut, QueueStatusOut, QueueVerarbeitenOut

router = APIRouter(prefix="/api/druckwarteschlange", tags=["druckwarteschlange"],
                   dependencies=[Depends(require_bediener)])


@router.get("", response_model=list[DruckauftragOut])
def liste(status: str | None = None, limit: int = 100, session: Session = Depends(get_session)) -> list[Druckauftrag]:
    q = session.query(Druckauftrag)
    if status:
        # Mehrere Status kommagetrennt zulassen, z. B. "offen,fehlgeschlagen"
        wanted = {s.strip() for s in status.split(",") if s.strip()}
        q = q.filter(Druckauftrag.status.in_(wanted))
    return q.order_by(Druckauftrag.id.desc()).limit(min(limit, 300)).all()


@router.get("/status", response_model=QueueStatusOut)
def status(session: Session = Depends(get_session)) -> QueueStatusOut:
    return QueueStatusOut(**print_queue.status(session))


@router.post("/verarbeiten", response_model=QueueVerarbeitenOut)
def verarbeiten(session: Session = Depends(get_session)) -> QueueVerarbeitenOut:
    return QueueVerarbeitenOut(**print_queue.verarbeite_offene(session))


@router.post("/{auftrag_id}/wiederholen", response_model=DruckauftragOut)
def wiederholen(auftrag_id: int, session: Session = Depends(get_session),
                benutzer: Benutzer = Depends(require_bediener)) -> Druckauftrag:
    return print_queue.wiederhole(session, auftrag_id, benutzer=benutzer.name)


@router.post("/{auftrag_id}/abbrechen", response_model=DruckauftragOut)
def abbrechen(auftrag_id: int, session: Session = Depends(get_session),
              benutzer: Benutzer = Depends(require_admin)) -> Druckauftrag:
    return print_queue.abbrechen(session, auftrag_id, benutzer=benutzer.name)
