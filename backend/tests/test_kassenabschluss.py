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


def test_abschluss_csv_enthaelt_detailpositionen(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 2, zm["Bar"]["id"], gegeben=1000)
    z = client.post("/api/abschluss/z", json={"kassenprofil_id": pid}).json()

    res = client.get(f"/api/abschluss/{z['abschluss_id']}/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "abschluss-Z-0001-detail.csv" in res.headers["content-disposition"]

    text = res.content.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == (
        "abschluss_nummer;abschluss_datum;abschluss_uhrzeit;belegnummer;verkauf_datum;verkauf_uhrzeit;"
        "verkauf_stunde;wochentag;position_typ;artikel;menge;einzelpreis_eur;umsatz_eur;"
        "zahlungsart;gegeben_eur;rueckgeld_eur"
    )
    assert ";Artikel;Cola;2;2,50;5,00;Bar;10,00;" in text
    assert ";Cola;" in text


def test_daten_reset_nur_nach_abschluss(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 1, zm["Bar"]["id"], gegeben=1000)

    offen = client.post(
        "/api/abschluss/daten-zuruecksetzen",
        params={"kassenprofil_id": pid},
        json={"bestaetigung": "ARTIKEL LOESCHEN"},
    )
    assert offen.status_code == 409

    client.post("/api/abschluss/z", json={"kassenprofil_id": pid})
    reset = client.post(
        "/api/abschluss/daten-zuruecksetzen",
        params={"kassenprofil_id": pid},
        json={"bestaetigung": "ARTIKEL LOESCHEN"},
    )
    assert reset.status_code == 200
    assert reset.json()["artikel_geloescht"] >= 1
    assert reset.json()["belege_geloescht"] == 1
    assert reset.json()["verkaufspositionen_geloescht"] >= 1
    assert reset.json()["zahlungen_geloescht"] == 1
    assert reset.json()["abschluesse_geloescht"] == 1
    assert reset.json()["belegkreis_zurueckgesetzt"] is True
    assert client.get("/api/artikel", params={"kassenprofil_id": pid, "mit_archiviert": True}).json() == []
    assert client.get("/api/verkauf", params={"kassenprofil_id": pid}).json() == []
    assert client.get("/api/abschluss", params={"kassenprofil_id": pid}).json() == []


def test_daten_reset_mit_auswahl(client):
    pid, arts, zm = _ctx(client)
    _verkauf(client, pid, arts["Cola"]["id"], 1, zm["Bar"]["id"], gegeben=1000)
    client.post("/api/abschluss/z", json={"kassenprofil_id": pid})

    reset = client.post(
        "/api/abschluss/daten-zuruecksetzen",
        params={"kassenprofil_id": pid},
        json={
            "bestaetigung": "DATEN LOESCHEN",
            "belege_loeschen": True,
            "abschluesse_loeschen": True,
            "artikel_loeschen": False,
            "pfandzuordnungen_loeschen": False,
            "druckwarteschlange_loeschen": True,
            "belegkreis_zuruecksetzen": True,
        },
    )
    assert reset.status_code == 200
    daten = reset.json()
    assert daten["belege_geloescht"] == 1
    assert daten["abschluesse_geloescht"] == 1
    assert daten["artikel_geloescht"] == 0
    assert daten["pfandzuordnungen_geloescht"] == 0
    assert daten["druckauftraege_geloescht"] >= 1
    assert client.get("/api/artikel", params={"kassenprofil_id": pid, "mit_archiviert": True}).json() != []
    assert client.get("/api/verkauf", params={"kassenprofil_id": pid}).json() == []
    assert client.get("/api/druckwarteschlange").json() == []


def test_abschluss_reset_braucht_mindestens_eine_auswahl(client):
    pid, _, _ = _ctx(client)
    reset = client.post(
        "/api/abschluss/daten-zuruecksetzen",
        params={"kassenprofil_id": pid},
        json={
            "bestaetigung": "DATEN LOESCHEN",
            "belege_loeschen": False,
            "abschluesse_loeschen": False,
            "artikel_loeschen": False,
            "pfandzuordnungen_loeschen": False,
            "druckwarteschlange_loeschen": False,
            "belegkreis_zuruecksetzen": False,
        },
    )
    assert reset.status_code == 422


def test_daten_reset_braucht_bestaetigung(client):
    pid, _, _ = _ctx(client)
    reset = client.post(
        "/api/abschluss/daten-zuruecksetzen",
        params={"kassenprofil_id": pid},
        json={"bestaetigung": "bitte"},
    )
    assert reset.status_code == 422


def test_abschluss_nur_admin(bediener_client):
    pid = bediener_client.get("/api/kassenprofile").json()[0]["id"]
    assert bediener_client.get("/api/abschluss/x", params={"kassenprofil_id": pid}).status_code == 403
    assert bediener_client.post("/api/abschluss/z", json={"kassenprofil_id": pid}).status_code == 403
    assert bediener_client.post(
        "/api/abschluss/daten-zuruecksetzen",
        params={"kassenprofil_id": pid},
        json={"bestaetigung": "ARTIKEL LOESCHEN"},
    ).status_code == 403
