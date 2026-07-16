"""Authentifizierungs-Endpunkte."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from .. import auth
from ..database import get_session
from ..models import Benutzer
from ..schemas import LoginIn, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/benutzerliste")
def benutzerliste(session: Session = Depends(get_session)) -> list[dict]:
    """Öffentliche Auswahlliste für den Anmeldebildschirm: nur ID und Name
    aktiver Benutzer. Keine PIN, keine Rolle - nur die Auswahl zum Tippen."""
    rows = session.query(Benutzer).filter(Benutzer.aktiv.is_(True)).order_by(Benutzer.name).all()
    return [{"id": b.id, "name": b.name} for b in rows]


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: Session = Depends(get_session)) -> TokenOut:
    sitzung = auth.login(session, payload.benutzer_id, payload.pin)
    b = sitzung.benutzer
    return TokenOut(token=sitzung.token, benutzer_id=b.id, name=b.name, rolle=b.rolle.name, stufe=b.rolle.stufe)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), session: Session = Depends(get_session)) -> dict:
    token = auth._extract_token(authorization)
    if token:
        auth.logout(session, token)
    return {"ok": True}


@router.get("/me", response_model=TokenOut)
def me(benutzer: Benutzer = Depends(auth.get_current_user)) -> TokenOut:
    return TokenOut(token="", benutzer_id=benutzer.id, name=benutzer.name, rolle=benutzer.rolle.name, stufe=benutzer.rolle.stufe)
