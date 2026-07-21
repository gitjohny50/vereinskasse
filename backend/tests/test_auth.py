


def test_login_success(raw_client):
    ids = raw_client.state_ids
    r = raw_client.post("/api/auth/login", json={"benutzer_id": ids["Test Admin"], "pin": "2222"})
    assert r.status_code == 200
    body = r.json()
    assert body["rolle"] == "administrator"
    assert body["stufe"] == 20
    assert body["token"]


def test_login_wrong_pin(raw_client):
    ids = raw_client.state_ids
    r = raw_client.post("/api/auth/login", json={"benutzer_id": ids["Test Admin"], "pin": "0000"})
    assert r.status_code == 401


def test_lock_after_five_failures(raw_client):
    ids = raw_client.state_ids
    uid = ids["Test Bediener"]
    for _ in range(5):
        raw_client.post("/api/auth/login", json={"benutzer_id": uid, "pin": "0000"})
    # Auch mit korrekter PIN nun gesperrt (423).
    r = raw_client.post("/api/auth/login", json={"benutzer_id": uid, "pin": "1111"})
    assert r.status_code == 423


def test_protected_endpoint_requires_token(raw_client):
    r = raw_client.get("/api/benutzer")
    assert r.status_code == 401


def test_role_guard_forbids_bediener(bediener_client):
    # Bediener (Stufe 10) darf keine Benutzer verwalten (Admin-Endpunkt).
    r = bediener_client.get("/api/benutzer")
    assert r.status_code == 403
    r2 = bediener_client.delete(f"/api/benutzer/{bediener_client.state_ids['Test Admin']}")
    assert r2.status_code == 403


def test_me_and_logout(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["rolle"] == "servicetechniker"
    r2 = client.post("/api/auth/logout")
    assert r2.status_code == 200
    # Nach Logout ist das Token ungültig.
    r3 = client.get("/api/auth/me")
    assert r3.status_code == 401


def test_admin_can_delete_user_without_history(client):
    rollen = client.get("/api/rollen").json()
    bediener_rolle = next(r for r in rollen if r["name"] == "bediener")
    created = client.post("/api/benutzer", json={"name": "Temp Bediener", "pin": "4444", "rolle_id": bediener_rolle["id"]})
    assert created.status_code == 201
    uid = created.json()["id"]

    deleted = client.delete(f"/api/benutzer/{uid}")
    assert deleted.status_code == 204
    liste = client.get("/api/benutzer").json()
    assert all(b["id"] != uid for b in liste)


def test_admin_cannot_delete_current_user(client):
    uid = client.state_ids["Test Service"]
    r = client.delete(f"/api/benutzer/{uid}")
    assert r.status_code == 409
