from app.hardware.escpos import EscposBuilder


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
