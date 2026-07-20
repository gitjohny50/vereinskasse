from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.hardware.service import build_receipt_bytes
from app.models import Verkauf


def _kasse(client):
    pid = client.get("/api/kassenprofile").json()[0]["id"]
    arts = {a["name"]: a for a in client.get("/api/artikel", params={"kassenprofil_id": pid}).json()}
    zm = {z["name"]: z for z in client.get("/api/zahlungsmethoden", params={"kassenprofil_id": pid}).json()}
    return pid, arts, zm


def test_verkaufs_auswertung_listet_zeit_und_artikel(client):
    pid, arts, zm = _kasse(client)
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid,
        "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 2}],
        "zahlungsmethode_id": zm["Karte"]["id"],
    })

    r = client.get("/api/auswertung/verkauf", params={"kassenprofil_id": pid, "tage": 1})

    assert r.status_code == 200
    body = r.json()
    assert body["anzahl_verkaeufe"] == 1
    assert body["buckets"]
    assert body["top_artikel"][0]["bezeichnung"] == "Cola"
    assert body["top_artikel"][0]["menge"] == 2
    assert body["verkaeufe"][0]["items"][0]["bezeichnung"] == "Cola"


def test_verkaufs_auswertung_pfand_schalter(client):
    pid, arts, zm = _kasse(client)
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid,
        "artikel": [{"artikel_id": arts["Wasser"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Karte"]["id"],
    })

    ohne = client.get("/api/auswertung/verkauf", params={"kassenprofil_id": pid, "tage": 1, "pfand": False}).json()
    mit = client.get("/api/auswertung/verkauf", params={"kassenprofil_id": pid, "tage": 1, "pfand": True}).json()

    assert ohne["gesamt_cent"] == 200
    assert {i["bezeichnung"] for i in ohne["verkaeufe"][0]["items"]} == {"Wasser"}
    assert mit["gesamt_cent"] == 400
    assert {i["bezeichnung"] for i in mit["verkaeufe"][0]["items"]} == {"Wasser", "Pfand: Glaspfand"}


def test_zeitreihe_liefert_lueckenlose_buckets_und_segmente(client):
    pid, arts, zm = _kasse(client)
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid,
        "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 2}],
        "zahlungsmethode_id": zm["Karte"]["id"],
    })
    heute = datetime.now().date()
    morgen = heute + timedelta(days=1)

    r = client.get("/api/auswertung/zeitreihe", params={
        "kassenprofil_id": pid,
        "von": f"{heute.isoformat()}T00:00:00",
        "bis": f"{morgen.isoformat()}T00:00:00",
        "granularitaet": "stunde",
        "metrik": "umsatz",
        "gruppierung": "artikel",
        "pfand_einbeziehen": False,
    })

    assert r.status_code == 200
    body = r.json()
    assert body["summe"]["anzahl"] == 1
    assert body["summe"]["umsatz_cent"] == 500
    assert len(body["buckets"]) == 24
    assert body["top_artikel"][0]["bezeichnung"] == "Cola"
    assert any(seg["name"] == "Cola" for bucket in body["buckets"] for seg in bucket["segmente"])


def test_auswertung_nur_admin_und_service(bediener_client):
    assert bediener_client.get("/api/auswertung/verkauf", params={"kassenprofil_id": 1}).status_code == 403


def test_beleg_interpretiert_sqlite_naive_utc_als_lokale_kassenzeit(monkeypatch):
    monkeypatch.setenv("VK_TIMEZONE", "Europe/Berlin")
    payload = build_receipt_bytes(
        {},
        bonkopf="Verein",
        bonfuss="",
        belegnummer="000001",
        zeitpunkt=datetime(2026, 7, 18, 10, 0),  # SQLite-naiv, fachlich UTC
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

    assert "18.07.2026 12:00".encode("cp858") in payload


def test_verkauf_api_gibt_utc_offset_fuer_sqlite_naive_zeit_zurueck(client):
    pid, arts, zm = _kasse(client)
    v = client.post("/api/verkauf", json={
        "kassenprofil_id": pid,
        "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Karte"]["id"],
    }).json()

    with SessionLocal() as session:
        verkauf = session.get(Verkauf, v["id"])
        verkauf.zeitpunkt = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc).replace(tzinfo=None)
        session.commit()

    detail = client.get(f"/api/verkauf/{v['id']}").json()
    assert detail["zeitpunkt"].endswith("+00:00") or detail["zeitpunkt"].endswith("Z")