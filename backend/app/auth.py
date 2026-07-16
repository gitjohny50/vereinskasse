"""Anmeldung, Sitzungen und Rollenprüfung (Lastenheft 6.4).

- Login per Benutzer-ID und PIN; bei Erfolg wird ein Sitzungstoken ausgegeben.
- Fehlversuche werden protokolliert und am Benutzer gezählt.
- Sitzungen haben einen Ablauf; jede Anfrage verlängert die Aktivität, sodass
  eine automatische Sperre nach Inaktivität möglich ist.
- Rechtestufen: Bediener 10, Administrator 20, Servicetechniker 30.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_session
from .models import AuditLog, Benutzer, Sitzung
from .security import new_token, verify_pin

STUFE_BEDIENER = 10
STUFE_ADMIN = 20
STUFE_SERVICE = 30

# Nach dieser Inaktivität läuft eine Sitzung ab (konfigurierbar in späterer Phase).
SITZUNG_INAKTIVITAET = timedelta(minutes=15)
MAX_FEHLVERSUCHE = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite liefert datetime ohne Zeitzone zurück; als UTC interpretieren."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def login(session: Session, benutzer_id: int, pin: str) -> Sitzung:
    benutzer = session.get(Benutzer, benutzer_id)
    if benutzer is None or not benutzer.aktiv:
        _protokoll(session, "auth.login_fehlgeschlagen", str(benutzer_id), "unbekannt/inaktiv")
        raise HTTPException(status_code=401, detail="Anmeldung fehlgeschlagen.")
    if benutzer.fehlversuche >= MAX_FEHLVERSUCHE:
        _protokoll(session, "auth.gesperrt", str(benutzer_id), "zu viele Fehlversuche")
        raise HTTPException(status_code=423, detail="Benutzer gesperrt. Bitte Administrator kontaktieren.")
    if not verify_pin(pin, benutzer.pin_hash):
        benutzer.fehlversuche += 1
        _protokoll(session, "auth.login_fehlgeschlagen", str(benutzer_id), f"falsche PIN (#{benutzer.fehlversuche})")
        session.commit()
        raise HTTPException(status_code=401, detail="Anmeldung fehlgeschlagen.")

    benutzer.fehlversuche = 0
    benutzer.letzter_login = _now()
    sitzung = Sitzung(
        token=new_token(),
        benutzer_id=benutzer.id,
        laeuft_ab_am=_now() + SITZUNG_INAKTIVITAET,
    )
    session.add(sitzung)
    _protokoll(session, "auth.login", str(benutzer_id), benutzer.name)
    session.commit()
    return sitzung


def logout(session: Session, token: str) -> None:
    sitzung = session.get(Sitzung, token)
    if sitzung is not None:
        session.delete(sitzung)
        session.commit()


def _protokoll(session: Session, aktion: str, datensatz: str, detail: str) -> None:
    session.add(AuditLog(benutzer="auth", aktion=aktion, datensatz=datensatz, nachher=detail))


def _resolve(session: Session, token: str | None) -> Benutzer:
    if not token:
        raise HTTPException(status_code=401, detail="Nicht angemeldet.")
    sitzung = session.get(Sitzung, token)
    if sitzung is None:
        raise HTTPException(status_code=401, detail="Sitzung ungültig.")
    if _aware(sitzung.laeuft_ab_am) < _now():
        session.delete(sitzung)
        session.commit()
        raise HTTPException(status_code=401, detail="Sitzung abgelaufen.")
    # Aktivität verlängern (gleitende Inaktivitätssperre).
    sitzung.letzte_aktivitaet = _now()
    sitzung.laeuft_ab_am = _now() + SITZUNG_INAKTIVITAET
    session.commit()
    return sitzung.benutzer


def _extract_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Benutzer:
    return _resolve(session, _extract_token(authorization))


def require_role(min_stufe: int):
    """Erzeugt eine Dependency, die mindestens die angegebene Rechtestufe verlangt."""

    def dependency(benutzer: Benutzer = Depends(get_current_user)) -> Benutzer:
        if benutzer.rolle.stufe < min_stufe:
            raise HTTPException(status_code=403, detail="Nicht berechtigt.")
        return benutzer

    return dependency


require_bediener = require_role(STUFE_BEDIENER)
require_admin = require_role(STUFE_ADMIN)
require_service = require_role(STUFE_SERVICE)
