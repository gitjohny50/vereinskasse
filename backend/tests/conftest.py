"""Test-Setup.

Setzt VOR dem Import der Anwendung ein temporäres Datenverzeichnis. Jeder Test
erhält eine frische DB, das Seeding (Rollen, Demo-Profil) läuft über den
Lifespan, und der Client ist als Servicetechniker angemeldet (Stufe 30 erfüllt
alle Rollenprüfungen). Für gezielte Rollentests gibt es zusätzliche Fixtures.
"""
import os
import tempfile

os.environ.setdefault("VK_DATA_DIR", tempfile.mkdtemp(prefix="vk-test-"))
os.environ.setdefault("VK_INITIAL_ADMIN_PIN", "123456")
os.environ.setdefault("VK_PBKDF2_ITERATIONS", "1000")  # nur für Tests, Produktiv bleibt hoch

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.hardware.service import ensure_defaults  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Benutzer  # noqa: E402
from app.seed import ensure_roles  # noqa: E402
from app.security import hash_pin  # noqa: E402


def _reset_and_seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_defaults(session)
        rollen = ensure_roles(session)
        # Bekannte Testbenutzer je Rolle.
        session.add_all([
            Benutzer(name="Test Service", pin_hash=hash_pin("9999"), rolle_id=rollen["servicetechniker"].id),
            Benutzer(name="Test Admin", pin_hash=hash_pin("2222"), rolle_id=rollen["administrator"].id),
            Benutzer(name="Test Bediener", pin_hash=hash_pin("1111"), rolle_id=rollen["bediener"].id),
        ])
        session.commit()
        ids = {b.name: b.id for b in session.query(Benutzer).all()}
    return ids


def _login(c: TestClient, benutzer_id: int, pin: str) -> str:
    r = c.post("/api/auth/login", json={"benutzer_id": benutzer_id, "pin": pin})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture()
def ids():
    return _reset_and_seed()


@pytest.fixture()
def raw_client(ids):
    with TestClient(app) as c:
        c.state_ids = ids  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
def client(ids):
    """Als Servicetechniker angemeldeter Client (erfüllt alle Rollenprüfungen)."""
    with TestClient(app) as c:
        token = _login(c, ids["Test Service"], "9999")
        c.headers.update({"Authorization": f"Bearer {token}"})
        c.state_ids = ids  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
def bediener_client(ids):
    with TestClient(app) as c:
        token = _login(c, ids["Test Bediener"], "1111")
        c.headers.update({"Authorization": f"Bearer {token}"})
        c.state_ids = ids  # type: ignore[attr-defined]
        yield c
