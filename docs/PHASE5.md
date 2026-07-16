# Phase 5 — Kassenabschluss (X- und Z-Bericht)

Phase 5 ergänzt den Tages-/Schichtabschluss: einen **X-Bericht** als
Zwischenstand (ändert nichts) und einen **Z-Bericht** als verbindlichen
Abschluss, inklusive Kassensturz (Soll/Ist-Vergleich des Bargelds) und
Aufschlüsselung nach Zahlart und Artikel.

## Datenmodell (Migration `2c7393097a67`)

- **Kassenabschluss** — ein Z-Bericht. Speichert Nummer (`Z-0001`, fortlaufend je
  Kassenprofil), Zeitraum (von/bis), erstellenden Benutzer, die Summen
  (Verkäufe, Waren, Pfand, Gesamt, Bar) sowie den Kassensturz
  (Anfangsbestand, erwartet, gezählt, Differenz). Unveränderlich.
- **KassenabschlussZahlart** — je Zahlart eine Zeile mit Anzahl, Betrag und
  Bar-Kennzeichen (Momentaufnahme).
- **Verkauf.abschluss_id** — ordnet jeden Verkauf genau einem Z-Bericht zu.
  Offene Verkäufe (`abschluss_id IS NULL`) bilden den aktuellen Zeitraum.

## Ablauf (`app/reports.py`)

- **`x_bericht(...)`** aggregiert die noch offenen Verkäufe eines Profils, ohne
  etwas zu ändern: Summen, Aufschlüsselung nach Zahlart und Artikel,
  Bar-Umsatz und – mit optionalem Anfangsbestand – der erwartete Kassenbestand.
- **`erstelle_z(...)`** bildet dieselbe Aggregation, vergibt die nächste
  Z-Nummer, speichert Kassenabschluss samt Zahlart-Zeilen, setzt bei allen
  betroffenen Verkäufen `abschluss_id` (schließt sie ab), schreibt einen
  Audit-Eintrag und druckt den Bericht über die Druckwarteschlange.
- **Kassensturz**: `erwartet = Anfangsbestand + Bar-Umsatz`,
  `Differenz = gezählt − erwartet`. Als „bar" gelten Zahlarten, die die
  Schublade öffnen (`schublade_oeffnen`).
- **`abschluss_bericht(...)`** rekonstruiert einen gespeicherten Z-Bericht;
  **`druck_bericht(...)`** reiht ihn (erneut) in die Druckwarteschlange ein.

## API (`/api/abschluss`, nur Administrator)

- `GET /x?kassenprofil_id=&anfangsbestand_cent=&gezaehlt_cent=` — X-Zwischenstand.
- `POST /z` — Z-Abschluss erstellen (Body: Profil, Anfangsbestand, gezählt).
- `GET /` — Liste bisheriger Abschlüsse.
- `GET /{id}` — gespeicherter Z-Bericht.
- `POST /{id}/nachdruck` — Bericht erneut drucken.

## Oberfläche

Neuer Reiter **Abschluss** (nur Administrator): oben der aktuelle Stand
(X-Bericht) mit Summen, Aufschlüsselung nach Zahlart, den Kassensturz-Feldern
(Anfangsbestand, gezähltes Bargeld) und der live berechneten Differenz. Der
Z-Abschluss wird mit Sicherheitsabfrage ausgelöst; danach erscheint das Ergebnis
mit Nachdruck-Möglichkeit. Darunter die Liste bisheriger Abschlüsse mit Detail
(inklusive Artikelaufstellung) und Nachdruck.

## Tests

`tests/test_kassenabschluss.py` (7 Tests): X-Zwischenstand mit Bar/Unbar-Trennung
und erwartetem Bestand, Z-Abschluss mit Zuordnung der Verkäufe (danach nichts
mehr offen), Kassensturz-Differenz, zweiter Z-Bericht nur über neue Verkäufe,
Erzeugung des Druckauftrags, Nachdruck und Rollenprüfung (nur Administrator).
Gesamtsuite: **71 Tests grün**.
