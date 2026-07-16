"""Mock-Drucker für Entwicklung und Tests.

Ohne echte Hardware muss der gesamte Druck- und Schnittablauf trotzdem prüfbar
sein. Dieser Adapter schreibt jeden Auftrag in eine Logdatei und hält die
zuletzt gesendeten Bytes vor, damit Tests Schnitt- und Schubladenbefehle
verifizieren können.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .printer_base import PrinterAdapter, PrintResult, PrinterStatus

# Bekannte Steuerbefehle für eine lesbare Protokollierung.
_MARKERS = {
    b"\x1d\x56\x42": "[TEILSCHNITT]",
    b"\x1d\x56\x41": "[VOLLSCHNITT]",
    b"\x1b\x70": "[SCHUBLADE-IMPULS]",
    b"\x1d\x28\x6b": "[QR-CODE]",
}


class MockPrinter(PrinterAdapter):
    name = "mock"

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path
        self.last_payload: bytes = b""
        self.sent_count = 0

    def send(self, payload: bytes) -> PrintResult:
        self.last_payload = payload
        self.sent_count += 1
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"\n===== Druckauftrag {datetime.now().isoformat()} =====\n")
                fh.write(self.render(payload))
                fh.write("\n")
        return PrintResult(ok=True, detail="an Mock-Drucker gesendet", bytes_sent=len(payload))

    def status(self) -> PrinterStatus:
        # Der Mock ist immer erreichbar und meldet einen bekannten, guten Zustand.
        return PrinterStatus(
            reachable=True, known=True, paper_ok=True, cover_closed=True, detail="Mock bereit"
        )

    @staticmethod
    def render(payload: bytes) -> str:
        """Erzeugt eine lesbare Textrepräsentation des Auftrags.

        Steuerbefehle und ihre Operanden werden korrekt übersprungen, die
        wichtigen Ereignisse (Schnitt, Schublade, QR) als Marker eingefügt.
        """
        out: list[str] = []
        text_run = bytearray()
        i, n = 0, len(payload)

        def flush():
            if text_run:
                out.append(text_run.decode("cp858", errors="replace"))
                text_run.clear()

        while i < n:
            b = payload[i]
            if b == 0x0A:  # LF
                flush()
                out.append("\n")
                i += 1
            elif b == 0x1B:  # ESC ...
                cmd = payload[i + 1] if i + 1 < n else 0
                if cmd == 0x64:  # ESC d n -> Vorschub
                    flush()
                    out.append("\n")
                    i += 3
                elif cmd == 0x70:  # ESC p m t1 t2 -> Schublade
                    flush()
                    out.append("[SCHUBLADE-IMPULS]")
                    i += 5
                elif cmd == 0x40:  # ESC @
                    i += 2
                else:  # ESC t/a/E/- n (jeweils 1 Operand)
                    i += 3
            elif b == 0x1D:  # GS ...
                cmd = payload[i + 1] if i + 1 < n else 0
                if cmd == 0x56:  # GS V ... (Schnitt)
                    m = payload[i + 2] if i + 2 < n else 0
                    flush()
                    out.append("[VOLLSCHNITT]" if m in (65, 0) else "[TEILSCHNITT]")
                    i += 4 if m in (65, 66) else 3
                elif cmd == 0x21:  # GS ! n
                    i += 3
                elif cmd == 0x28:  # GS ( k ... (QR)
                    pl = payload[i + 3] if i + 3 < n else 0
                    ph = payload[i + 4] if i + 4 < n else 0
                    block = 5 + pl + (ph << 8)
                    # QR-Block nur einmal als Marker ausgeben
                    if b"\x50\x30" in payload[i : i + block]:  # Datenblock
                        flush()
                        out.append("[QR-CODE]")
                    i += block
                else:
                    i += 2
            else:
                text_run.append(b)
                i += 1
        flush()
        return "".join(out)
