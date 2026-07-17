"""Phase 4: Druckwarteschlange - Einreihung, Wiederholung, Max-Versuche,
manuelle Wiederholung, Abbruch, Statusanzeige."""
import fastapi
import pytest

from app import print_queue
from app.database import SessionLocal
from app.hardware.printer_base import PrinterAdapter, PrinterStatus, PrintResult


class FailPrinter(PrinterAdapter):
    name = "FehlDrucker"

    def send(self, payload: bytes) -> PrintResult:
        return PrintResult(ok=False, detail="Papier leer")

    def status(self) -> PrinterStatus:
        return PrinterStatus(reachable=False, known=True)


class OkPrinter(PrinterAdapter):
    name = "OkDrucker"

    def send(self, payload: bytes) -> PrintResult:
        return PrintResult(ok=True, detail="ok", bytes_sent=len(payload))

    def status(self) -> PrinterStatus:
        return PrinterStatus(reachable=True, known=True)


def _kasse(client):
    pid = client.get("/api/kassenprofile").json()[0]["id"]
    arts = {a["name"]: a for a in client.get("/api/artikel", params={"kassenprofil_id": pid}).json()}
    zm = {z["name"]: z for z in client.get("/api/zahlungsmethoden", params={"kassenprofil_id": pid}).json()}
    return pid, arts, zm


def test_verkauf_druckt_tickets_ohne_beleg(client):
    """Standard (verkauf.beleg_autodruck=0): pro Artikel ein Ticket, KEIN
    automatischer Beleg; bei Barzahlung wird die Schublade separat geöffnet."""
    pid, arts, zm = _kasse(client)
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 1000})
    typen = {j["dokumenttyp"] for j in client.get("/api/druckwarteschlange").json()}
    assert "Artikelticket" in typen
    assert "Bon" not in typen
    assert "Schublade" in typen
    st = client.get("/api/druckwarteschlange/status").json()
    assert st["offen"] == 0


def test_beleg_autodruck_an_druckt_bon(client):
    """Bei verkauf.beleg_autodruck=1 kommt der Bon automatisch (Schublade im Bon)."""
    pid, arts, zm = _kasse(client)
    client.put("/api/einstellungen/verkauf.beleg_autodruck", json={"wert": "1"})
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 1000})
    typen = {j["dokumenttyp"] for j in client.get("/api/druckwarteschlange").json()}
    assert {"Bon", "Artikelticket"} <= typen
    assert "Schublade" not in typen


def test_beleg_auf_knopfdruck(client):
    """Beleg lässt sich für einen Verkauf gezielt anfordern (dokumenttyp 'Beleg')."""
    pid, arts, zm = _kasse(client)
    v = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 500}).json()
    r = client.post(f"/api/verkauf/{v['id']}/beleg")
    assert r.status_code == 200 and r.json()["ok"] is True
    typen = {j["dokumenttyp"] for j in client.get("/api/druckwarteschlange").json()}
    assert "Beleg" in typen


def test_wiederholung_bis_max_dann_fehlgeschlagen():
    with SessionLocal() as s:
        job = print_queue.enqueue(s, dokumenttyp="Bon", payload=b"\x1b@test", max_versuche=3)
        assert job.status == "offen"
        fail = FailPrinter()
        print_queue._versuch(s, job, fail)
        assert job.status == "offen" and job.versuche == 1
        print_queue._versuch(s, job, fail)
        assert job.status == "offen" and job.versuche == 2
        print_queue._versuch(s, job, fail)
        assert job.status == "fehlgeschlagen" and job.versuche == 3
        assert "Papier" in job.letzte_fehlermeldung


def test_manuelle_wiederholung_stellt_zu():
    with SessionLocal() as s:
        job = print_queue.enqueue(s, dokumenttyp="Bon", payload=b"x", max_versuche=1)
        print_queue._versuch(s, job, FailPrinter())
        assert job.status == "fehlgeschlagen"
        wieder = print_queue.wiederhole(s, job.id, benutzer="Test", printer=OkPrinter())
        assert wieder.status == "erfolgreich" and wieder.letzte_fehlermeldung == ""


def test_verarbeite_offene_wiederholt():
    with SessionLocal() as s:
        job = print_queue.enqueue(s, dokumenttyp="Bon", payload=b"a", max_versuche=5)
        print_queue._versuch(s, job, FailPrinter())     # offen (1/5)
        res = print_queue.verarbeite_offene(s, printer=OkPrinter())
        assert res["verarbeitet"] == 1 and res["erfolg"] == 1
        s.refresh(job)
        assert job.status == "erfolgreich"


def test_abbrechen_und_nicht_erfolgreiche():
    with SessionLocal() as s:
        job = print_queue.enqueue(s, dokumenttyp="Bon", payload=b"a", max_versuche=1)
        print_queue._versuch(s, job, FailPrinter())
        ab = print_queue.abbrechen(s, job.id, benutzer="Test")
        assert ab.status == "abgebrochen"
        # Erfolgreiche Aufträge lassen sich nicht abbrechen
        ok_job = print_queue.enqueue(s, dokumenttyp="Bon", payload=b"b")
        print_queue._versuch(s, ok_job, OkPrinter())
        with pytest.raises(fastapi.HTTPException):
            print_queue.abbrechen(s, ok_job.id, benutzer="Test")


def test_api_filter_und_verarbeiten(client):
    pid, arts, zm = _kasse(client)
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 500})
    # Alles gedruckt -> nichts offen
    assert client.get("/api/druckwarteschlange", params={"status": "offen"}).json() == []
    res = client.post("/api/druckwarteschlange/verarbeiten").json()
    assert res["verarbeitet"] == 0


def test_abbrechen_nur_admin(bediener_client):
    with SessionLocal() as s:
        job = print_queue.enqueue(s, dokumenttyp="Bon", payload=b"a", max_versuche=1)
        jid = job.id
    assert bediener_client.post(f"/api/druckwarteschlange/{jid}/abbrechen").status_code == 403
