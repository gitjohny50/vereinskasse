"""Druckwarteschlange (Phase 4 - Lastenheft 14.9/14.10: zuverlässiger Druck).

Jeder Druck (Bon, Artikelticket, Nachdruck) wird als `Druckauftrag` mit seinen
fertigen ESC/POS-Bytes gespeichert und dann versucht. Schlägt der Druck fehl
(Drucker offline, Papier leer), bleibt der Auftrag in der Warteschlange und kann
automatisch oder manuell wiederholt werden - der Verkauf selbst ist bereits
gebucht und geht nie verloren.

Statuslebenszyklus:  offen -> erfolgreich
                     offen -> (Fehler, unter max) -> offen
                     offen -> (Fehler, max erreicht) -> fehlgeschlagen
                     offen/fehlgeschlagen -> abgebrochen (manuell)
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .hardware import service as hw
from .hardware.factory import build_printer
from .hardware.printer_base import PrinterAdapter

OFFEN = "offen"
ERFOLGREICH = "erfolgreich"
FEHLGESCHLAGEN = "fehlgeschlagen"
ABGEBROCHEN = "abgebrochen"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _printer(session: Session, injected: PrinterAdapter | None) -> PrinterAdapter:
    if injected is not None:
        return injected
    cfg = hw.load_hw_settings(session)
    return build_printer(cfg, mock_log_path=hw._mock_log_path(session))


def enqueue(
    session: Session, *, dokumenttyp: str, payload: bytes, verkauf_id: int | None = None,
    nachdruck: bool = False, max_versuche: int = 3, drucker: str = "", bezeichnung: str = "",
) -> models.Druckauftrag:
    auftrag = models.Druckauftrag(
        dokumenttyp=dokumenttyp, bezeichnung=bezeichnung, drucker=drucker, status=OFFEN, versuche=0,
        max_versuche=max_versuche, nachdruck=nachdruck, verkauf_id=verkauf_id,
        payload_b64=base64.b64encode(payload).decode("ascii"),
    )
    session.add(auftrag)
    session.commit()
    session.refresh(auftrag)
    return auftrag


def _versuch(session: Session, auftrag: models.Druckauftrag, printer: PrinterAdapter) -> bool:
    """Ein Druckversuch. Aktualisiert Status, Versuchszähler und Fehlermeldung."""
    payload = base64.b64decode(auftrag.payload_b64) if auftrag.payload_b64 else b""
    try:
        result = printer.send(payload)
        ok, detail = result.ok, result.detail
    except Exception as exc:  # Adapter, der nicht sauber abfängt
        ok, detail = False, f"Ausnahme: {exc}"

    auftrag.versuche += 1
    auftrag.drucker = printer.name
    auftrag.aktualisiert_am = _now()
    if ok:
        auftrag.status = ERFOLGREICH
        auftrag.letzte_fehlermeldung = ""
    else:
        auftrag.letzte_fehlermeldung = detail
        auftrag.status = FEHLGESCHLAGEN if auftrag.versuche >= auftrag.max_versuche else OFFEN
    session.commit()
    return ok


def verarbeite_offene(session: Session, printer: PrinterAdapter | None = None, limit: int = 100) -> dict:
    """Versucht alle offenen Aufträge (FIFO). Für automatische Wiederholung."""
    offen = (
        session.query(models.Druckauftrag)
        .filter(models.Druckauftrag.status == OFFEN)
        .order_by(models.Druckauftrag.id)
        .limit(limit)
        .all()
    )
    if not offen:
        return {"verarbeitet": 0, "erfolg": 0, "fehler": 0}
    p = _printer(session, printer)
    erfolg = 0
    for auftrag in offen:
        if _versuch(session, auftrag, p):
            erfolg += 1
    return {"verarbeitet": len(offen), "erfolg": erfolg, "fehler": len(offen) - erfolg}


def wiederhole(session: Session, auftrag_id: int, benutzer: str, printer: PrinterAdapter | None = None) -> models.Druckauftrag:
    """Manuelle Wiederholung - auch für fehlgeschlagene oder abgebrochene Aufträge.
    Erhöht bei Bedarf das Limit, damit ein weiterer Versuch möglich ist."""
    auftrag = session.get(models.Druckauftrag, auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden.")
    if auftrag.status == ERFOLGREICH:
        return auftrag
    if auftrag.versuche >= auftrag.max_versuche:
        auftrag.max_versuche = auftrag.versuche + 1
    auftrag.status = OFFEN
    session.add(models.AuditLog(benutzer=benutzer, aktion="druck.wiederholung", datensatz=str(auftrag_id)))
    session.commit()
    _versuch(session, auftrag, _printer(session, printer))
    session.refresh(auftrag)
    return auftrag


def abbrechen(session: Session, auftrag_id: int, benutzer: str) -> models.Druckauftrag:
    auftrag = session.get(models.Druckauftrag, auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden.")
    if auftrag.status == ERFOLGREICH:
        raise HTTPException(status_code=409, detail="Erfolgreiche Aufträge können nicht abgebrochen werden.")
    auftrag.status = ABGEBROCHEN
    auftrag.aktualisiert_am = _now()
    session.add(models.AuditLog(benutzer=benutzer, aktion="druck.abbruch", datensatz=str(auftrag_id)))
    session.commit()
    session.refresh(auftrag)
    return auftrag


def status(session: Session) -> dict:
    rows = dict(
        session.query(models.Druckauftrag.status, func.count())
        .group_by(models.Druckauftrag.status)
        .all()
    )
    return {
        "offen": rows.get(OFFEN, 0),
        "fehlgeschlagen": rows.get(FEHLGESCHLAGEN, 0),
        "erfolgreich": rows.get(ERFOLGREICH, 0),
        "abgebrochen": rows.get(ABGEBROCHEN, 0),
    }


# -------------------------------------------------------------------
# Verkaufsdruck über die Warteschlange
# -------------------------------------------------------------------
def _verkauf_bon_bytes(session: Session, cfg: dict, verkauf: models.Verkauf, *, schublade: bool, kopie: bool) -> bytes:
    profil = session.get(models.Kassenprofil, verkauf.kassenprofil_id)
    benutzer = session.get(models.Benutzer, verkauf.benutzer_id)
    zahlung = verkauf.zahlungen[0] if verkauf.zahlungen else None
    return hw.build_receipt_bytes(
        cfg, bonkopf=profil.bonkopf if profil else "", bonfuss=profil.bonfuss if profil else "",
        belegnummer=verkauf.belegnummer, zeitpunkt=verkauf.zeitpunkt,
        bediener=benutzer.name if benutzer else "?", positionen=hw._pos_dicts(verkauf),
        waren_cent=verkauf.waren_cent, pfand_cent=verkauf.pfand_cent, gesamt_cent=verkauf.gesamt_cent,
        zahlung_name=zahlung.bezeichnung if zahlung else "-",
        gegeben_cent=zahlung.gegeben_cent if zahlung else verkauf.gesamt_cent,
        rueckgeld_cent=zahlung.rueckgeld_cent if zahlung else 0, schublade=schublade, kopie=kopie,
    )


def druck_verkauf(session: Session, verkauf_id: int, schublade: bool, printer: PrinterAdapter | None = None) -> dict:
    """Reiht die Artikeltickets ein - und den Beleg (Bon) nur, wenn der
    Auto-Belegdruck aktiv ist (Einstellung ``verkauf.beleg_autodruck``).
    Ist er aus, wird bei Barzahlung die Schublade per eigenem Impuls geöffnet,
    da der Kick sonst im Bon steckt. Fehlgeschlagene Aufträge bleiben in der
    Warteschlange."""
    cfg = hw.load_hw_settings(session)
    verkauf = session.get(models.Verkauf, verkauf_id)
    positionen = hw._pos_dicts(verkauf)
    auto_beleg = cfg.get("verkauf.beleg_autodruck", "1") == "1"

    # Vereinsname für die Kopfzeile der Artikeltickets ermitteln.
    profil = session.get(models.Kassenprofil, verkauf.kassenprofil_id)
    verein = session.get(models.Verein, profil.verein_id) if profil else None
    verein_name = verein.name if verein else ""

    jobs: list[models.Druckauftrag] = []

    if auto_beleg:
        bon_bytes = _verkauf_bon_bytes(session, cfg, verkauf, schublade=schublade, kopie=False)
        jobs.append(enqueue(session, dokumenttyp="Bon", payload=bon_bytes, verkauf_id=verkauf.id,
                            bezeichnung=f"Beleg {verkauf.belegnummer}"))

    # Jedes Artikelticket als EIGENEN Auftrag: so erscheint jeder Artikel einzeln
    # im Druckprotokoll und lässt sich einzeln wiederholen; ein hängendes Ticket
    # blockiert die übrigen nicht mehr. Der Vereinsname steht als Kopfzeile darauf.
    tickets = hw._ticket_liste(positionen)
    for bez in tickets:
        payload = hw.build_ticket_bytes(cfg, bez, verkauf.belegnummer, kopf=verein_name)
        jobs.append(enqueue(session, dokumenttyp="Artikelticket", payload=payload,
                            verkauf_id=verkauf.id, bezeichnung=bez))

    # Schublade nur separat öffnen, wenn kein Bon gedruckt wird (der Bon enthält
    # den Kick bereits) und die Zahlungsart die Schublade vorsieht.
    if schublade and not auto_beleg and cfg.get("schublade.aktiv", "1") == "1":
        jobs.append(enqueue(session, dokumenttyp="Schublade", payload=hw.build_drawer_pulse(cfg),
                            verkauf_id=verkauf.id, bezeichnung="Kassenschublade"))

    p = _printer(session, printer)
    ok = True
    for job in jobs:
        if not _versuch(session, job, p):
            ok = False
    return {"ok": ok, "auftraege": len(jobs), "tickets": len(tickets), "drucker": p.name}


def druck_beleg(session: Session, verkauf_id: int, benutzer: str, printer: PrinterAdapter | None = None) -> dict:
    """Beleg (Original-Bon) auf Anforderung drucken - ohne Schublade, ohne
    Tickets, ohne KOPIE-Kennzeichnung."""
    cfg = hw.load_hw_settings(session)
    verkauf = session.get(models.Verkauf, verkauf_id)
    bon_bytes = _verkauf_bon_bytes(session, cfg, verkauf, schublade=False, kopie=False)
    job = enqueue(session, dokumenttyp="Beleg", payload=bon_bytes, verkauf_id=verkauf.id, bezeichnung=f"Beleg {verkauf.belegnummer}")
    session.add(models.AuditLog(benutzer=benutzer, aktion="verkauf.beleg", datensatz=verkauf.belegnummer))
    session.commit()
    ok = _versuch(session, job, _printer(session, printer))
    return {"ok": ok, "detail": job.letzte_fehlermeldung, "auftrag_id": job.id, "drucker": job.drucker}


def druck_nachdruck(session: Session, verkauf_id: int, benutzer: str, printer: PrinterAdapter | None = None) -> dict:
    """Belegkopie über die Warteschlange - ohne Schublade, ohne Tickets."""
    cfg = hw.load_hw_settings(session)
    verkauf = session.get(models.Verkauf, verkauf_id)
    bon_bytes = _verkauf_bon_bytes(session, cfg, verkauf, schublade=False, kopie=True)
    job = enqueue(session, dokumenttyp="Bon-Nachdruck", payload=bon_bytes, verkauf_id=verkauf.id, nachdruck=True, bezeichnung=f"Kopie {verkauf.belegnummer}")
    session.add(models.AuditLog(benutzer=benutzer, aktion="verkauf.nachdruck", datensatz=verkauf.belegnummer))
    session.commit()
    ok = _versuch(session, job, _printer(session, printer))
    return {"ok": ok, "detail": job.letzte_fehlermeldung, "auftrag_id": job.id, "drucker": job.drucker}
