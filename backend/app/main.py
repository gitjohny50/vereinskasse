"""FastAPI-Anwendung (lokales Kassen-Backend).

Startet die Datenbank, führt das Seeding aus (Rollen, Erst-Administrator,
Demo-Profil) und bindet die Router. Im Produktivbetrieb liefert dieselbe
Anwendung das gebaute Frontend aus, sodass Chromium im Kiosk nur eine lokale
Adresse öffnen muss.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .hardware.service import ensure_defaults
from .routers import auth, catalog, diagnostics, health, profiles, reports, sales, settings as settings_router, users
from .routers import print_queue as print_queue_router
from .seed import seed_all


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as session:
        ensure_defaults(session)  # Hardware-Standardeinstellungen (Phase 1)
        seed_all(session)         # Rollen, Erst-Administrator, Demo-Profil (Phase 2)
    yield


app = FastAPI(title="Vereinskasse", version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(catalog.router)
app.include_router(sales.router)
app.include_router(reports.router)
app.include_router(print_queue_router.router)
app.include_router(diagnostics.router)
app.include_router(settings_router.router)

# Optional: gebautes Frontend ausliefern, falls vorhanden.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
