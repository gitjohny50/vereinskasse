# Phase 4 — Druckwarteschlange & Zuverlässigkeit

Phase 4 macht den Druck ausfallsicher. Ein Verkauf wird immer zuerst gebucht und
ist unveränderlich; der Druck läuft danach über eine persistente Warteschlange.
Fällt der Drucker aus (offline, Papier leer), geht der Bon nicht verloren,
sondern bleibt als Auftrag erhalten und wird automatisch oder von Hand wiederholt.

## Datenmodell

Der bestehende `Druckauftrag` wurde zur Warteschlange ausgebaut (Migration
`69b3ccccef42`): zusätzlich zu Typ, Drucker, Status und Versuchszähler speichert
er jetzt die fertigen **ESC/POS-Bytes** (`payload_b64`), ein Versuchslimit
(`max_versuche`), den Änderungszeitpunkt und den Bezug zum Verkauf
(`verkauf_id`). Weil die Bytes gespeichert sind, kann jeder Auftrag ohne
Neuberechnung wiederholt werden — auch wenn sich Stammdaten inzwischen ändern.

Statuslebenszyklus:

```
offen ──► erfolgreich
offen ──► (Fehler, Versuche < max) ──► offen
offen ──► (Fehler, Versuche = max) ──► fehlgeschlagen
offen / fehlgeschlagen ──► abgebrochen   (manuell, nur Administrator)
```

## Ablauf (`app/print_queue.py`)

- **`enqueue(...)`** legt einen Auftrag mit Status *offen* und den Druck-Bytes an.
- **`_versuch(...)`** führt genau einen Druckversuch aus, erhöht den Zähler und
  setzt den Status; Ausnahmen des Adapters werden abgefangen und als Fehler
  gewertet.
- **`verarbeite_offene(...)`** versucht alle offenen Aufträge (FIFO) — die Basis
  der automatischen Wiederholung.
- **`wiederhole(...)`** erzwingt einen weiteren Versuch, auch für fehlgeschlagene
  oder abgebrochene Aufträge (das Limit wird bei Bedarf angehoben).
- **`abbrechen(...)`** setzt einen Auftrag auf *abgebrochen* (Erfolgreiche nicht).
- **`druck_verkauf(...)` / `druck_nachdruck(...)`** bauen Bon bzw. Belegkopie und
  die Artikeltickets, reihen sie ein und versuchen sie sofort zu drucken.

Der Verkaufsabschluss ruft `druck_verkauf` auf. Schlägt der Druck fehl, bleibt
der Verkauf gebucht (Antwort 201) und die Aufträge liegen zur Wiederholung bereit.

## API (`/api/druckwarteschlange`, ab Bediener)

- `GET /` — Aufträge, optional gefiltert (`?status=offen,fehlgeschlagen`).
- `GET /status` — Zähler je Status.
- `POST /verarbeiten` — alle offenen Aufträge erneut versuchen.
- `POST /{id}/wiederholen` — einen Auftrag von Hand wiederholen.
- `POST /{id}/abbrechen` — Auftrag abbrechen (nur Administrator).

## Oberfläche

Neuer Reiter **Drucke** (ab Bediener) mit Statusübersicht (offen /
fehlgeschlagen / erfolgreich / abgebrochen), Auftragsliste mit Fehlermeldung und
Versuchszähler sowie den Aktionen „Jetzt verarbeiten", „Wiederholen" und
(für Administratoren) „Abbrechen". Die Seite pollt regelmäßig und stößt dabei die
automatische Wiederholung offener Aufträge an. Am Reiter zeigt ein rotes
Abzeichen die Zahl offener plus fehlgeschlagener Aufträge.

## Tests

`tests/test_druckwarteschlange.py` (7 Tests) prüft mit einem absichtlich
fehlschlagenden Drucker: Einreihung von Bon und Tickets beim Verkauf,
Wiederholung bis zum Limit mit anschließendem Status *fehlgeschlagen*, erfolgreiche
manuelle Wiederholung, Sammelverarbeitung offener Aufträge, Abbruch (und dass
erfolgreiche Aufträge nicht abgebrochen werden können) sowie die Rollenprüfung
(Abbrechen nur Administrator). Gesamtsuite: **64 Tests grün**.
