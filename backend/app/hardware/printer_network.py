"""Ethernet-Druckeranbindung über rohes ESC/POS via TCP (Standardport 9100).

Bevorzugter Transport laut Lastenheft 28.2. Sendet die vom EscposBuilder
erzeugten Bytes direkt an den Drucker. Keine externe Bibliothek nötig.
"""
from __future__ import annotations

import socket

from .printer_base import PrinterAdapter, PrintResult, PrinterStatus


class NetworkPrinter(PrinterAdapter):
    name = "network"

    def __init__(self, host: str, port: int = 9100, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, payload: bytes) -> PrintResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(payload)
            return PrintResult(ok=True, detail=f"{self.host}:{self.port}", bytes_sent=len(payload))
        except OSError as exc:
            return PrintResult(ok=False, detail=f"Netzwerkfehler: {exc}", bytes_sent=0)

    def status(self) -> PrinterStatus:
        """Erreichbarkeit per TCP-Verbindung prüfen.

        Papier-/Abdeckungsstatus über Netzwerk ist geräteabhängig und wird für
        Phase 1 als 'unbekannt' gemeldet, bis am echten Gerät geklärt.
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout):
                return PrinterStatus(reachable=True, known=False, detail="erreichbar (Detailstatus unbekannt)")
        except OSError as exc:
            return PrinterStatus(reachable=False, known=True, detail=f"nicht erreichbar: {exc}")
