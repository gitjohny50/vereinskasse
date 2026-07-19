"""Verkaufstests. Nutzt den angemeldeten `client` und das Demo-Profil
'Vereinsfest' (Cola 250 + Glaspfand 200 automatisch, Pommes 400,
Zahlarten Bar/Karte)."""


def _ctx(client):
    pid = client.get("/api/kassenprofile").json()[0]["id"]
    arts = {a["name"]: a for a in client.get("/api/artikel", params={"kassenprofil_id": pid}).json()}
    pf = {p["name"]: p for p in client.get("/api/pfandarten", params={"kassenprofil_id": pid}).json()}
    zm = {z["name"]: z for z in client.get("/api/zahlungsmethoden", params={"kassenprofil_id": pid}).json()}
    return pid, arts, pf, zm


def test_berechnung_auto_pfand(client):
    pid, arts, _, _ = _ctx(client)
    r = client.post("/api/verkauf/berechnung", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 2}]})
    assert r.status_code == 200
    b = r.json()
    assert b["waren_cent"] == 500          # 2 x 250
    assert b["pfand_cent"] == 400          # 2 x 200 Glaspfand automatisch
    assert b["gesamt_cent"] == 900
    typen = [p["typ"] for p in b["positionen"]]
    assert "artikel" in typen and "pfand" in typen


def test_abschluss_bar_mit_rueckgeld(client):
    pid, arts, _, zm = _ctx(client)
    r = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 2}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 1000})
    assert r.status_code == 201
    v = r.json()
    assert v["belegnummer"] == "000001"
    assert v["gesamt_cent"] == 900
    assert v["zahlung"]["rueckgeld_cent"] == 100
    assert v["zahlung"]["gegeben_cent"] == 1000


def test_belegnummer_increments(client):
    pid, arts, _, zm = _ctx(client)
    body = {"kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
            "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 400}
    n1 = client.post("/api/verkauf", json=body).json()["belegnummer"]
    n2 = client.post("/api/verkauf", json=body).json()["belegnummer"]
    assert (n1, n2) == ("000001", "000002")


def test_bar_zu_wenig_gegeben(client):
    pid, arts, _, zm = _ctx(client)
    r = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 100})
    assert r.status_code == 422


def test_karte_ohne_rueckgeld(client):
    pid, arts, _, zm = _ctx(client)
    r = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Karte"]["id"]})
    assert r.status_code == 201
    z = r.json()["zahlung"]
    assert z["gegeben_cent"] == 400 and z["rueckgeld_cent"] == 0


def test_pfandrueckgabe_reduziert_summe(client):
    pid, arts, pf, zm = _ctx(client)
    # Pommes 400 kaufen, 1 Glaspfand (200) zurückgeben -> 200
    r = client.post("/api/verkauf/berechnung", json={
        "kassenprofil_id": pid,
        "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
        "pfand_rueckgaben": [{"pfandart_id": pf["Glaspfand"]["id"], "menge": 1}]})
    b = r.json()
    assert b["pfand_cent"] == -200
    assert b["gesamt_cent"] == 200


def test_negativbetrag_nur_mit_erlaubter_zahlart(client):
    pid, _, pf, zm = _ctx(client)
    # reine Rückgabe -> negativ; Bar hat negativ_erlaubt=False -> 422
    r = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [],
        "pfand_rueckgaben": [{"pfandart_id": pf["Glaspfand"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"]})
    assert r.status_code == 422


def test_event_ohne_pfand(client):
    pid, arts, _, zm = _ctx(client)
    ev = client.post("/api/veranstaltungen", json={
        "kassenprofil_id": pid, "name": "Ohne Pfand", "pfand_aktiv": False}).json()
    r = client.post("/api/verkauf/berechnung", json={
        "kassenprofil_id": pid, "veranstaltung_id": ev["id"],
        "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 1}]})
    b = r.json()
    assert b["pfand_cent"] == 0          # bei diesem Event kein automatisches Pfand
    assert b["gesamt_cent"] == 250


def test_profil_ohne_pfand(client):
    pid, arts, _, _ = _ctx(client)
    profil = client.get("/api/kassenprofile").json()[0]
    client.put(f"/api/kassenprofile/{pid}", json={
        "name": profil["name"], "verein_id": profil["verein_id"], "bonkopf": profil.get("bonkopf") or "",
        "bonfuss": profil.get("bonfuss") or "", "waehrung": profil["waehrung"], "pfand_aktiv": False,
    })
    r = client.post("/api/verkauf/berechnung", json={
        "kassenprofil_id": pid,
        "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 1}],
    })
    b = r.json()
    assert b["pfand_cent"] == 0
    assert b["gesamt_cent"] == 250


def test_verkauf_ist_unveraenderlich(client):
    pid, arts, _, zm = _ctx(client)
    v = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Pommes"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 400}).json()
    # Kein Änderungs-/Löschendpunkt vorhanden.
    assert client.put(f"/api/verkauf/{v['id']}", json={}).status_code == 405
    assert client.delete(f"/api/verkauf/{v['id']}").status_code == 405


def test_nachdruck_und_liste(client):
    pid, arts, _, zm = _ctx(client)
    v = client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": arts["Cola"]["id"], "menge": 1}],
        "zahlungsmethode_id": zm["Bar"]["id"], "gegeben_cent": 500}).json()
    assert client.post(f"/api/verkauf/{v['id']}/nachdruck").json()["ok"] is True
    liste = client.get("/api/verkauf", params={"kassenprofil_id": pid}).json()
    assert v["id"] in [x["id"] for x in liste]
