"""End-to-End-Tests der Diagnose-Endpunkte gegen eine temporäre DB.

Der Standard-Transport ist 'mock', sodass kein Drucker nötig ist.
"""


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


def test_settings_roundtrip(client):
    r = client.get("/api/einstellungen")
    assert r.status_code == 200
    keys = {row["schluessel"] for row in r.json()}
    assert "drucker.transport" in keys

    r2 = client.put("/api/einstellungen/schnitt.modus", json={"wert": "full"})
    assert r2.status_code == 200
    assert r2.json()["wert"] == "full"

    r3 = client.put("/api/einstellungen/unbekannt.key", json={"wert": "x"})
    assert r3.status_code == 404
