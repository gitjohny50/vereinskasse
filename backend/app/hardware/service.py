"""Druck- und Schubladendienst.

Baut die Phase-1-Testdokumente (Testseite, Schnitttest, reiner Schubladen-
impuls), sendet sie über den konfigurierten Adapter und protokolliert jeden
Vorgang in Druckauftrag + Audit-Log.

Sicherheitsregeln aus dem Lastenheft, die hier gelten:
  * Ein Testdruck erzeugt keinen Verkauf und keine Umsätze (15.5).
  * Die Kassenschublade wird pro Auslösung genau einmal angesteuert (13.4).
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    Benutzer,
    Druckauftrag,
    Kassenprofil,
    Systemeinstellung,
    Verkauf,
)
from ..money import format_cents
from ..timeutils import to_local
from .escpos import EscposBuilder
from .factory import DEFAULT_HW_SETTINGS, build_printer
from .printer_base import PrinterStatus


def load_hw_settings(session: Session) -> dict[str, str]:
    """Liest Hardware-Einstellungen aus der DB, ergänzt fehlende mit Standardwerten."""
    stored = {
        row.schluessel: row.wert
        for row in session.query(Systemeinstellung).all()
    }
    cfg = dict(DEFAULT_HW_SETTINGS)
    cfg.update({k: v for k, v in stored.items() if k in DEFAULT_HW_SETTINGS})
    return cfg


def ensure_defaults(session: Session) -> None:
    """Legt fehlende Standard-Einstellungen beim ersten Start an."""
    existing = {row.schluessel for row in session.query(Systemeinstellung).all()}
    created = False
    for key, value in DEFAULT_HW_SETTINGS.items():
        if key not in existing:
            session.add(Systemeinstellung(schluessel=key, wert=value))
            created = True
    if created:
        session.commit()


def _builder(cfg: dict[str, str]) -> EscposBuilder:
    return EscposBuilder(
        codepage_id=int(cfg.get("drucker.codepage_id", "19")),
        encoding=cfg.get("drucker.encoding", "cp858"),
    )


def build_test_page(cfg: dict[str, str]) -> bytes:
    """Testseite: prüft Umlaute, Eurozeichen, Stile, QR und Schnitt (Lastenheft 29.1)."""
    b = _builder(cfg)
    b.init()
    _print_logo_if_configured(b, cfg)
    b.align("center").bold(True).size(2, 2).line("VEREINSKASSE")
    b.size(1, 1).bold(False).line("Testseite - kein Verkauf").feed(1)
    b.align("left")
    b.line("Umlaute:  aeoue -> \u00e4\u00f6\u00fc\u00df \u00c4\u00d6\u00dc")
    b.line("Euro:     Preis 2,50 \u20ac")
    b.bold(True).line("Fett: BEZAHLT").bold(False)
    b.size(2, 1).line("Doppelte Breite").size(1, 2).line("Doppelte Hoehe").size(1, 1)
    b.feed(1).align("center")
    qr_url = cfg.get("diagnose.testseite.qr_url", "").strip()
    if qr_url:
        b.qr(qr_url, module_size=6)
    b.feed(1).line("Zeit: " + datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M:%S"))
    b.cut(mode=cfg.get("schnitt.modus", "partial"), feed_lines=int(cfg.get("schnitt.vorschub_zeilen", "3")))
    return b.build()


def build_cut_test(cfg: dict[str, str], count: int = 3) -> bytes:
    """Mehrere kurze Tickets mit Schnitt dazwischen (Lastenheft 29.2)."""
    b = _builder(cfg)
    b.init()
    mode = cfg.get("schnitt.modus", "partial")
    feed = int(cfg.get("schnitt.vorschub_zeilen", "3"))
    for i in range(1, count + 1):
        b.align("center").bold(True).size(2, 2).line(f"TICKET {i}/{count}")
        b.size(1, 1).bold(False).line("Schnitt-Test")
        b.cut(mode=mode, feed_lines=feed)
    return b.build()


def build_startup_receipt(cfg: dict[str, str], info: dict[str, str | list[str]]) -> bytes:
    """Startbeleg nach systemd/Backend-Start mit Netzwerk- und Betriebsdaten."""
    width = int(cfg.get("bon.breite_zeichen", "42"))
    urls = info.get("urls", [])
    if not isinstance(urls, list):
        urls = []
    b = _builder(cfg)
    b.init()
    b.align("center").bold(True).size(1, 2).line("VEREINSKASSE").size(1, 1)
    b.line("Backend gestartet").bold(False).feed(1)
    b.align("left")
    b.line("-" * width)
    for label, key in [
        ("Zeit:", "zeit"),
        ("Host:", "hostname"),
        ("User:", "user"),
        ("Version:", "version"),
        ("Profil:", "profil"),
        ("Daten:", "data_dir"),
        ("Drucker:", "drucker"),
    ]:
        value = str(info.get(key, "-"))
        b.line(_zeile(label, value, width))
    b.line("-" * width)
    b.bold(True).line("Erreichbar unter:").bold(False)
    if urls:
        for url in urls:
            b.line(str(url))
    else:
        b.line("Keine Netzwerkadresse gefunden")
    b.line("-" * width)
    b.align("center")
    qr_url = str(urls[0]) if urls else ""
    if qr_url:
        b.qr(qr_url, module_size=5)
    b.feed(1).line("Bereit fuer Verkauf")
    b.cut(mode=cfg.get("schnitt.modus", "partial"), feed_lines=int(cfg.get("schnitt.vorschub_zeilen", "3")))
    return b.build()


def run_startup_receipt(session: Session, info: dict[str, str | list[str]], benutzer: str = "systemd") -> dict:
    cfg = load_hw_settings(session)
    printer = build_printer(cfg, mock_log_path=_mock_log_path(session))
    result = printer.send(build_startup_receipt(cfg, info))
    auftrag = _log(session, "Startbeleg", printer.name, result.ok, result.detail, benutzer)
    return {"ok": result.ok, "detail": result.detail, "auftrag_id": auftrag.id, "drucker": printer.name}


def build_drawer_pulse(cfg: dict[str, str]) -> bytes:
    """Reiner Schubladenimpuls ohne Druckinhalt (Lastenheft 13.3 Testbutton)."""
    b = _builder(cfg)
    b.init()
    b.kick_drawer(
        pin=int(cfg.get("schublade.pin", "0")),
        on_ms=int(cfg.get("schublade.puls_ms", "100")),
        off_ms=int(cfg.get("schublade.pause_ms", "100")),
    )
    return b.build()


def _log(session: Session, dokumenttyp: str, drucker: str, ok: bool, detail: str, benutzer: str) -> Druckauftrag:
    auftrag = Druckauftrag(
        dokumenttyp=dokumenttyp,
        drucker=drucker,
        status="erfolgreich" if ok else "fehlgeschlagen",
        versuche=1,
        letzte_fehlermeldung="" if ok else detail,
    )
    session.add(auftrag)
    session.add(
        AuditLog(
            benutzer=benutzer,
            aktion=f"hardware.{dokumenttyp}",
            datensatz=drucker,
            nachher=f"ok={ok}; {detail}",
        )
    )
    session.commit()
    return auftrag


def run_test_page(session: Session, benutzer: str = "servicetechniker") -> dict:
    cfg = load_hw_settings(session)
    printer = build_printer(cfg, mock_log_path=_mock_log_path(session))
    result = printer.send(build_test_page(cfg))
    auftrag = _log(session, "Testseite", printer.name, result.ok, result.detail, benutzer)
    return {"ok": result.ok, "detail": result.detail, "auftrag_id": auftrag.id, "drucker": printer.name}


def run_cut_test(session: Session, count: int = 3, benutzer: str = "servicetechniker") -> dict:
    cfg = load_hw_settings(session)
    printer = build_printer(cfg, mock_log_path=_mock_log_path(session))
    result = printer.send(build_cut_test(cfg, count=count))
    auftrag = _log(session, "Schnitt-Test", printer.name, result.ok, result.detail, benutzer)
    return {"ok": result.ok, "detail": result.detail, "auftrag_id": auftrag.id, "anzahl": count, "drucker": printer.name}


def open_drawer(session: Session, benutzer: str = "servicetechniker", grund: str = "manueller Test") -> dict:
    """Manuelle Schubladenöffnung - protokolliert mit Benutzer, Zeit, Grund (Lastenheft 13.4)."""
    cfg = load_hw_settings(session)
    if cfg.get("schublade.aktiv", "1") != "1":
        return {"ok": False, "detail": "Schubladenfunktion ist deaktiviert"}
    printer = build_printer(cfg, mock_log_path=_mock_log_path(session))
    result = printer.send(build_drawer_pulse(cfg))
    auftrag = _log(session, "Schubladenimpuls", printer.name, result.ok, f"{grund}: {result.detail}", benutzer)
    return {"ok": result.ok, "detail": result.detail, "auftrag_id": auftrag.id, "drucker": printer.name}


def printer_status(session: Session) -> PrinterStatus:
    cfg = load_hw_settings(session)
    printer = build_printer(cfg, mock_log_path=_mock_log_path(session))
    return printer.status()


def _mock_log_path(session: Session):
    from ..config import settings

    return settings.data_dir / "mock-drucker.log"


# ===================================================================
# Phase 3: Bon- und Artikelticketdruck
# ===================================================================
def _zeile(links: str, rechts: str, width: int) -> str:
    """Zeile mit linksbündigem Text und rechtsbündigem Betrag."""
    platz = max(1, width - len(rechts))
    if len(links) > platz - 1:
        links = links[: platz - 1]
    return links.ljust(platz) + rechts


def _print_logo_if_configured(b: EscposBuilder, cfg: dict[str, str]) -> None:
    if cfg.get("bon.logo.aktiv", "0") != "1":
        return
    try:
        width_px = int(cfg.get("bon.logo.breite_px", "0"))
        height_px = int(cfg.get("bon.logo.hoehe_px", "0"))
        raster = base64.b64decode(cfg.get("bon.logo.raster_b64", ""), validate=True)
        b.align("center").raster_image(width_px, height_px, raster).feed(1)
    except (ValueError, binascii.Error):
        return


def build_receipt_bytes(
    cfg: dict[str, str], *, bonkopf: str, bonfuss: str, belegnummer: str, zeitpunkt: datetime,
    bediener: str, positionen: list[dict], waren_cent: int, pfand_cent: int, gesamt_cent: int,
    zahlung_name: str, gegeben_cent: int, rueckgeld_cent: int, schublade: bool, kopie: bool = False,
) -> bytes:
    """Baut den Kassenbon (Lastenheft 14). Bei kopie=True als Nachdruck gekennzeichnet."""
    width = int(cfg.get("bon.breite_zeichen", "42"))
    b = _builder(cfg)
    b.init()
    _print_logo_if_configured(b, cfg)
    b.align("center").bold(True).size(1, 2)
    for zeile in (bonkopf or "Vereinskasse").split("\n"):
        b.line(zeile)
    b.size(1, 1).bold(False)
    if kopie:
        b.line("*** KOPIE / NACHDRUCK ***")
    b.feed(1).align("left")
    b.line("-" * width)
    b.line(_zeile("Beleg-Nr:", belegnummer, width))
    b.line(_zeile("Datum:", to_local(zeitpunkt).strftime("%d.%m.%Y %H:%M"), width))
    b.line(_zeile("Bediener:", bediener, width))
    b.line("-" * width)
    for p in positionen:
        b.line(_zeile(f'{p["menge"]} x {p["bezeichnung"]}', format_cents(p["gesamt_cent"]), width))
    b.line("-" * width)
    b.line(_zeile("Waren:", format_cents(waren_cent), width))
    if pfand_cent != 0:
        b.line(_zeile("Pfand:", format_cents(pfand_cent), width))
    b.bold(True).size(1, 2).line(_zeile("GESAMT:", format_cents(gesamt_cent), width)).size(1, 1).bold(False)
    b.line("-" * width)
    b.line(_zeile(f"Zahlung {zahlung_name}:", format_cents(gegeben_cent), width))
    if rueckgeld_cent:
        b.line(_zeile("Rueckgeld:", format_cents(rueckgeld_cent), width))
    b.feed(1).align("center")
    for zeile in (bonfuss or "").split("\n"):
        if zeile:
            b.line(zeile)
    b.cut(mode=cfg.get("schnitt.modus", "partial"), feed_lines=int(cfg.get("schnitt.vorschub_zeilen", "3")))
    # Schublade nur beim echten Verkauf und nur wenn die Zahlungsart es vorsieht (Lastenheft 13.1).
    if schublade and cfg.get("schublade.aktiv", "1") == "1":
        b.kick_drawer(
            pin=int(cfg.get("schublade.pin", "0")),
            on_ms=int(cfg.get("schublade.puls_ms", "100")),
            off_ms=int(cfg.get("schublade.pause_ms", "100")),
        )
    return b.build()


def _ticket_liste(positionen: list[dict]) -> list[str]:
    """Erzeugt aus den Positionen die einzelnen Artikeltickets (Lastenheft 14.3):
    pro_stueck -> ein Ticket je Stück, pro_position -> ein Ticket je Position,
    kein -> keine Tickets."""
    tickets: list[str] = []
    for p in positionen:
        modus = p.get("artikelticket_modus", "kein")
        if modus == "pro_stueck":
            tickets.extend([p["bezeichnung"]] * p["menge"])
        elif modus == "pro_position":
            bez = p["bezeichnung"] if p["menge"] == 1 else f'{p["bezeichnung"]} x{p["menge"]}'
            tickets.append(bez)
    return tickets


def build_tickets_bytes(cfg: dict[str, str], tickets: list[str], belegnummer: str) -> bytes | None:
    if not tickets:
        return None
    b = _builder(cfg)
    b.init()
    for bez in tickets:
        _ticket_block(b, cfg, bez, belegnummer)
    return b.build()


def build_ticket_bytes(cfg: dict[str, str], bezeichnung: str, belegnummer: str, kopf: str = "") -> bytes:
    """Ein einzelnes Artikelticket für getrennte Druckaufträge je Artikel.

    ``kopf`` erscheint klein über dem Artikelnamen, z. B. Vereins- oder Veranstaltungsname.
    """
    b = _builder(cfg)
    b.init()
    _ticket_block(b, cfg, bezeichnung, belegnummer, kopf)
    return b.build()

def _ticket_block(b: EscposBuilder, cfg: dict[str, str], bezeichnung: str, belegnummer: str, kopf: str = "") -> None:
    mode = cfg.get("schnitt.modus", "partial")
    feed = int(cfg.get("schnitt.vorschub_zeilen", "3"))

    b.align("center")

    for zeile in (kopf or "Vereinskasse").split("\n"):
        if zeile.strip():
            b.bold(False).size(1, 1).line(zeile.strip())

    b.bold(True).size(2, 2).line(bezeichnung)
    # Einige ESC/POS-Drucker verschlucken nach doppelter Hoehe sonst den Anfang der Folgezeile.
    b.bold(False).size(1, 1).feed(1)
    b.line(f"Beleg {belegnummer}")
    b.cut(mode=mode, feed_lines=feed)

def _pos_dicts(verkauf: Verkauf) -> list[dict]:
    return [
        {
            "bezeichnung": p.bezeichnung, "menge": p.menge, "gesamt_cent": p.gesamt_cent,
            "artikelticket_modus": p.artikelticket_modus, "typ": p.typ,
        }
        for p in verkauf.positionen
    ]


# ===================================================================
# Phase 5: X-/Z-Berichtsdruck
# ===================================================================
def build_bericht_bytes(cfg: dict[str, str], bericht: dict, profil_name: str) -> bytes:
    """Baut den X- oder Z-Bericht (Lastenheft 15). `bericht` ist die Struktur aus
    app.reports (x_bericht / abschluss_bericht)."""
    from datetime import datetime as _dt  # lokal, um Importreihenfolge unkritisch zu halten

    width = int(cfg.get("bon.breite_zeichen", "42"))
    ist_z = bericht.get("typ") == "Z"
    b = _builder(cfg)
    b.init()
    b.align("center").bold(True).size(1, 2)
    b.line(profil_name or "Vereinskasse")
    b.line("TAGESABSCHLUSS (Z)" if ist_z else "ZWISCHENBERICHT (X)")
    b.size(1, 1).bold(False)
    if bericht.get("nummer"):
        b.line(str(bericht["nummer"]))
    b.feed(1).align("left")
    b.line("-" * width)

    def zeit(val) -> str:
        return to_local(val).strftime("%d.%m.%Y %H:%M") if isinstance(val, _dt) else "-"

    if bericht.get("von"):
        b.line(_zeile("Von:", zeit(bericht["von"]), width))
    b.line(_zeile("Bis:", zeit(bericht["bis"]), width))
    b.line(_zeile("Verkäufe:", str(bericht["anzahl_verkaeufe"]), width))
    b.line("-" * width)
    b.line(_zeile("Waren:", format_cents(bericht["waren_cent"]), width))
    b.line(_zeile("Pfand:", format_cents(bericht["pfand_cent"]), width))
    b.bold(True).size(1, 2).line(_zeile("GESAMT:", format_cents(bericht["gesamt_cent"]), width)).size(1, 1).bold(False)

    if bericht["zahlarten"]:
        b.line("-" * width)
        b.line("Zahlarten:")
        for z in bericht["zahlarten"]:
            b.line(_zeile(f'  {z["bezeichnung"]} ({z["anzahl"]})', format_cents(z["betrag_cent"]), width))

    b.line("-" * width)
    b.line("Bargeld:")
    b.line(_zeile("  Anfangsbestand:", format_cents(bericht["anfangsbestand_cent"]), width))
    b.line(_zeile("  Bar-Umsatz:", format_cents(bericht["bar_cent"]), width))
    b.line(_zeile("  Erwartet:", format_cents(bericht["erwartet_cent"]), width))
    if bericht.get("gezaehlt_cent") is not None:
        b.line(_zeile("  Gezählt:", format_cents(bericht["gezaehlt_cent"]), width))
        b.bold(True).line(_zeile("  Differenz:", format_cents(bericht["differenz_cent"]), width)).bold(False)

    if bericht["artikel"]:
        b.line("-" * width)
        b.line("Artikel:")
        for a in bericht["artikel"]:
            b.line(_zeile(f'  {a["menge"]} x {a["bezeichnung"]}', format_cents(a["betrag_cent"]), width))

    b.feed(1).align("center").line("* * *")
    b.cut(mode=cfg.get("schnitt.modus", "partial"), feed_lines=int(cfg.get("schnitt.vorschub_zeilen", "3")))
    return b.build()


def list_usb_devices() -> dict:
    """Listet angeschlossene USB-Geräte für die Drucker-Einrichtung auf.

    Liefert Hersteller-/Produkt-ID (als 0x-Hex, direkt in die Einstellungen
    übernehmbar) und - soweit lesbar - Klartextnamen. Ist pyusb nicht
    installiert, wird das gemeldet, ohne dass ein Fehler auftritt.
    """
    try:
        import usb.core
        import usb.util
    except Exception:  # pyusb nicht installiert
        return {"pyusb_installiert": False, "geraete": []}

    geraete: list[dict] = []
    try:
        for dev in usb.core.find(find_all=True):
            def _str(index: int) -> str:
                try:
                    return usb.util.get_string(dev, index) or ""
                except Exception:
                    return ""
            hersteller = _str(dev.iManufacturer) if dev.iManufacturer else ""
            produkt = _str(dev.iProduct) if dev.iProduct else ""
            beschreibung = (f"{hersteller} {produkt}").strip() or f"{dev.idVendor:04x}:{dev.idProduct:04x}"
            geraete.append({
                "vendor_id": f"0x{dev.idVendor:04x}",
                "product_id": f"0x{dev.idProduct:04x}",
                "hersteller": hersteller,
                "produkt": produkt,
                "beschreibung": beschreibung,
            })
    except Exception as exc:  # z. B. fehlende Berechtigungen
        return {"pyusb_installiert": True, "geraete": [], "hinweis": f"USB-Suche fehlgeschlagen: {exc}"}
    return {"pyusb_installiert": True, "geraete": geraete}
