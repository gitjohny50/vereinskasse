"""Zentrale Konfiguration.

Alle veränderlichen Werte kommen aus Umgebungsvariablen bzw. der Datenbank
(Systemeinstellungen). Es werden bewusst KEINE Zugangsdaten im Quellcode
hinterlegt (Lastenheft 25.1). Für Phase 1 genügen wenige Umgebungswerte;
Hardware-Parameter (Drucker, Schublade) liegen in der DB und sind über die
Oberfläche änderbar (Lastenheft 13.3, 14.6).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Standard-Datenverzeichnis. Auf dem Pi zeigt dies auf die NVMe-SSD.
DEFAULT_DATA_DIR = Path(
    os.environ.get("VK_DATA_DIR", str(Path.home() / "vereinskasse-daten"))
)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = DEFAULT_DATA_DIR
    db_filename: str = "kasse.sqlite3"
    # Bind-Adresse: standardmäßig nur lokal erreichbar (Lastenheft 25.2).
    host: str = os.environ.get("VK_HOST", "127.0.0.1")
    port: int = int(os.environ.get("VK_PORT", "8000"))
    # Frontend-Herkunft für CORS im Entwicklungsbetrieb.
    frontend_origin: str = os.environ.get("VK_FRONTEND_ORIGIN", "http://localhost:5173")
    app_version: str = "0.5.4-phase5"

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
