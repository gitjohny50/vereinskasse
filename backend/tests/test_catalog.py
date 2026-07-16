"""Katalogtests. Nutzt den als Servicetechniker angemeldeten `client` (erfüllt
alle Rollenprüfungen) und das per Seeding erzeugte Demo-Kassenprofil."""


def _profil_id(client) -> int:
    r = client.get("/api/kassenprofile")
    assert r.status_code == 200
    return r.json()[0]["id"]


def test_demo_profile_and_catalog_seeded(client):
    pid = _profil_id(client)
    arts = client.get("/api/artikel", params={"kassenprofil_id": pid}).json()
    namen = {a["name"] for a in arts}
    assert {"Cola", "Wasser", "Pommes"} <= namen
    # Cola trägt automatisch Glaspfand.
    cola = next(a for a in arts if a["name"] == "Cola")
    assert cola["preis_cent"] == 250
    assert len(cola["pfandzuordnungen"]) == 1


def test_create_category_and_article_with_deposit(client):
    pid = _profil_id(client)
    kat = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "Kaffee und Kuchen", "sortierung": 3}).json()
    pf = client.post("/api/pfandarten", json={"kassenprofil_id": pid, "name": "Geschirrpfand", "betrag_cent": 300}).json()
    r = client.post("/api/artikel", json={
        "kassenprofil_id": pid, "name": "Kuchen", "preis_cent": 350, "kategorie_id": kat["id"],
        "pfandzuordnungen": [{"pfandart_id": pf["id"], "menge_pro_einheit": 1}],
    })
    assert r.status_code == 201
    art = r.json()
    assert art["preis_cent"] == 350
    assert art["pfandzuordnungen"][0]["pfandart_id"] == pf["id"]


def test_price_stored_as_cents(client):
    pid = _profil_id(client)
    art = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "Bier", "preis_cent": 380}).json()
    assert art["preis_cent"] == 380  # ganzzahlig, kein Float


def test_invalid_ticket_mode_rejected(client):
    pid = _profil_id(client)
    r = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "X", "preis_cent": 100, "artikelticket_modus": "quatsch"})
    assert r.status_code == 422


def test_article_is_archived_not_deleted(client):
    pid = _profil_id(client)
    art = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "Temporär", "preis_cent": 100}).json()
    r = client.delete(f"/api/artikel/{art['id']}")
    assert r.status_code == 200
    assert r.json()["archiviert"] is True
    # Standardliste ohne Archivierte enthält ihn nicht mehr.
    aktive = client.get("/api/artikel", params={"kassenprofil_id": pid}).json()
    assert art["id"] not in [a["id"] for a in aktive]
    # Mit Flag ist er weiterhin da (nicht physisch gelöscht).
    alle = client.get("/api/artikel", params={"kassenprofil_id": pid, "mit_archiviert": True}).json()
    assert art["id"] in [a["id"] for a in alle]


def test_copy_article_drops_number_and_barcode(client):
    pid = _profil_id(client)
    orig = client.post("/api/artikel", json={
        "kassenprofil_id": pid, "name": "Original", "preis_cent": 200,
        "artikelnummer": "A-100", "barcode": "12345",
    }).json()
    kopie = client.post(f"/api/artikel/{orig['id']}/kopieren").json()
    assert kopie["id"] != orig["id"]
    assert kopie["name"] == "Original (Kopie)"
    assert kopie["artikelnummer"] == ""
    assert kopie["barcode"] == ""
    assert kopie["preis_cent"] == 200


def test_bulk_price_increase(client):
    pid = _profil_id(client)
    a1 = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "B1", "preis_cent": 100}).json()
    a2 = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "B2", "preis_cent": 200}).json()
    r = client.post("/api/artikel/sammelbearbeitung", json={"artikel_ids": [a1["id"], a2["id"]], "preis_delta_cent": 50})
    assert r.status_code == 200
    preise = {x["name"]: x["preis_cent"] for x in r.json()}
    assert preise["B1"] == 150 and preise["B2"] == 250


def test_reorder_sets_positions(client):
    pid = _profil_id(client)
    a1 = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "R1", "preis_cent": 100}).json()
    a2 = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "R2", "preis_cent": 100}).json()
    client.post("/api/artikel/reihenfolge", json={"reihenfolge": [a2["id"], a1["id"]]})
    assert client.get(f"/api/artikel/{a2['id']}").json()["sortierung"] == 1
    assert client.get(f"/api/artikel/{a1['id']}").json()["sortierung"] == 2


def test_update_article_replaces_deposits(client):
    pid = _profil_id(client)
    pf = client.post("/api/pfandarten", json={"kassenprofil_id": pid, "name": "Kistenpfand", "betrag_cent": 500}).json()
    art = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "Kiste", "preis_cent": 900}).json()
    assert art["pfandzuordnungen"] == []
    upd = client.put(f"/api/artikel/{art['id']}", json={
        "pfandzuordnungen": [{"pfandart_id": pf["id"], "menge_pro_einheit": 12}]
    }).json()
    assert len(upd["pfandzuordnungen"]) == 1
    assert upd["pfandzuordnungen"][0]["menge_pro_einheit"] == 12


def test_toggle_aktiv_via_full_put(client):
    """Phase 2.1: aktiv-Status von Kategorie/Pfandart/Zahlungsmethode ist über
    den vollständigen PUT (wie ihn das Frontend sendet) umschaltbar."""
    pid = _profil_id(client)
    k = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "Temp-Kat"}).json()
    r = client.put(f"/api/kategorien/{k['id']}", json={
        "kassenprofil_id": pid, "name": "Temp-Kat", "farbe": "", "symbol": "", "sortierung": 0, "aktiv": False})
    assert r.status_code == 200 and r.json()["aktiv"] is False

    z = client.post("/api/zahlungsmethoden", json={"kassenprofil_id": pid, "name": "Temp-Zahl"}).json()
    r = client.put(f"/api/zahlungsmethoden/{z['id']}", json={
        "kassenprofil_id": pid, "name": "Temp-Zahl", "kurzname": "", "farbe": "", "symbol": "", "sortierung": 0,
        "schublade_oeffnen": True, "rueckgeld_berechnen": True, "negativ_erlaubt": False, "aktiv": False})
    assert r.status_code == 200 and r.json()["aktiv"] is False
