"""End-to-End-Tests der Diagnose-Endpunkte gegen eine temporäre DB.

Der Standard-Transport ist 'mock', sodass kein Drucker nötig ist.
"""

from types import SimpleNamespace


def test_health_reports_ok_and_integrity(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db_integrity"] == "ok"


def test_printer_status_mock_reachable(client):
    r = client.get("/api/diagnose/drucker/status")
    assert r.status_code == 200
    assert r.json()["reachable"] is True


def test_testseite_creates_print_job(client):
    r = client.post("/api/diagnose/drucker/testseite")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["auftrag_id"] is not None
    assert body["drucker"] == "mock"


def test_cut_test_multiple(client):
    r = client.post("/api/diagnose/drucker/schnitt-test", json={"anzahl": 5})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_drawer_open_logged(client):
    r = client.post("/api/diagnose/schublade/oeffnen", json={"grund": "Abnahmetest"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_uhr_stellen_schreibt_rtc_mit_hwclock(client, monkeypatch):
    commands = []

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        if cmd[:3] == ["timedatectl", "show", "-p"]:
            return SimpleNamespace(returncode=0, stdout="no\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.routers.diagnostics._hwclock_command",
        lambda: ["sudo", "-n", "/usr/sbin/hwclock", "--systohc"],
    )
    monkeypatch.setattr("app.routers.diagnostics.subprocess.run", fake_run)

    r = client.post("/api/diagnose/uhr", json={"datum": "2026-08-26", "stunde": 14, "minute": 30})
    assert r.status_code == 200
    assert "RTC" in r.json()["detail"]
    assert ["sudo", "-n", "/usr/sbin/hwclock", "--systohc"] in commands


def test_settings_roundtrip(client):
    r = client.get("/api/einstellungen")
    assert r.status_code == 200
    keys = {row["schluessel"] for row in r.json()}
    assert "drucker.transport" in keys
    assert "artikelticket.vorschub_zeilen" in keys

    r2 = client.put("/api/einstellungen/schnitt.modus", json={"wert": "full"})
    assert r2.status_code == 200
    assert r2.json()["wert"] == "full"

    r3 = client.put("/api/einstellungen/unbekannt.key", json={"wert": "x"})
    assert r3.status_code == 404


def test_bon_logo_roundtrip(client):
    r = client.get("/api/einstellungen/bon-logo/status")
    assert r.status_code == 200
    assert r.json()["aktiv"] is False

    r2 = client.put("/api/einstellungen/bon-logo/datei", json={
        "breite_px": 8,
        "hoehe_px": 1,
        "raster_b64": "gA==",
    })
    assert r2.status_code == 200
    assert r2.json()["aktiv"] is True
    assert r2.json()["breite_px"] == 8

    r3 = client.delete("/api/einstellungen/bon-logo/datei")
    assert r3.status_code == 200
    assert r3.json()["aktiv"] is False


def test_usb_geraete_liste(client):
    """USB-Geräteliste für die Drucker-Einrichtung: liefert strukturierte Antwort,
    auch wenn pyusb/libusb in der Umgebung fehlt (dann leere Liste, kein Fehler)."""
    r = client.get("/api/diagnose/drucker/usb-geraete")
    assert r.status_code == 200
    body = r.json()
    assert "pyusb_installiert" in body
    assert isinstance(body["geraete"], list)


def test_usb_geraete_nur_service(bediener_client):
    assert bediener_client.get("/api/diagnose/drucker/usb-geraete").status_code == 403
