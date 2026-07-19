# API-Dauertest fuer Kasse, Drucker und Schublade

Dieses Szenario testet die Kasse ueber die echte API. Es ist bewusst als
externes Skript umgesetzt, damit auf dem Raspberry Pi kein versteckter
Produktiv-Endpunkt existiert, der versehentlich Buchungen ausloest.

Wichtig: Der Test erzeugt echte Verkaeufe, echte Druckauftraege und bei
passender Zahlungsart echte Schubladenimpulse. Nutze dafuer am besten ein
eigenes Test-Kassenprofil oder fuehre danach einen klar markierten Z-Abschluss
fuer den Testzeitraum aus.

## Vorbereitung

1. Backend auf dem Pi starten.
2. Drucker einschalten, Papierrolle einlegen, Cutter freihalten.
3. Kassenschublade anschliessen.
4. Mindestens einen aktiven Artikel und eine aktive Zahlungsmethode im
   Kassenprofil anlegen.
5. Fuer den vollstaendigen Hardwaretest mit einem Service- oder Admin-Benutzer
   anmelden, weil die Diagnose-Endpunkte geschuetzt sind.

Benutzer-IDs kannst du bei Bedarf so anzeigen:

```bash
curl http://127.0.0.1:8000/api/auth/benutzerliste
```

## Szenario 1: Abnahmetest

Der Abnahmetest prueft gezielt die wichtigsten Funktionen in einer festen
Reihenfolge:

1. Login und Rechtepruefung.
2. Druckerstatus lesen.
3. Drucker-Testseite senden.
4. Cutter mehrfach ausloesen.
5. Kassenschublade oeffnen.
6. Einen Testverkauf buchen.
7. Original-Beleg anfordern.
8. Nachdruck anfordern.
9. Druckwarteschlange verarbeiten und Status ausgeben.

Start:

```bash
python3 tools/api_kassen_test.py \
  --base-url http://127.0.0.1:8000 \
  --user-id 1 \
  --pin 1234 \
  --profil-id 1 \
  --modus abnahme \
  --schnitt-anzahl 3 \
  --ich-weiss-dass-gebucht-wird
```

Erwartung:

- Testseite kommt vollstaendig aus dem Drucker.
- Alle Schnitte sind sauber.
- Die Schublade oeffnet einmal durch den Diagnoseimpuls.
- Beim Barverkauf oeffnet die Schublade erneut, wenn die Zahlungsart so
  konfiguriert ist.
- Beleg und Nachdruck sind vollstaendig und haben die korrekte Uhrzeit.
- Am Ende meldet die Druckwarteschlange `offen=0` und `fehlgeschlagen=0`.

## Szenario 2: 1-Stunden-Dauertest

Der Dauertest bucht ueber eine definierte Zeit immer wieder zufaellige Warenkoerbe.
Dabei werden aktive Artikel aus dem gewaehlten Kassenprofil verwendet. Das Skript
wechselt zwischen einer Zahlungsart mit Schubladenimpuls und einer ohne
Schubladenimpuls, sofern beides vorhanden ist. Die Pause zwischen den Buchungen
wird zufaellig variiert, damit der Drucker nicht nur einen kuenstlichen
Metronom-Takt sieht.

Empfohlener 1-Stunden-Test mit wechselnden Intervallen und gelegentlichem
zusaetzlichem Belegbon:

```bash
python3 tools/api_kassen_test.py \
  --base-url http://127.0.0.1:8000 \
  --user-id 1 \
  --pin 1234 \
  --profil-id 1 \
  --modus dauer \
  --dauer-minuten 60 \
  --intervall-min-sekunden 5 \
  --intervall-max-sekunden 45 \
  --beleg-jeder-n 7 \
  --beleg-wahrscheinlichkeit 0.20 \
  --ich-weiss-dass-gebucht-wird
```

Beispiel fuer einen kurzen Probelauf mit maximal 10 Buchungen:

```bash
python3 tools/api_kassen_test.py \
  --base-url http://127.0.0.1:8000 \
  --user-id 1 \
  --pin 1234 \
  --profil-id 1 \
  --modus dauer \
  --dauer-minuten 15 \
  --intervall-min-sekunden 2 \
  --intervall-max-sekunden 8 \
  --max-verkaeufe 10 \
  --beleg-jeder-n 3 \
  --ich-weiss-dass-gebucht-wird
```

Waehrend des Laufs protokolliert das Skript je Verkauf:

- laufende Nummer,
- Belegnummer,
- Betrag,
- verwendete Zahlungsart,
- gebuchte Artikel,
- ob ein zusaetzlicher Belegbon angefordert wurde,
- Status der Druckwarteschlange.

Parameter fuer den Druck-Mix:

- `--intervall-min-sekunden` und `--intervall-max-sekunden`: zufaellige Pause
  zwischen zwei Buchungen.
- `--beleg-jeder-n`: jeder n-te Verkauf bekommt sicher einen zusaetzlichen
  Original-Belegbon.
- `--beleg-wahrscheinlichkeit`: Zusatzchance pro Verkauf fuer einen Belegbon.
- `--seed`: optional, wenn ein Lauf reproduzierbar wiederholt werden soll.

## Bewertung

Ein Lauf gilt als bestanden, wenn:

- keine API-Fehler auftreten,
- keine Druckauftraege dauerhaft offen bleiben,
- keine Druckauftraege fehlgeschlagen sind,
- Belege nicht abgeschnitten oder halb gedruckt werden,
- der Cutter bei jedem Beleg sauber trennt,
- die Schublade bei Zahlungsarten mit `schublade_oeffnen=true` zuverlaessig
  ausloest,
- die Beleg-Uhrzeit zur lokalen Uhrzeit des Pi passt.

Wenn der erste Bon wieder halb gedruckt wird, ist der Abnahmetest besonders
wertvoll: Dann sieht man, ob schon die Testseite betroffen ist oder erst der
erste echte Verkauf. Das grenzt Drucker-Wakeup, Cutter/Feed und Verkaufsausdruck
sauber voneinander ab.
