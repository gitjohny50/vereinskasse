import sys
import types

from app.hardware import printer_usb
from app.hardware.printer_usb import USB_WAKEUP_BYTES, UsbPrinter


class FakeUsbDevice:
    def __init__(self):
        self.writes = []

    def write(self, endpoint, payload, timeout):
        self.writes.append((endpoint, bytes(payload), timeout))
        return len(payload)


def test_usb_send_wakes_printer_before_payload(monkeypatch):
    dev = FakeUsbDevice()
    printer = UsbPrinter(vendor_id=0x1234, product_id=0x5678, out_endpoint=0x02, timeout_ms=123)
    usb_module = types.ModuleType("usb")
    usb_util_module = types.ModuleType("usb.util")
    usb_util_module.dispose_resources = lambda _dev: None
    usb_module.util = usb_util_module

    monkeypatch.setattr(printer, "_open", lambda: dev)
    monkeypatch.setattr(printer_usb, "sleep", lambda _seconds: None)
    monkeypatch.setitem(sys.modules, "usb", usb_module)
    monkeypatch.setitem(sys.modules, "usb.util", usb_util_module)

    result = printer.send(b"abcdef")

    assert result.ok is True
    assert result.bytes_sent == 6
    assert dev.writes == [
        (0x02, USB_WAKEUP_BYTES, 123),
        (0x02, b"abcdef", 123),
    ]


def test_usb_send_chunks_payload_after_wakeup(monkeypatch):
    dev = FakeUsbDevice()
    printer = UsbPrinter(vendor_id=0x1234, product_id=0x5678)
    payload = b"x" * (printer_usb.USB_WRITE_CHUNK_SIZE + 1)
    usb_module = types.ModuleType("usb")
    usb_util_module = types.ModuleType("usb.util")
    usb_util_module.dispose_resources = lambda _dev: None
    usb_module.util = usb_util_module

    monkeypatch.setattr(printer, "_open", lambda: dev)
    monkeypatch.setattr(printer_usb, "sleep", lambda _seconds: None)
    monkeypatch.setitem(sys.modules, "usb", usb_module)
    monkeypatch.setitem(sys.modules, "usb.util", usb_util_module)

    result = printer.send(payload)

    assert result.ok is True
    assert result.bytes_sent == len(payload)
    assert [write[1] for write in dev.writes] == [
        USB_WAKEUP_BYTES,
        b"x" * printer_usb.USB_WRITE_CHUNK_SIZE,
        b"x",
    ]
