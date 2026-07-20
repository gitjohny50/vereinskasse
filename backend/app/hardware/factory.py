"""Baut aus den Systemeinstellungen den passenden Drucker-Adapter.

Alle Hardware-Parameter sind über die Oberfläche änderbar (Lastenheft 13.3,
14.6). Bis ein echtes Gerät konfiguriert ist, arbeitet der Prototyp mit dem
Mock-Drucker, sodass der gesamte Ablauf ohne Hardware testbar bleibt.
"""
from __future__ import annotations

from pathlib import Path

from .printer_base import PrinterAdapter
from .printer_mock import MockPrinter
from .printer_network import NetworkPrinter
from .printer_usb import UsbPrinter

# Standardwerte. Diese landen beim ersten Start in der DB (Systemeinstellung)
# und werden danach von dort gelesen.
DEFAULT_HW_SETTINGS: dict[str, str] = {
    # Drucker
    "drucker.transport": "mock",          # mock | network | usb
    "drucker.netzwerk.host": "192.168.1.50",
    "drucker.netzwerk.port": "9100",
    "drucker.usb.vendor_id": "0x0483",    # PLATZHALTER - am Gerät per lsusb prüfen
    "drucker.usb.product_id": "0x5743",   # PLATZHALTER - am Gerät per lsusb prüfen
    "drucker.usb.endpoint": "0x01",
    "drucker.codepage_id": "19",          # CP858 (Euro/Umlaute) - am Gerät prüfen
    "drucker.encoding": "cp858",
    "bon.breite_zeichen": "42",           # 80mm-Papier: meist 42-48 Zeichen
    "bon.logo.aktiv": "0",
    "bon.logo.breite_px": "0",
    "bon.logo.hoehe_px": "0",
    "bon.logo.raster_b64": "",
    "diagnose.testseite.qr_url": "https://vereinskasse.local/test",
    # Schnitt (Lastenheft 14.6)
    "schnitt.modus": "partial",           # partial | full | none
    "schnitt.vorschub_zeilen": "3",
    "artikelticket.vorschub_zeilen": "0",
    # Kassenschublade (Lastenheft 13.3)
    "schublade.aktiv": "1",
    "schublade.pin": "0",                 # 0 = Pin 2, 1 = Pin 5
    "schublade.puls_ms": "100",
    "schublade.pause_ms": "100",

    # Verkaufsdruck: 1 = Beleg (Bon) automatisch bei jedem Verkauf drucken,
    # 0 = nur die Artikeltickets drucken; der Beleg kommt nur auf Knopfdruck.
    "verkauf.beleg_autodruck": "0",
}


def _to_int(value: str) -> int:
    value = value.strip()
    return int(value, 16) if value.lower().startswith("0x") else int(value)


def build_printer(cfg: dict[str, str], mock_log_path: Path | None = None) -> PrinterAdapter:
    transport = cfg.get("drucker.transport", "mock")
    if transport == "network":
        return NetworkPrinter(
            host=cfg["drucker.netzwerk.host"],
            port=_to_int(cfg.get("drucker.netzwerk.port", "9100")),
        )
    if transport == "usb":
        return UsbPrinter(
            vendor_id=_to_int(cfg["drucker.usb.vendor_id"]),
            product_id=_to_int(cfg["drucker.usb.product_id"]),
            out_endpoint=_to_int(cfg.get("drucker.usb.endpoint", "0x01")),
        )
    return MockPrinter(log_path=mock_log_path)
