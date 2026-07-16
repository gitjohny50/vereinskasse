# Architektur — Phase 1 (Technischer Prototyp)

Dieses Dokument beschreibt die Struktur des Prototyps und die bewusst getroffenen
Entscheidungen. Es folgt der empfohlenen Architektur aus Lastenheft 5 und bereitet
die späteren Phasen vor, ohne sie schon umzusetzen.

## Überblick

```
┌────────────────────────────────────────────────────────────┐
│  Raspberry Pi 5 (offline)                                   │
│                                                            │
│  Chromium Kiosk ──HTTP──▶ FastAPI-Backend ──▶ SQLite (NVMe) │
│   (React/Vite)            │  Geschäftslogik                 │
│                           │                                 │
│                           ├──▶ ESC/POS-Druckdienst          │
│                           │      ├─ MockPrinter (Dev/Test)  │
│                           │      ├─ NetworkPrinter (TCP)    │
│                           │      └─ UsbPrinter (pyusb)      │
│                           │                                 │
│                           └──▶ Kassenschublade (über Drucker)│
└────────────────────────────────────────────────────────────┘
```

## Entscheidungen

**Frontend ohne DB-Zugriff.** Das Frontend spricht ausschließlich die lokale
API an (Lastenheft 5.1). Sämtliche Geschäftslogik — auch Preis- und
Pfandberechnung in späteren Phasen — liegt im Backend (28.1).

**Geld nur als Cent.** `app/money.py` kapselt alle Umrechnungen. Float ist für
Geldbeträge technisch verboten und wird per `TypeError` abgewiesen (5.3, 32.5).

**SQLite mit erzwungenen PRAGMA.** `app/database.py` setzt bei jeder Verbindung
`foreign_keys=ON` und `journal_mode=WAL`. Eine Integritätsprüfung ist über
`/api/health` abrufbar (5.3, 23.3).

**Hardware hinter Adaptern.** Drucker und Schublade werden über die abstrakte
`PrinterAdapter`-Schnittstelle angesprochen. Der `MockPrinter` erlaubt den
vollständigen Ablauf ohne Gerät; `NetworkPrinter` (TCP 9100) und `UsbPrinter`
(pyusb) sind die realen Transporte (24.4, 28.2, 32.7/32.8). Die Schublade wird
gemäß 13.1 über den ESC/POS-Impuls des Bondruckers ausgelöst, nicht über GPIO.

**ESC/POS als reiner Byte-Baukasten.** `app/hardware/escpos.py` erzeugt nur
Bytefolgen und ist isoliert testbar. Kritische Werte (Schnittbefehl, Codepage,
Schubladenpins/-pulsdauer) sind Parameter und über die Oberfläche änderbar
(13.3, 14.6), weil sie am echten NS-8360L verifiziert werden müssen (4.2).

**Einstellungen in der DB, nicht im Code.** Hardware-Parameter liegen in der
Tabelle `systemeinstellung` und sind über `/api/einstellungen` änderbar. Keine
Zugangsdaten oder Gerätekonstanten im Quellcode (25.1).

**Protokollierung von Anfang an.** Testdrucke, Schubladenimpulse und
Einstellungsänderungen werden in `druckauftrag` und `audit_log` protokolliert
(16.3) — die Grundlage für die vollständige Warteschlange in Phase 4.

## Modulgrenzen (Vorbereitung auf Lastenheft 24.4)

| Modul            | Status Phase 1                                  |
| ---------------- | ----------------------------------------------- |
| Systemdiagnose   | umgesetzt (Health, Druck-/Schnitt-/Schubladentest) |
| Druck            | Grundgerüst (ESC/POS, Adapter, Warteschlange-Stub) |
| Kassenschublade  | umgesetzt (Impuls, Protokoll, manuelle Öffnung) |
| Authentifizierung| Platzhalter-Benutzer, scharf ab Phase 2         |
| Artikel/Pfand/Verkauf/Zahlung | noch nicht (Phasen 2–3)            |
| Export/Backup    | noch nicht (Phase 7)                            |
| Fiskalisierung   | Datenfelder vorgesehen, Adapter ab Phase 9      |

## Was Phase 1 bewusst noch nicht enthält

Kein Warenkorb, keine Verkäufe, keine Zahlungen, keine Auswertungen. Der
Prototyp beweist die technische Kette (Kiosk → Backend → SQLite → Drucker/
Schublade) und die harten Grundregeln (Cent-Arithmetik, WAL/Fremdschlüssel,
austauschbare Hardware-Adapter, Protokollierung). Darauf setzen die weiteren
Phasen auf.
