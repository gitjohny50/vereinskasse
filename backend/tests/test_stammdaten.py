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
