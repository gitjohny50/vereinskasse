"""Phase 5: Kassenabschluss - X-Bericht (Zwischenstand), Z-Abschluss
(unveränderlich, taggt Verkäufe), Kassensturz und Rollenprüfung.

Demo: Cola 250 + Glaspfand 200 automatisch; Bar (schublade -> bar),
Karte (keine Schublade -> unbar)."""


def _ctx(client):
    pid = client.get("/api/kassenprofile").json()[0]["id"]
    arts = {a["name"]: a for a in client.get("/api/artikel", params={"kassenprofil_id": pid}).json()}
    zm = {z["name"]: z for z in client.get("/api/zahlungsmethoden", params={"kassenprofil_id": pid}).json()}
    return pid, arts, zm


def _verkauf(client, pid, artikel_id, menge, zm_id, gegeben=None):
    body = {"kassenprofil_id": pid, "artikel": [{"artikel_id": artikel_id, "menge": menge}], "zahlungsmethode_id": zm_id}
    if gegeben is not None:
        body["gegeben_cent"] = gegeben
    return client.post("/api/verkauf", json=body)


def test_x_bericht_zwischenstand(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 2, zm["Bar"]["id"], gegeben=1000)   # 500 + 400 Pfand = 900 bar
    _verkauf(client, pid, arts["Pommes"]["id"], 1, zm["Karte"]["id"])             # 400 unbar
    x = client.get("/api/abschluss/x", params={"kassenprofil_id": pid, "anfangsbestand_cent": 5000}).json()
    assert x["typ"] == "X" and x["nummer"] is None
    assert x["anzahl_verkaeufe"] == 2
    assert x["waren_cent"] == 900 and x["pfand_cent"] == 400 and x["gesamt_cent"] == 1300
    assert x["bar_cent"] == 900                     # nur die Barzahlung
    assert x["erwartet_cent"] == 5900              # Anfangsbestand 5000 + 900 bar
    bar = {z["bezeichnung"]: z for z in x["zahlarten"]}
    assert bar["Bar"]["bar"] is True and bar["Karte"]["bar"] is False


def test_z_abschluss_schliesst_und_taggt(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 1, zm["Bar"]["id"], gegeben=1000)
    z = client.post("/api/abschluss/z", json={"kassenprofil_id": pid, "anfangsbestand_cent": 0}).json()
    assert z["typ"] == "Z" and z["nummer"] == "Z-0001"
    # Danach keine offenen Verkäufe mehr
    x = client.get("/api/abschluss/x", params={"kassenprofil_id": pid}).json()
    assert x["anzahl_verkaeufe"] == 0


def test_kassensturz_differenz(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 1, zm["Bar"]["id"], gegeben=1000)  # 250 + 200 = 450 bar
    z = client.post("/api/abschluss/z", json={
        "kassenprofil_id": pid, "anfangsbestand_cent": 5000, "gezaehlt_cent": 5450}).json()
    assert z["erwartet_cent"] == 5450          # 5000 + 450
    assert z["differenz_cent"] == 0
    z2 = client.get(f"/api/abschluss/{z['abschluss_id']}").json()
    assert z2["nummer"] == "Z-0001"


def test_zweiter_z_nur_neue_verkaeufe(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Pommes"]["id"], 1, zm["Bar"]["id"], gegeben=400)
    client.post("/api/abschluss/z", json={"kassenprofil_id": pid})
    _verkauf(client, pid, arts["Pommes"]["id"], 2, zm["Bar"]["id"], gegeben=800)
    z2 = client.post("/api/abschluss/z", json={"kassenprofil_id": pid}).json()
    assert z2["nummer"] == "Z-0002"
    assert z2["anzahl_verkaeufe"] == 1 and z2["gesamt_cent"] == 800   # nur der zweite Verkauf
    liste = client.get("/api/abschluss", params={"kassenprofil_id": pid}).json()
    assert [a["nummer"] for a in liste] == ["Z-0002", "Z-0001"]


def test_z_erzeugt_druckauftrag(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 1, zm["Bar"]["id"], gegeben=1000)
    client.post("/api/abschluss/z", json={"kassenprofil_id": pid})
    typen = {j["dokumenttyp"] for j in client.get("/api/druckwarteschlange").json()}
    assert "Kassenabschluss" in typen


def test_nachdruck(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 1, zm["Bar"]["id"], gegeben=1000)
    z = client.post("/api/abschluss/z", json={"kassenprofil_id": pid}).json()
    assert client.post(f"/api/abschluss/{z['abschluss_id']}/nachdruck").json()["ok"] is True


def test_abschluss_nur_admin(bediener_client):
    pid = bediener_client.get("/api/kassenprofile").json()[0]["id"]
    assert bediener_client.get("/api/abschluss/x", params={"kassenprofil_id": pid}).status_code == 403
    assert bediener_client.post("/api/abschluss/z", json={"kassenprofil_id": pid}).status_code == 403
