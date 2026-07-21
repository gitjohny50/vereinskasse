"""FastAPI-Anwendung (lokales Kassen-Backend).

Startet die Datenbank, führt das Seeding aus (Rollen, Erst-Administrator,
Demo-Profil) und bindet die Router. Im Produktivbetrieb liefert dieselbe
Anwendung das gebaute Frontend aus, sodass Chromium im Kiosk nur eine lokale
Adresse öffnen muss.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .hardware import service as hw_service
from .hardware.service import ensure_defaults
from .models import Artikel, Kassenprofil
from .routers import analytics, auth, catalog, diagnostics, health, profiles, reports, sales, settings as settings_router, users
from .routers import print_queue as print_queue_router
from . import print_queue
from .seed import seed_all
from .timeutils import local_tz, now_local


def _worker_intervall() -> float:
    try:
        return float(os.environ.get("VK_PRINT_WORKER_INTERVALL", "8"))
    except ValueError:
        return 8.0


async def _druck_worker(stop: asyncio.Event) -> None:
    """Verarbeitet offene Druckaufträge dauerhaft im Hintergrund - unabhängig
    davon, welcher Reiter im Frontend geöffnet ist. So werden Tickets, die beim
    ersten Versuch scheitern (z. B. kurzer USB-Hänger), zuverlässig nachgedruckt.
    Die eigentliche Druckausgabe läuft in einem Thread, um den Server nicht zu
    blockieren."""
    intervall = _worker_intervall()
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=intervall)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            break
        try:
            def _lauf():
                with SessionLocal() as session:
                    print_queue.verarbeite_offene(session)
            await asyncio.to_thread(_lauf)
        except Exception:  # pragma: no cover - Worker darf nie sterben
            pass


def _startup_delay() -> float:
    try:
        return float(os.environ.get("VK_STARTUP_BELEG_DELAY", "8"))
    except ValueError:
        return 8.0


def _local_ips() -> list[str]:
    ips: set[str] = set()
    hostname = socket.gethostname()
    try:
        for result in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = result[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def _internet_status() -> str:
    for host, port in [("1.1.1.1", 53), ("8.8.8.8", 53)]:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return "online"
        except OSError:
            continue
    return "offline"


def _startup_info() -> dict[str, str | list[str]]:
    host = os.environ.get("VK_HOST", "0.0.0.0")
    port = os.environ.get("VK_PORT", "8000")
    ips = _local_ips()
    urls = [f"http://{ip}:{port}" for ip in ips]
    hostname = socket.gethostname()
    mdns_name = os.environ.get("VK_MDNS_NAME", hostname or "kasse").strip().removesuffix(".local")
    mdns_url = f"http://{mdns_name}.local:{port}" if mdns_name else ""
    if mdns_url:
        urls.append(mdns_url)
    if hostname:
        urls.append(f"http://{hostname}.local:{port}")
    public_host = os.environ.get("VK_PUBLIC_HOST", "").strip()
    if public_host:
        urls.insert(0, f"http://{public_host}:{port}")

    with SessionLocal() as session:
        profil = session.query(Kassenprofil).filter(Kassenprofil.aktiv.is_(True)).order_by(Kassenprofil.name).first()
        artikel_count = 0
        profil_text = "-"
        if profil is not None:
            profil_text = f"{profil.name} ({profil.id})"
            artikel_count = session.query(Artikel).filter(
                Artikel.kassenprofil_id == profil.id,
                Artikel.aktiv.is_(True),
                Artikel.archiviert.is_(False),
            ).count()
        cfg = hw_service.load_hw_settings(session)
        drucker = cfg.get("drucker.transport", "mock")

    return {
        "zeit": now_local().strftime("%d.%m.%Y %H:%M:%S"),
        "hostname": hostname or "-",
        "user": getpass.getuser(),
        "version": settings.app_version,
        "internet": _internet_status(),
        "mdns": mdns_url or "-",
        "timezone": str(local_tz()),
        "profil": f"{profil_text}, {artikel_count} Artikel",
        "data_dir": str(settings.data_dir),
        "drucker": drucker,
        "host": host,
        "urls": urls,
    }


async def _startup_receipt_task(stop: asyncio.Event) -> None:
    if os.environ.get("VK_STARTUP_BELEG", "0") != "1":
        return
    try:
        await asyncio.wait_for(stop.wait(), timeout=_startup_delay())
        return
    except asyncio.TimeoutError:
        pass
    if stop.is_set():
        return
    try:
        info = _startup_info()

        def _druck():
            with SessionLocal() as session:
                hw_service.run_startup_receipt(session, info)

        await asyncio.to_thread(_druck)
    except Exception:  # pragma: no cover - Startbeleg darf Backend nie verhindern
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as session:
        ensure_defaults(session)  # Hardware-Standardeinstellungen (Phase 1)
        seed_all(session)         # Rollen, Erst-Administrator, Demo-Profil (Phase 2)

    stop = asyncio.Event()
    worker = None
    startup_receipt = None
    if os.environ.get("VK_PRINT_WORKER", "1") == "1":
        worker = asyncio.create_task(_druck_worker(stop))
    startup_receipt = asyncio.create_task(_startup_receipt_task(stop))
    try:
        yield
    finally:
        stop.set()
        for task in (worker, startup_receipt):
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


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
app.include_router(analytics.router)
app.include_router(print_queue_router.router)
app.include_router(diagnostics.router)
app.include_router(settings_router.router)

# Optional: gebautes Frontend ausliefern, falls vorhanden.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
