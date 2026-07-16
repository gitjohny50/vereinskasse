"""Hardware-Diagnose (Servicebereich, Lastenheft 6.3, 29).

Diese Endpunkte gehören in einer späteren Version hinter die Rollenprüfung
'Servicetechniker'. In Phase 1 ist die Authentifizierung noch nicht scharf
geschaltet; der Platzhalter-Benutzer wird protokolliert.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_service
from ..database import get_session
from ..hardware import service
from ..models import Benutzer
from ..schemas import ActionResult, CutTestIn, DrawerOpenIn, PrinterStatusOut

# Hardware-Diagnose erfordert Servicetechniker-Rechte (Lastenheft 6.3).
router = APIRouter(prefix="/api/diagnose", tags=["diagnose"], dependencies=[Depends(require_service)])


@router.get("/drucker/status", response_model=PrinterStatusOut)
def drucker_status(session: Session = Depends(get_session)) -> PrinterStatusOut:
    st = service.printer_status(session)
    return PrinterStatusOut(
        reachable=st.reachable,
        known=st.known,
        paper_ok=st.paper_ok,
        cover_closed=st.cover_closed,
        detail=st.detail,
    )


@router.post("/drucker/testseite", response_model=ActionResult)
def drucker_testseite(session: Session = Depends(get_session), benutzer: Benutzer = Depends(require_service)) -> ActionResult:
    return ActionResult(**service.run_test_page(session, benutzer=benutzer.name))


@router.post("/drucker/schnitt-test", response_model=ActionResult)
def drucker_schnitt_test(payload: CutTestIn, session: Session = Depends(get_session), benutzer: Benutzer = Depends(require_service)) -> ActionResult:
    result = service.run_cut_test(session, count=payload.anzahl, benutzer=benutzer.name)
    result.pop("anzahl", None)
    return ActionResult(**result)


@router.post("/schublade/oeffnen", response_model=ActionResult)
def schublade_oeffnen(payload: DrawerOpenIn, session: Session = Depends(get_session), benutzer: Benutzer = Depends(require_service)) -> ActionResult:
    return ActionResult(**service.open_drawer(session, benutzer=benutzer.name, grund=payload.grund))
