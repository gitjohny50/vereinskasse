"""USB-Druckeranbindung über pyusb.

Sendet rohe ESC/POS-Bytes an den Bulk-OUT-Endpunkt des Druckers. Hersteller-
und Produkt-ID sowie der Endpunkt müssen am echten NetumScan NS-8360L per
``lsusb`` ermittelt und in den Systemeinstellungen hinterlegt werden
(Lastenheft 4.2, 28.2). pyusb wird bewusst erst zur Laufzeit importiert, damit
das Modul auch ohne installierte USB-Bibliothek geladen werden kann.
"""
from __future__ import annotations
from time import sleep

from .printer_base import PrinterAdapter, PrintResult, PrinterStatus

USB_WAKEUP_BYTES = b"\x1b\x40\x1b\x64\x02"
USB_WAKEUP_DELAY_SECONDS = 0.35
USB_CHUNK_DELAY_SECONDS = 0.02
USB_FINISH_DELAY_SECONDS = 0.8
USB_WRITE_CHUNK_SIZE = 256


class UsbPrinter(PrinterAdapter):
    name = "usb"

    def __init__(self, vendor_id: int, product_id: int, out_endpoint: int = 0x01, timeout_ms: int = 5000):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.out_endpoint = out_endpoint
        self.timeout_ms = timeout_ms

    def _open(self):
        import usb.core  # lazy import
        import usb.util  # noqa: F401

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
        # Konfiguration setzen; ist sie schon aktiv, ignorieren wir den Fehler.
        try:
            dev.set_configuration()
        except Exception:  # noqa: BLE001
            pass
        return dev

    def send(self, payload: bytes) -> PrintResult:
        import usb.util
        dev = None
        try:
            dev = self._open()
            dev.write(self.out_endpoint, USB_WAKEUP_BYTES, timeout=self.timeout_ms)
            sleep(USB_WAKEUP_DELAY_SECONDS)
            for start in range(0, len(payload), USB_WRITE_CHUNK_SIZE):
                chunk = payload[start : start + USB_WRITE_CHUNK_SIZE]
                dev.write(self.out_endpoint, chunk, timeout=self.timeout_ms)
                sleep(USB_CHUNK_DELAY_SECONDS)
            sleep(USB_FINISH_DELAY_SECONDS)
            return PrintResult(ok=True, detail="USB", bytes_sent=len(payload))
        except Exception as exc:  # noqa: BLE001 - jede USB-Störung sauber melden
            return PrintResult(ok=False, detail=f"USB-Fehler: {exc}", bytes_sent=0)
        finally:
            # Schnittstelle nach JEDEM Druck wieder freigeben und Kernel-Treiber
            # zurückgeben - sonst ist das Gerät beim nächsten Druck "busy" (Errno 16).
            if dev is not None:
                try:
                    usb.util.dispose_resources(dev)
                except Exception:  # noqa: BLE001
                    pass

    def status(self) -> PrinterStatus:
        import usb.util
        dev = None
        try:
            dev = self._open()
            return PrinterStatus(reachable=True, known=False, detail="USB-Gerät gefunden (Detailstatus unbekannt)")
        except Exception as exc:  # noqa: BLE001
            return PrinterStatus(reachable=False, known=True, detail=f"USB nicht erreichbar: {exc}")
        finally:
            if dev is not None:
                try:
                    usb.util.dispose_resources(dev)
                except Exception:  # noqa: BLE001
                    pass
