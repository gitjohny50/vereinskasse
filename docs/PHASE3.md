# Phase 3 — Verkauf (Kasse)

Phase 3 macht die Vereinskasse zur echten Kasse: Warenauswahl per Touch,
automatische Pfandberechnung, Zahlung mit Rückgeld, unveränderlicher Beleg mit
fortlaufender Belegnummer sowie Bon- und Artikelticket-Druck mit Schubladenimpuls.

## Datenmodell (zuerst, dann Logik — Lastenheft 32.4)

Vier neue Tabellen (Migration `d721d2ce1511_phase3_verkauf`):

- **Belegkreis** – je Kassenprofil ein fortlaufender Zähler (`letzte_nummer`).
  Die Belegnummer wird beim Abschluss atomar hochgezählt und als sechsstellige
  Zeichenkette vergeben (`000001`).
- **Verkauf** – Kopf mit `belegnummer`, Profil, optionaler Veranstaltung,
  Bediener, Zeitpunkt, `waren_cent`, `pfand_cent`, `gesamt_cent`, `status`.
  Eindeutig je (Kassenprofil, Belegnummer).
- **Verkaufsposition** – Zeilen vom Typ `artikel`, `pfand` oder
  `pfand_rueckgabe`. Bezeichnung, Einzelpreis, Menge, Gesamt (vorzeichenbehaftet),
  Ticketmodus und Steuersatz werden als **Momentaufnahme** gespeichert, damit der
  Beleg unveränderlich bleibt, auch wenn sich Artikel später ändern.
- **Zahlung** – Zahlungsmethode, zugeordneter Betrag, gegebener Betrag, Rückgeld.

## Ablauf

`app/sales.py` trennt Berechnung und Abschluss:

- **`berechne(...)`** prüft, ob Artikel verkäuflich sind (aktiv, nicht archiviert,
  richtiges Profil), ergänzt automatisch Pfandpositionen aus den
  Artikel-Pfand-Zuordnungen (sofern `automatisch`), berücksichtigt
  Pfandrückgaben (negative Positionen, begrenzt durch `max_rueckgabe_menge`) und
  liefert Waren-, Pfand- und Gesamtsumme. Ist bei einer Veranstaltung
  `pfand_aktiv = false`, entfällt der automatische Pfand.
- **`finalisiere(...)`** rechnet serverseitig neu (nie der Client-Summe vertrauen),
  prüft die Zahlungsmethode, verlangt bei Rückgeld-Methoden ausreichend Bargeld
  (sonst 422), erlaubt Negativbeträge nur bei entsprechend gekennzeichneter
  Methode, vergibt die Belegnummer und schreibt Verkauf, Positionen, Zahlung und
  einen Audit-Eintrag. Der Druck erfolgt danach „best effort" (ein Druckfehler
  macht den Verkauf nicht rückgängig).

## Druck (`hardware/service.py`)

- **`build_receipt_bytes(...)`** erzeugt den Bon: Bonkopf, Beleg-Nr, Datum,
  Bediener, Positionen, Waren/Pfand/GESAMT, Zahlung/Rückgeld, Bonfuß,
  Teilschnitt und — bei Barzahlung mit Schubladen-Methode — Schubladenimpuls.
- **Artikeltickets** je nach Modus: `pro_stueck` = ein Ticket je Stück,
  `pro_position` = ein Ticket je Position, `kein` = keins. Jedes Ticket mit
  Teilschnitt. Pfandpositionen erzeugen keine Tickets.
- **`run_verkauf_nachdruck(...)`** druckt eine als „KOPIE / NACHDRUCK"
  gekennzeichnete Belegkopie ohne Schubladenimpuls und ohne Tickets.

## API (`/api/verkauf`, Rolle Bediener genügt)

- `POST /berechnung` – Vorschau (Positionen + Summen), ohne zu speichern.
- `POST /` – Verkauf abschließen (201). Serverseitige Neuberechnung, Belegnummer,
  Druck.
- `GET /` – Belegliste (Filter `kassenprofil_id`).
- `GET /{id}` – Belegdetail.
- `POST /{id}/nachdruck` – Belegkopie drucken.
- **Kein** `PUT`/`DELETE` – Verkäufe sind unveränderlich (405).

## Oberfläche

- **Verkauf** (Reiter, ab Bediener): Kategorie-Filter, Artikelkacheln,
  Warenkorb mit Mengensteuerung, Live-Berechnung inkl. automatischem Pfand,
  Zahlungsmethodenwahl, Bar-Eingabe mit Schnellbeträgen und Rückgeldanzeige,
  Abschluss mit Belegnummer und Nachdruck. Optionale Veranstaltungswahl.
- **Belege** (Reiter, ab Bediener): Belegliste mit aufklappbarem Detail und
  Nachdruck.

Ein Verkauf ist damit vollständig offline möglich; ohne echte Hardware rendert
der Mock-Drucker Bon und Tickets inklusive `[TEILSCHNITT]`- und
`[SCHUBLADE-IMPULS]`-Markierungen in die Log-Datei.

## Tests

`tests/test_verkauf.py` (10 Tests) deckt ab: automatische Pfandberechnung,
Barzahlung mit Rückgeld, fortlaufende Belegnummern, zu wenig Bargeld (422),
Kartenzahlung ohne Rückgeld, Pfandrückgabe, Negativbetrag nur bei erlaubter
Methode, Veranstaltung mit deaktiviertem Pfand, Unveränderlichkeit (405) sowie
Nachdruck und Liste. Gesamtsuite: **57 Tests grün**.
