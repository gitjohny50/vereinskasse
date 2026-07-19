def test_create_verein_profile_event_chain(client):
    v = client.post("/api/vereine", json={"name": "TSV Beispiel"}).json()
    p = client.post("/api/kassenprofile", json={"name": "Sommerfest", "verein_id": v["id"]}).json()
    e = client.post("/api/veranstaltungen", json={
        "kassenprofil_id": p["id"], "name": "Tag 1", "ort": "Festplatz", "pfand_aktiv": True,
    })
    assert e.status_code == 201
    assert e.json()["status"] == "geplant"


def test_event_status_transition(client):
    profil = client.get("/api/kassenprofile").json()[0]
    e = client.post("/api/veranstaltungen", json={"kassenprofil_id": profil["id"], "name": "Status-Test"}).json()
    r = client.put(f"/api/veranstaltungen/{e['id']}/status", params={"status": "aktiv"})
    assert r.status_code == 200
    assert r.json()["status"] == "aktiv"
    bad = client.put(f"/api/veranstaltungen/{e['id']}/status", params={"status": "quatsch"})
    assert bad.status_code == 422


def test_profile_requires_existing_verein(client):
    r = client.post("/api/kassenprofile", json={"name": "Waise", "verein_id": 99999})
    assert r.status_code == 422


def test_verein_und_profil_aendern_mit_pfand_schalter(client):
    v = client.post("/api/vereine", json={"name": "Alter Name"}).json()
    changed = client.put(f"/api/vereine/{v['id']}", json={"name": "Neuer Name", "kontakt": "info@example.test"}).json()
    assert changed["name"] == "Neuer Name"
    assert changed["kontakt"] == "info@example.test"

    p = client.post("/api/kassenprofile", json={"name": "Profil", "verein_id": v["id"], "pfand_aktiv": True}).json()
    assert p["pfand_aktiv"] is True
    changed_profile = client.put(f"/api/kassenprofile/{p['id']}", json={
        "name": "Profil neu", "verein_id": v["id"], "waehrung": "EUR", "pfand_aktiv": False,
    }).json()
    assert changed_profile["name"] == "Profil neu"
    assert changed_profile["pfand_aktiv"] is False
    profiles = client.get("/api/kassenprofile").json()
    assert next(row for row in profiles if row["id"] == p["id"])["pfand_aktiv"] is False


def test_kassenprofil_loeschen_deaktiviert(client):
    v = client.post("/api/vereine", json={"name": "Löschverein"}).json()
    p = client.post("/api/kassenprofile", json={"name": "Weg damit", "verein_id": v["id"]}).json()
    deleted = client.delete(f"/api/kassenprofile/{p['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["aktiv"] is False
    assert all(row["id"] != p["id"] for row in client.get("/api/kassenprofile").json())
    inactive = client.get("/api/kassenprofile", params={"mit_inaktiv": True}).json()
    assert next(row for row in inactive if row["id"] == p["id"])["aktiv"] is False


def test_payment_methods_seeded_and_creatable(client):
    pid = client.get("/api/kassenprofile").json()[0]["id"]
    seeded = client.get("/api/zahlungsmethoden", params={"kassenprofil_id": pid}).json()
    assert {"Bar", "Karte"} <= {z["name"] for z in seeded}
    bar = next(z for z in seeded if z["name"] == "Bar")
    assert bar["schublade_oeffnen"] is True
    neu = client.post("/api/zahlungsmethoden", json={
        "kassenprofil_id": pid, "name": "Gutschein", "schublade_oeffnen": False, "negativ_erlaubt": True,
    })
    assert neu.status_code == 201
    assert neu.json()["negativ_erlaubt"] is True
