"""Reiner ESC/POS-Befehlsbaukasten.

Diese Klasse erzeugt nur die rohen Bytefolgen. Sie kennt keinen Transport
(USB/Ethernet) und keine Datenbank. Dadurch lässt sie sich isoliert testen und
von jedem Adapter verwenden.

WICHTIG (Lastenheft 4.2, 14.6): Die konkreten Schnitt- und Schubladenbefehle
sowie die Codepage müssen am echten NetumScan NS-8360L verifiziert werden. Alle
kritischen Werte sind daher Parameter, keine festverdrahteten Konstanten.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ESC = 0x1B
GS = 0x1D
LF = 0x0A


@dataclass
class EscposBuilder:
    """Sammelt Bytes für einen Druckauftrag.

    Args:
        codepage_id: Wert für ``ESC t n`` (Zeichentabelle des Druckers).
            Für Euro-Zeichen und Umlaute ist bei Epson-kompatiblen Geräten
            häufig CP858 passend (oft n=19). Muss am Gerät geprüft werden.
        encoding: Python-Codec passend zur codepage_id (Standard: cp858).
    """

    codepage_id: int = 19
    encoding: str = "cp858"
    _buffer: bytearray = field(default_factory=bytearray)

    # -- Grundfunktionen -------------------------------------------------
    def init(self) -> "EscposBuilder":
        """ESC @ - Drucker zurücksetzen und Zeichentabelle wählen."""
        self._buffer += bytes([ESC, 0x40])
        self._buffer += bytes([ESC, 0x74, self.codepage_id])  # ESC t n
        return self

    def text(self, value: str) -> "EscposBuilder":
        self._buffer += value.encode(self.encoding, errors="replace")
        return self

    def line(self, value: str = "") -> "EscposBuilder":
        return self.text(value).feed(1)

    def feed(self, lines: int = 1) -> "EscposBuilder":
        """ESC d n - n Zeilen vorschieben."""
        self._buffer += bytes([ESC, 0x64, max(0, min(lines, 255))])
        return self

    # -- Ausrichtung & Stil ---------------------------------------------
    def align(self, mode: str) -> "EscposBuilder":
        """ESC a n - 'left' | 'center' | 'right'."""
        code = {"left": 0, "center": 1, "right": 2}[mode]
        self._buffer += bytes([ESC, 0x61, code])
        return self

    def bold(self, on: bool) -> "EscposBuilder":
        """ESC E n."""
        self._buffer += bytes([ESC, 0x45, 1 if on else 0])
        return self

    def underline(self, on: bool) -> "EscposBuilder":
        """ESC - n."""
        self._buffer += bytes([ESC, 0x2D, 1 if on else 0])
        return self

    def size(self, width: int = 1, height: int = 1) -> "EscposBuilder":
        """GS ! n - Zeichengröße (1..8 fache Breite/Höhe)."""
        w = max(1, min(width, 8)) - 1
        h = max(1, min(height, 8)) - 1
        self._buffer += bytes([GS, 0x21, (w << 4) | h])
        return self

    # -- QR-Code (GS ( k) ------------------------------------------------
    def qr(self, data: str, module_size: int = 6, ec_level: int = 49) -> "EscposBuilder":
        """Druckt einen QR-Code (Modell 2).

        ec_level: 48=L, 49=M, 50=Q, 51=H.
        """
        payload = data.encode("utf-8")
        # Modell 2 wählen
        self._buffer += bytes([GS, 0x28, 0x6B, 0x04, 0x00, 0x31, 0x41, 0x32, 0x00])
        # Modulgröße
        self._buffer += bytes([GS, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x43, max(1, min(module_size, 16))])
        # Fehlerkorrektur
        self._buffer += bytes([GS, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x45, ec_level])
        # Daten speichern
        length = len(payload) + 3
        pl, ph = length & 0xFF, (length >> 8) & 0xFF
        self._buffer += bytes([GS, 0x28, 0x6B, pl, ph, 0x31, 0x50, 0x30]) + payload
        # Drucken
        self._buffer += bytes([GS, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x51, 0x30])
        return self

    # -- Rasterbild -----------------------------------------------------
    def raster_image(self, width_px: int, height_px: int, data: bytes) -> "EscposBuilder":
        """GS v 0 - monochromes Rasterbild drucken.

        ``data`` enthält zeilenweise 1 Bit pro Pixel, MSB zuerst. Die Breite
        muss durch 8 teilbar sein.
        """
        if width_px <= 0 or height_px <= 0 or width_px % 8 != 0:
            raise ValueError("Rasterbild braucht positive Breite durch 8 und positive Hoehe")
        width_bytes = width_px // 8
        expected = width_bytes * height_px
        if len(data) != expected:
            raise ValueError(f"Rasterbild hat {len(data)} Bytes, erwartet {expected}")
        self._buffer += bytes([
            GS, 0x76, 0x30, 0x00,
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            height_px & 0xFF, (height_px >> 8) & 0xFF,
        ])
        self._buffer += data
        return self

    # -- Schnitt ---------------------------------------------------------
    def cut(self, mode: str = "partial", feed_lines: int = 3) -> "EscposBuilder":
        """Schneidebefehl (Lastenheft 14.6).

        mode: 'partial' (Teilschnitt), 'full' (Vollschnitt), 'none' (kein Schnitt).
        feed_lines: Papiertransport vor dem Schnitt, damit kein Text im Messer landet.
        """
        if mode == "none":
            return self
        if feed_lines:
            self.feed(feed_lines)
        if mode == "full":
            # GS V 65 n : Vorschub + Vollschnitt
            self._buffer += bytes([GS, 0x56, 65, 0])
        else:
            # GS V 66 n : Vorschub + Teilschnitt (Standard für NetumScan geplant)
            self._buffer += bytes([GS, 0x56, 66, 0])
        return self

    # -- Kassenschublade -------------------------------------------------
    def kick_drawer(self, pin: int = 0, on_ms: int = 100, off_ms: int = 100) -> "EscposBuilder":
        """ESC p m t1 t2 - Impuls für die am Drucker angeschlossene Schublade.

        pin: 0 = Pin 2 (üblich), 1 = Pin 5.
        on_ms/off_ms: Pulsdauer/Pausendauer. Der Befehl rechnet in 2-ms-Einheiten.
        (Lastenheft 13.1: Ansteuerung über den Bondrucker, nicht über GPIO.)
        """
        m = 0 if pin == 0 else 1
        t1 = max(0, min(on_ms // 2, 255))
        t2 = max(0, min(off_ms // 2, 255))
        self._buffer += bytes([ESC, 0x70, m, t1, t2])
        return self

    # -- Ausgabe ---------------------------------------------------------
    def build(self) -> bytes:
        return bytes(self._buffer)
