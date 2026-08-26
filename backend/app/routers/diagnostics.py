"""Hardware-Diagnose (Servicebereich, Lastenheft 6.3, 29).

Diese Endpunkte gehören in einer späteren Version hinter die Rollenprüfung
'Servicetechniker'. In Phase 1 ist die Authentifizierung noch nicht scharf
geschaltet; der Platzhalter-Benutzer wird protokolliert.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_service
from ..database import get_session
from ..hardware import service
from ..models import Benutzer
from ..schemas import ActionResult, ClockSetIn, ClockStatusOut, CutTestIn, DrawerOpenIn, PrinterStatusOut, UsbListeOut
from ..timeutils import local_tz, now_local

# Hardware-Diagnose erfordert Servicetechniker-Rechte (Lastenheft 6.3).
router = APIRouter(prefix="/api/diagnose", tags=["diagnose"], dependencies=[Depends(require_service)])


def _hwclock_command() -> list[str] | None:
    for path in ("/usr/sbin/hwclock", "/sbin/hwclock", "/usr/bin/hwclock", "/bin/hwclock"):
        if Path(path).exists():
            return ["sudo", "-n", path, "--systohc"]
    return None


def _clock_status(detail: str = "") -> ClockStatusOut:
    jetzt = now_local()
    ntp_aktiv: bool | None = None
    try:
        res = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            ntp_aktiv = res.stdout.strip().lower() == "yes"
    except (OSError, subprocess.SubprocessError):
        ntp_aktiv = None
    return ClockStatusOut(
        lokal=jetzt.isoformat(),
        datum=jetzt.strftime("%Y-%m-%d"),
        uhrzeit=jetzt.strftime("%H:%M"),
        zeitzone=str(local_tz()),
        ntp_aktiv=ntp_aktiv,
        detail=detail,
    )


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


@router.get("/drucker/usb-geraete", response_model=UsbListeOut)
def usb_geraete() -> UsbListeOut:
    """Angeschlossene USB-Geräte auflisten, um Hersteller-/Produkt-ID des
    Druckers ohne 'lsusb' zu ermitteln."""
    return UsbListeOut(**service.list_usb_devices())


@router.get("/uhr", response_model=ClockStatusOut)
def uhr_status() -> ClockStatusOut:
    return _clock_status()


@router.post("/uhr", response_model=ClockStatusOut)
def uhr_stellen(payload: ClockSetIn, benutzer: Benutzer = Depends(require_service)) -> ClockStatusOut:
    aktuelle_zeit = now_local()
    ziel = aktuelle_zeit.replace(
        year=payload.datum.year,
        month=payload.datum.month,
        day=payload.datum.day,
        hour=payload.stunde,
        minute=payload.minute,
        second=0,
        microsecond=0,
    )
    ziel_lokal = ziel.strftime("%Y-%m-%d %H:%M:%S")
    commands = [
        ["sudo", "-n", "/usr/bin/timedatectl", "set-ntp", "false"],
        ["sudo", "-n", "/usr/bin/timedatectl", "set-time", ziel_lokal],
    ]
    for cmd in commands:
        res = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            detail = (
                "Uhr konnte nicht gesetzt werden. Bitte sudoers erlauben: "
                "admin ALL=(root) NOPASSWD: /usr/bin/timedatectl"
            )
            if res.stderr.strip():
                detail += f" · {res.stderr.strip()}"
            return _clock_status(detail)

    hwclock_cmd = _hwclock_command()
    if hwclock_cmd is None:
        return _clock_status(
            f"Uhr gestellt von {benutzer.name} auf {ziel.strftime('%d.%m.%Y %H:%M')}. "
            "RTC wurde nicht geschrieben: hwclock ist nicht installiert."
        )

    res = subprocess.run(hwclock_cmd, check=False, capture_output=True, text=True, timeout=5)
    if res.returncode != 0:
        detail = (
            f"Uhr gestellt von {benutzer.name} auf {ziel.strftime('%d.%m.%Y %H:%M')}. "
            "RTC konnte nicht geschrieben werden. Bitte sudoers fuer hwclock pruefen."
        )
        if res.stderr.strip():
            detail += f" · {res.stderr.strip()}"
        return _clock_status(detail)

    return _clock_status(f"Uhr gestellt von {benutzer.name} auf {ziel.strftime('%d.%m.%Y %H:%M')} und in die RTC geschrieben.")


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
