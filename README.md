# Vereinskasse — Phase 1 + 2

Offlinefähige Mietkasse für Vereine auf dem Raspberry Pi 5. Dieser Stand setzt
**Phase 1** (technischer Prototyp) und **Phase 2** (Stammdaten) aus dem
Lastenheft um: die technische Kette aus Kiosk-Frontend, lokalem Backend, SQLite
und ESC/POS-Hardware — lauffähig **ohne** angeschlossene Hardware über einen
Mock-Drucker — sowie Benutzer/Rollen mit PIN-Anmeldung und die vollständige
Stammdatenverwaltung. Details zu Phase 2: `docs/PHASE2.md`.

## Was schon funktioniert

- FastAPI-Backend mit SQLite (WAL, Fremdschlüssel, Integritätsprüfung)
- Geldrechnung ausschließlich in ganzzahligen Cent (Float ist verboten)
- ESC/POS-Druckdienst hinter austauschbaren Adaptern (Mock / Ethernet / USB)
- Hardware-Diagnose: Testseite, Schnitt-Test, Kassenschublade
- Anmeldung per PIN mit Rollen (Bediener/Administrator/Servicetechniker);
  PINs werden gehasht gespeichert, Sperre nach Fehlversuchen
- Stammdaten: Benutzer, Vereine, Kassenprofile, Veranstaltungen, Kategorien,
  Artikel (mit Pfandzuordnung, Kopieren, Reihenfolge, Sammelbearbeitung),
  Pfandarten, Zahlungsmethoden
- Alembic-Migrationen als versionierter Schemapfad
- Touchtaugliches Frontend (React + TypeScript + Vite): Login, Artikelverwaltung,
  Servicebildschirm
- Protokollierung (Audit-Log, Druckaufträge) und über die Oberfläche änderbare
  Hardware-Einstellungen
- systemd-Dienste und Chromium-Kiosk für den Autostart auf dem Pi
- Automatische Tests (46 Tests, grün)

## Schnellstart (Entwicklung, ohne Hardware)

**Backend**

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
VK_DATA_DIR=$(mktemp -d) .venv/bin/uvicorn app.main:app --port 8000
```

**Frontend** (zweites Terminal)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (leitet /api an :8000)
```

**Tests**

```bash
cd backend && python -m pytest -q
```

Für den Betrieb auf dem Pi (ein Origin, Autostart): `frontend/` bauen
(`npm run build`) — das Backend liefert dann `frontend/dist` unter `/` aus.
Vollständige Anleitung: `deploy/INSTALL.md`.

## Projektstruktur

```
vereinskasse/
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI-App, Lifespan, statisches Frontend
│   │   ├── config.py         Einstellungen (Umgebungsvariablen, keine Secrets)
│   │   ├── database.py       SQLite-Engine, WAL/FK, Integritätsprüfung
│   │   ├── models.py         Phase-1-Datenmodell
│   │   ├── money.py          Cent-Arithmetik (kein Float)
│   │   ├── schemas.py        API-Ein-/Ausgaben
│   │   ├── routers/          health, diagnose, einstellungen
│   │   └── hardware/         ESC/POS + Adapter (mock/network/usb) + Dienst
│   ├── tests/                money, escpos, diagnose (21 Tests)
│   └── requirements.txt
├── frontend/
│   └── src/                  React/TS Servicebildschirm (api.ts, Diagnose.tsx)
├── deploy/                   systemd-Dienste, Kiosk-Skript, INSTALL.md
└── docs/                     ARCHITEKTUR.md, HARDWARE-TEST.md
```

## Wichtige API-Endpunkte

| Methode | Pfad | Zweck |
| --- | --- | --- |
| GET | `/api/health` | Version + DB-Integrität |
| GET | `/api/diagnose/drucker/status` | Druckerstatus (bereit/unbekannt/nicht erreichbar) |
| POST | `/api/diagnose/drucker/testseite` | Testseite drucken |
| POST | `/api/diagnose/drucker/schnitt-test` | mehrere Tickets + Schnitt (`{"anzahl": n}`) |
| POST | `/api/diagnose/schublade/oeffnen` | Schubladenimpuls (`{"grund": "…"}`) |
| GET/PUT | `/api/einstellungen[/{schluessel}]` | Hardware-Einstellungen lesen/ändern |

## Hinweise / Grenzen

- **Keine Verkaufsfunktion.** Warenkorb, Zahlungen, Pfand, Auswertungen und
  Export folgen in den Phasen 2–7.
- **Hardware-Parameter sind Platzhalter**, bis sie am echten NetumScan NS-8360L
  verifiziert sind (Lastenheft 4.2). Bis dahin: Transport `mock`.
- **Keine produktive Freigabe.** Fiskalisierung (TSE/DSFinV-K, § 146a AO,
  KassenSichV) ist noch nicht umgesetzt und vor dem Echtbetrieb rechtlich zu
  klären (Lastenheft 26).

Details zu den Entscheidungen: `docs/ARCHITEKTUR.md`.
```
