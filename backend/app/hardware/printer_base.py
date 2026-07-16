"""Abstrakte Druckerschnittstelle.

Alle Drucker (Mock, USB, Ethernet) implementieren dieselbe Schnittstelle.
Dadurch bleibt die Fachlogik hardwareunabhängig (Lastenheft 24.4, 32.7/32.8:
Hardwarezugriffe hinter klaren, austauschbaren Adaptern kapseln).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PrintResult:
    ok: bool
    detail: str = ""
    bytes_sent: int = 0


@dataclass
class PrinterStatus:
    """Ergebnis einer Statusabfrage.

    'unknown' ist ein eigener Zustand: liefert der Drucker keine verlässliche
    Rückmeldung, muss die Oberfläche zwischen 'bestätigt' und 'unbekannt'
    unterscheiden (Lastenheft 14.11).
    """

    reachable: bool
    known: bool  # True = Status verlässlich ermittelt, False = unbekannt
    paper_ok: bool | None = None
    cover_closed: bool | None = None
    detail: str = ""


class PrinterAdapter(ABC):
    """Gemeinsame Schnittstelle für alle Druckeranbindungen."""

    name: str = "unbekannt"

    @abstractmethod
    def send(self, payload: bytes) -> PrintResult:
        """Sendet rohe ESC/POS-Bytes an den Drucker."""

    @abstractmethod
    def status(self) -> PrinterStatus:
        """Fragt den Druckerstatus ab (soweit unterstützt)."""

    def close(self) -> None:  # pragma: no cover - optional
        """Verbindung freigeben (falls nötig)."""
        return None
