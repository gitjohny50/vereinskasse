# Hardware-Testprotokoll (NetumScan NS-8360L)

Diese Tests entsprechen Lastenheft 29 und müssen mit dem **echten Drucker**
bestanden werden, bevor der Transport von `mock` auf `network`/`usb` produktiv
gestellt wird. Der Prototyp liefert die Auslöser dafür bereits über den
Servicebereich und die API.

## Vorbereitung

1. Drucker anschließen (USB oder Ethernet), Papier (80 mm) einlegen.
2. Bei USB: `lsusb` ausführen, Vendor-/Product-ID notieren und in den
   Einstellungen `drucker.usb.vendor_id` / `drucker.usb.product_id` eintragen.
3. Bei Ethernet: IP im Router/Drucker festlegen, `drucker.netzwerk.host` setzen.
4. Transport auf `network` bzw. `usb` umstellen.

## 29.1 Druckertest

| Prüfpunkt | Auslöser | Erwartet |
| --- | --- | --- |
| Textdruck, Umlaute, Eurozeichen | Testseite | äöüß ÄÖÜ und € korrekt (ggf. `drucker.codepage_id` anpassen) |
| Fett / doppelte Breite / doppelte Höhe | Testseite | sichtbar unterschiedlich |
| QR-Code | Testseite | scanbar |
| Mehrere Tickets in Folge | Schnitt-Test (z. B. 20) | keine Vermischung, sauberer Ablauf |
| Papier-Ende / Abdeckung offen | manuell herbeiführen | klare Fehlermeldung, Verkauf/Test bleibt protokolliert |
| Drucker während Auftrag aus | manuell | Fehlerstatus, kein Absturz |

## 29.2 Schneidetest

- Teilschnitt nach jedem Ticket (Einstellung `schnitt.modus = partial`).
- Papiertransport vor dem Schnitt prüfen (`schnitt.vorschub_zeilen`), damit kein
  Text abgeschnitten wird.
- Verhalten bei 20+ kurzen Tickets prüfen.
- **Mindestens 100 Schnitte** im Testbetrieb (Lastenheft 29.1): Schnitt-Test
  mehrfach mit hoher Ticketzahl ausführen.

## 29.3 Kassenschubladentest

- Öffnung über den Drucker-Anschluss (`schublade.pin`, `schublade.puls_ms`).
- Genau **eine** Öffnung pro Verkauf (in Phase 1 pro Testauslösung).
- Keine Öffnung beim späteren Nachdruck (Phase 4).
- Manuelle Öffnung wird mit Benutzer, Zeit und Grund protokolliert (13.4) —
  prüfbar im Audit-Log.
- Verhalten bei ausgeschaltetem Drucker: Fehlermeldung, kein zweiter Impuls.

## Ergebnis festhalten

Jeder Testlauf erzeugt einen Eintrag in `druckauftrag` und `audit_log`. Für die
Abnahme sollten die bestandenen Punkte zusätzlich hier abgehakt und mit Datum,
Firmware-/Softwareversion und Prüfer dokumentiert werden.
