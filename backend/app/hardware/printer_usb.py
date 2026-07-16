"""USB-Druckeranbindung über pyusb.

Sendet rohe ESC/POS-Bytes an den Bulk-OUT-Endpunkt des Druckers. Hersteller-
und Produkt-ID sowie der Endpunkt müssen am echten NetumScan NS-8360L per
``lsusb`` ermittelt und in den Systemeinstellungen hinterlegt werden
(Lastenheft 4.2, 28.2). pyusb wird bewusst erst zur Laufzeit importiert, damit
das Modul auch ohne installierte USB-Bibliothek geladen werden kann.
"""
from __future__ import annotations

from .printer_base import PrinterAdapter, PrintResult, PrinterStatus


class UsbPrinter(PrinterAdapter):
    name = "usb"

    def __init__(self, vendor_id: int, product_id: int, out_endpoint: int = 0x01, timeout_ms: int = 5000):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.out_endpoint = out_endpoint
        self.timeout_ms = timeout_ms

    def _open(self):
        import usb.core  # lazy import
        import usb.util

        dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if dev is None:
            raise OSError(
                f"USB-Drucker {self.vendor_id:#06x}:{self.product_id:#06x} nicht gefunden"
            )
        # Kernel-Treiber lösen, falls belegt (Linux).
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except (NotImplementedError, Exception):  # noqa: BLE001 - plattformabhängig
            pass
        dev.set_configuration()
        return dev

    def send(self, payload: bytes) -> PrintResult:
        try:
            dev = self._open()
            dev.write(self.out_endpoint, payload, timeout=self.timeout_ms)
            return PrintResult(ok=True, detail="USB", bytes_sent=len(payload))
        except Exception as exc:  # noqa: BLE001 - jede USB-Störung sauber melden
            return PrintResult(ok=False, detail=f"USB-Fehler: {exc}", bytes_sent=0)

    def status(self) -> PrinterStatus:
        try:
            self._open()
            return PrinterStatus(reachable=True, known=False, detail="USB-Gerät gefunden (Detailstatus unbekannt)")
        except Exception as exc:  # noqa: BLE001
            return PrinterStatus(reachable=False, known=True, detail=f"USB nicht erreichbar: {exc}")
