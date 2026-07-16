# Phase 2 — Stammdaten

Phase 2 baut auf dem technischen Prototyp auf und liefert die Stammdatenebene:
Benutzer und Rollen mit PIN-Anmeldung, Vereine, Kassenprofile, Veranstaltungen,
Kategorien, Artikel, Pfandarten und Zahlungsmethoden. Gemäß Lastenheft 32.4
stehen Datenmodell und Migrationen vor der Oberfläche.

## Was neu ist

- Datenmodell für alle Stammdaten (`app/models.py`), Katalogdaten sind einem
  Kassenprofil zugeordnet (Lastenheft 7.1).
- Anmeldung per PIN (`app/security.py`, `app/auth.py`): PINs werden mit
  PBKDF2-HMAC-SHA256 und zufälligem Salt gespeichert, nie im Klartext
  (Lastenheft 6.4). Fehlversuche werden gezählt und nach fünf Versuchen wird der
  Benutzer gesperrt; Sitzungen laufen nach Inaktivität ab.
- Rollen mit Rechtestufen: Bediener (10), Administrator (20), Servicetechniker
  (30). Diagnose erfordert Stufe 30, Einstellungen und Stammdatenpflege Stufe 20.
- CRUD-APIs mit den geforderten Regeln: Artikel werden archiviert statt gelöscht
  (8.2), Artikel kopieren ohne Nummer/Barcode (8.3), Reihenfolge (8.4),
  Sammelbearbeitung (8.5). Preise wandern ausschließlich als Cent-Ganzzahlen
  über die Schnittstelle.
- Alembic-Migrationen (`backend/alembic/`) als versionierter Schemapfad.
- Oberfläche: Anmeldebildschirm mit PIN-Pad und die Artikelverwaltung
  (Liste, Anlegen mit Kategorie und Pfand, Preis-Inline-Bearbeitung, Aktiv-
  Schalter, Kopieren, Archivieren).

## Erst-Administrator

Beim ersten Start wird — nur wenn noch kein Benutzer existiert — ein
Administrator angelegt. Die Start-PIN kommt aus `VK_INITIAL_ADMIN_PIN` oder wird
zufällig erzeugt und einmalig in das Log geschrieben. Sie **muss** im
Produktivbetrieb geändert werden (Lastenheft 25.1, keine Standardpasswörter):

```bash
VK_INITIAL_ADMIN_PIN=246810 VK_DATA_DIR=/opt/vereinskasse-daten \
  .venv/bin/uvicorn app.main:app --port 8000
```

Zusätzlich wird ein Demo-Kassenprofil „Vereinsfest“ mit Beispielsortiment
angelegt. Es kann bearbeitet oder ersetzt werden.

## Migrationen

Auf dem Raspberry Pi ist `alembic upgrade head` der Weg zum aktuellen Schema:

```bash
cd backend
VK_DATA_DIR=/opt/vereinskasse-daten .venv/bin/alembic upgrade head
```

In Entwicklung und Tests werden die Tabellen direkt aus den Modellen erzeugt.
Nach Modelländerungen eine neue Revision erzeugen:

```bash
.venv/bin/alembic revision --autogenerate -m "beschreibung"
```

## Rollen und Endpunkte (Auszug)

| Bereich | Endpunkt | Mindeststufe |
| --- | --- | --- |
| Anmeldung | `POST /api/auth/login`, `GET /api/auth/benutzerliste` | offen |
| Eigene Sitzung | `GET /api/auth/me`, `POST /api/auth/logout` | angemeldet |
| Benutzer/Rollen | `GET/POST/PUT /api/benutzer`, `GET /api/rollen` | Administrator |
| Profile/Veranstaltungen | `GET /api/kassenprofile`, `/api/veranstaltungen` | Bediener (lesen) |
| Stammdaten schreiben | `POST/PUT` auf Profile, Katalog | Administrator |
| Artikel | `GET /api/artikel`, `POST /api/artikel/...` | Bediener (lesen) / Admin (schreiben) |
| Diagnose | `/api/diagnose/...` | Servicetechniker |

## Nächste Schritte

Die übrigen Verwaltungsmasken (Benutzer, Profile, Veranstaltungen, Kategorien,
Pfandarten, Zahlungsmethoden) nutzen dieselben, bereits vorhandenen APIs und
folgen dem Muster der Artikelverwaltung. Danach steht Phase 3 an: Verkauf mit
Warenkorb, automatischer Pfandberechnung, Zahlungen und Bon-/Artikelticketdruck.

## Phase 2.1 — Oberfläche für alle Stammdaten

Phase 2.1 ergänzt die Weboberfläche für die bereits vorhandenen APIs, sodass die
komplette Stammdatenpflege ohne Umweg über die API möglich ist. Neue Reiter
(alle ab Administrator, Stufe 20):

- **Artikel** – wie bisher (Liste, Anlegen mit Kategorie und Pfand, Preis-Inline-
  Bearbeitung, Aktiv-Schalter, Kopieren, Archivieren).
- **Kategorien** – Anlegen mit Farbe und Sortierung, Umbenennen, Aktiv-Schalter.
- **Pfand** – Pfandarten mit Betrag (in Euro erfasst, als Cent gespeichert),
  Rückgabe- und Artikelticket-Option, Aktiv-Schalter.
- **Zahlarten** – Zahlungsmethoden mit den Schaltern Schublade öffnen, Rückgeld
  berechnen, Negativbeträge, Aktiv.
- **Veranstaltungen** – Vereine, Kassenprofile und Veranstaltungen inklusive
  Statuswechsel (geplant → aktiv → abgeschlossen → archiviert).
- **Benutzer** – Anlegen mit Rolle und PIN, Rollenwechsel, Aktiv-Schalter und
  PIN-Zurücksetzen (hebt zugleich eine Sperre nach Fehlversuchen auf).

Ein gemeinsamer Umschalter „Aktives Kassenprofil“ oben steuert, für welches
Profil die katalogbezogenen Reiter (Artikel, Kategorien, Pfand, Zahlarten)
gelten.

Kleine Backend-Ergänzung dazu: Die Eingabeschemata von Kategorie, Pfandart und
Zahlungsmethode erhielten das Feld `aktiv`, damit sich diese Einträge über die
Oberfläche deaktivieren und wieder aktivieren lassen.
