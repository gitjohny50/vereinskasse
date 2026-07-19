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


def test_duplicate_category_name_rejected(client):
    pid = _profil_id(client)
    r1 = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "Getränke Spezial"})
    assert r1.status_code == 201
    r2 = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "  getränke   spezial  "})
    assert r2.status_code == 409


def test_update_category_color_and_reject_duplicate_rename(client):
    pid = _profil_id(client)
    a = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "A", "farbe": "#111111"}).json()
    b = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "B", "farbe": "#222222"}).json()
    r = client.put(f"/api/kategorien/{a['id']}", json={
        "kassenprofil_id": pid, "name": "A", "farbe": "#abcdef", "symbol": "", "sortierung": 4, "aktiv": True,
    })
    assert r.status_code == 200
    assert r.json()["farbe"] == "#abcdef"
    assert r.json()["sortierung"] == 4
    dup = client.put(f"/api/kategorien/{b['id']}", json={
        "kassenprofil_id": pid, "name": "A", "farbe": "#222222", "symbol": "", "sortierung": 0, "aktiv": True,
    })
    assert dup.status_code == 409


def test_delete_category_only_after_zabschluss_and_detaches_articles(client):
    pid = _profil_id(client)
    kat = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "Nur kurz"}).json()
    art = client.post("/api/artikel", json={
        "kassenprofil_id": pid, "name": "Kurzartikel", "preis_cent": 100, "kategorie_id": kat["id"],
    }).json()
    zm = client.get("/api/zahlungsmethoden", params={"kassenprofil_id": pid}).json()[0]
    client.post("/api/verkauf", json={
        "kassenprofil_id": pid, "artikel": [{"artikel_id": art["id"], "menge": 1}], "zahlungsmethode_id": zm["id"],
        "gegeben_cent": 100,
    })

    blocked = client.delete(f"/api/kategorien/{kat['id']}")
    assert blocked.status_code == 409

    client.post("/api/abschluss/z", json={"kassenprofil_id": pid})
    deleted = client.delete(f"/api/kategorien/{kat['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["name"] == "Nur kurz"
    assert client.get(f"/api/artikel/{art['id']}").json()["kategorie_id"] is None
    kategorien = client.get("/api/kategorien", params={"kassenprofil_id": pid}).json()
    assert kat["id"] not in [k["id"] for k in kategorien]


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
    kat = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "Kisten"}).json()
    art = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "Kiste", "preis_cent": 900}).json()
    assert art["pfandzuordnungen"] == []
    upd = client.put(f"/api/artikel/{art['id']}", json={
        "name": "Kiste groß",
        "kategorie_id": kat["id"],
        "pfandzuordnungen": [{"pfandart_id": pf["id"], "menge_pro_einheit": 12}]
    }).json()
    assert upd["name"] == "Kiste groß"
    assert upd["kategorie_id"] == kat["id"]
    assert len(upd["pfandzuordnungen"]) == 1
    assert upd["pfandzuordnungen"][0]["menge_pro_einheit"] == 12


def test_csv_import_creates_articles_with_category_and_deposit(client):
    pid = _profil_id(client)
    kat = client.post("/api/kategorien", json={"kassenprofil_id": pid, "name": "Import Getränke"}).json()
    pf = client.post("/api/pfandarten", json={"kassenprofil_id": pid, "name": "Import Glas", "betrag_cent": 200}).json()
    csv_text = "name;preis;kategorie;pfand;ticket;reihenfolge\nImport Wasser;2,00;Import Getränke;Import Glas:1;pro_stueck;7\n"

    r = client.post("/api/artikel/csv-import", json={"kassenprofil_id": pid, "csv_text": csv_text, "delimiter": ";"})

    assert r.status_code == 200
    assert r.json()["angelegt"] == 1
    rows = client.get("/api/artikel", params={"kassenprofil_id": pid}).json()
    art = next(a for a in rows if a["name"] == "Import Wasser")
    assert art["preis_cent"] == 200
    assert art["kategorie_id"] == kat["id"]
    assert art["sortierung"] == 7
    assert art["pfandzuordnungen"][0]["pfandart_id"] == pf["id"]


def test_csv_import_rejects_duplicate_inside_file_without_partial_import(client):
    pid = _profil_id(client)
    csv_text = "name;preis\nCSV A;1,00\nCSV A;2,00\n"

    r = client.post("/api/artikel/csv-import", json={"kassenprofil_id": pid, "csv_text": csv_text, "delimiter": ";"})

    assert r.status_code == 200
    assert r.json()["angelegt"] == 0
    assert "doppelt" in r.json()["fehler"][0]
    rows = client.get("/api/artikel", params={"kassenprofil_id": pid}).json()
    assert "CSV A" not in {a["name"] for a in rows}


def test_csv_import_updates_archived_article_and_creates_missing_master_data(client):
    pid = _profil_id(client)
    art = client.post("/api/artikel", json={"kassenprofil_id": pid, "name": "CSV Alt", "preis_cent": 100}).json()
    client.delete(f"/api/artikel/{art['id']}")
    csv_text = "name;preis;kategorie;pfand;ticket\nCSV Alt;3,50;CSV Kategorie;CSV Pfand:2:1,50;kein\n"

    r = client.post("/api/artikel/csv-import", json={"kassenprofil_id": pid, "csv_text": csv_text, "delimiter": ";"})

    assert r.status_code == 200
    body = r.json()
    assert body["angelegt"] == 0
    assert body["aktualisiert"] == 1
    assert body["kategorien_angelegt"] == 1
    assert body["pfandarten_angelegt"] == 1
    rows = client.get("/api/artikel", params={"kassenprofil_id": pid}).json()
    updated = next(a for a in rows if a["name"] == "CSV Alt")
    assert updated["archiviert"] is False
    assert updated["aktiv"] is True
    assert updated["preis_cent"] == 350
    assert updated["artikelticket_modus"] == "kein"
    assert updated["pfandzuordnungen"][0]["menge_pro_einheit"] == 2


def test_archive_all_and_reset_article_deposits(client):
    pid = _profil_id(client)
    r = client.post("/api/artikel/pfand-zuruecksetzen", params={"kassenprofil_id": pid})
    assert r.status_code == 200
    assert r.json()["anzahl"] >= 1
    rows = client.get("/api/artikel", params={"kassenprofil_id": pid}).json()
    assert all(a["pfandzuordnungen"] == [] for a in rows)

    r2 = client.post("/api/artikel/alle-archivieren", params={"kassenprofil_id": pid})
    assert r2.status_code == 200
    assert r2.json()["anzahl"] >= 1
    assert client.get("/api/artikel", params={"kassenprofil_id": pid}).json() == []


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
