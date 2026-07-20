import base64
from datetime import datetime, timezone

from app.hardware.escpos import EscposBuilder
from app.hardware.service import build_receipt_bytes, build_test_page, build_ticket_bytes


def test_init_contains_reset_and_codepage():
    payload = EscposBuilder(codepage_id=19).init().build()
    assert payload.startswith(b"\x1b\x40")       # ESC @
    assert b"\x1b\x74\x13" in payload            # ESC t 19


def test_partial_cut_with_feed():
    payload = EscposBuilder().init().cut(mode="partial", feed_lines=3).build()
    assert b"\x1b\x64\x03" in payload            # ESC d 3 (Vorschub)
    assert b"\x1d\x56\x42\x00" in payload        # GS V 66 0 (Teilschnitt)


def test_full_cut():
    payload = EscposBuilder().cut(mode="full", feed_lines=0).build()
    assert b"\x1d\x56\x41\x00" in payload        # GS V 65 0 (Vollschnitt)


def test_no_cut_emits_nothing():
    payload = EscposBuilder().cut(mode="none").build()
    assert payload == b""


def test_drawer_kick_pulse_units():
    # 100 ms -> 50 Einheiten (2 ms je Einheit)
    payload = EscposBuilder().kick_drawer(pin=0, on_ms=100, off_ms=100).build()
    assert payload == bytes([0x1B, 0x70, 0x00, 50, 50])


def test_drawer_kick_pin5():
    payload = EscposBuilder().kick_drawer(pin=1, on_ms=60, off_ms=120).build()
    assert payload == bytes([0x1B, 0x70, 0x01, 30, 60])


def test_umlaut_and_euro_encode_cp858():
    payload = EscposBuilder(encoding="cp858").text("\u00e4\u20ac").build()
    # cp858 kodiert diese Zeichen einbyteweise (kein Ersatz-'?')
    assert b"?" not in payload
    assert len(payload) == 2


def test_qr_has_store_and_print_blocks():
    payload = EscposBuilder().qr("hallo").build()
    assert b"\x1d\x28\x6b" in payload            # GS ( k
    assert payload.endswith(bytes([0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x51, 0x30]))


def test_ticket_uses_compact_event_layout_with_time_without_price():
    payload = build_ticket_bytes({"artikelticket.vorschub_zeilen": "0"}, "Wasser", "000030", kopf="Musikverein Leutenbach\nHocketse 20.07.2026 14:35")
    assert b"Musikverein Leutenbach" in payload
    assert b"Hocketse 20.07.2026 14:35" in payload
    assert b"\x1d\x21\x11Wasser" in payload
    assert b"EUR" not in payload
    assert b"Kasse 000030" not in payload
    assert b"-000030-" in payload
    assert b"Hocketse 20.07.2026 14:35  -000030-" in payload
    assert payload.index(b"Musikverein Leutenbach") < payload.index(b"Wasser") < payload.index(b"Hocketse 20.07.2026 14:35  -000030-")
    # Der Papierschnitt (b'\x1d\x56\x42\x00') ist jetzt erwünscht, daher wurde die Prüfung auf 'not in' entfernt.
    assert payload.endswith(b"\x1d\x56\x42\x00")


def test_raster_image_uses_gs_v_0_command():
    payload = EscposBuilder().raster_image(8, 1, b"\x80").build()
    assert payload == b"\x1dv0\x00\x01\x00\x01\x00\x80"


def test_receipt_prints_configured_logo_before_header():
    payload = build_receipt_bytes(
        {
            "bon.logo.aktiv": "1",
            "bon.logo.breite_px": "8",
            "bon.logo.hoehe_px": "1",
            "bon.logo.raster_b64": base64.b64encode(b"\x80").decode("ascii"),
        },
        bonkopf="Verein",
        bonfuss="",
        belegnummer="000001",
        zeitpunkt=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
        bediener="Test",
        positionen=[],
        waren_cent=0,
        pfand_cent=0,
        gesamt_cent=0,
        zahlung_name="Bar",
        gegeben_cent=0,
        rueckgeld_cent=0,
        schublade=False,
    )
    logo_pos = payload.index(b"\x1dv0\x00\x01\x00\x01\x00\x80")
    header_pos = payload.index("Verein".encode("cp858"))
    assert logo_pos < header_pos


def test_test_page_prints_configured_logo_and_qr():
    payload = build_test_page({
        "bon.logo.aktiv": "1",
        "bon.logo.breite_px": "8",
        "bon.logo.hoehe_px": "1",
        "bon.logo.raster_b64": base64.b64encode(b"\x80").decode("ascii"),
        "diagnose.testseite.qr_url": "https://example.test/kasse",
    })
    assert b"\x1dv0\x00\x01\x00\x01\x00\x80" in payload
    assert b"https://example.test/kasse" in payload


def test_test_page_omits_qr_when_url_empty():
    payload = build_test_page({"diagnose.testseite.qr_url": ""})
    assert b"\x1d\x28\x6b" not in payload
