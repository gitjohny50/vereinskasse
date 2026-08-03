# Dokumentation: Frontend-Tests (`Verkauf.tsx` / `Verkauf.test.tsx`)

| Kategorie / Feature | Getesteter Aspekt | Test-Status | Beschreibung & Technische Details |
| --- | --- | --- | --- |
| **Rendering & Initialisierung** | Grundlegendes Laden | **Bestanden** | Prüft, ob die Komponente fehlerfrei rendert, die API-Daten abruft und der Haupt-Kassier-Button im leeren Zustand korrekt deaktiviert ist. |
| **Warenkorb-Interaktion** | Artikel hinzufügen | **Bestanden** | Simuliert das Antippen einer Artikelkachel, verifiziert die Aktualisierung des Gesamtbetrags und die Aktivierung des Kassieren-Buttons. |
| **Warenkorb-Interaktion** | Mengenänderung (`+`/`-`) | **Bestanden** | Testet die Stepper-Buttons innerhalb der Warenkorbzeilen und prüft die korrekte dynamische Neuberechnung über die API-Mocks. |
| **Warenkorb-Interaktion** | Warenkorb leeren | **Bestanden** | Klickt auf den "Leeren"-Button und verifiziert, dass alle Positionen gelöscht und der Ausgangszustand wiederhergestellt wird. |
| **Kategorie-Filterung** | Filter-Chips | **Bestanden** | Überprüft, ob das Anklicken von Kategorie-Chips die angezeigten Artikelkacheln im Grid korrekt einschränkt. |
| **Checkout-Ablauf** | Standard-Barzahlung | **Bestanden** | Simuliert den vollständigen modalen Workflow: Pfand-Abfrage (Nein) $\rightarrow$ Zahlungsart (Bar) $\rightarrow$ manuelle Betragseingabe $\rightarrow$ Rückgeldberechnung $\rightarrow$ erfolgreicher Abschluss. |
| **Checkout-Ablauf** | Direktzahlung (EC-Karte) | **Bestanden** | Überprüft Zahlungsarten ohne Rückgeldberechnung (`rueckgeld_berechnen: false`), bei denen der Bar-Dialog übersprungen und direkt abgeschlossen wird. |
| **Pfand-Integration** | Pfand-Rückgabe im Modal | **Bestanden** | Testet den modalen Pfand-Auswahlschritt (Antwort "Ja" auf die Pfandfrage) und das Hinzufügen von Rückgabe-Pfandarten. |
| **Fehlerbehandlung** | Zu geringer Barbetrag | **Bestanden** | Prüft, ob der Kassenabschluss blockiert wird und die korrekte Fehlermeldung ausgegeben wird, wenn der gegebene Betrag unter dem Gesamtbetrag liegt. |
| **Fehlerbehandlung** | API-Fehler beim Abschluss | **Bestanden** | Simuliert einen serverseitigen Fehler (`ApiError`) beim Verkaufsabschluss und stellt sicher, dass die Fehlermeldung im UI angezeigt wird. |
| **Offene Lücke / Bug** | Reine Pfandrückgabe (Ohne Warenkauf) | **Geskipppt (`test.skip`)** | **Status:** Dokumentiert eine Einschränkung in der aktuellen `Verkauf.tsx`-Logik. Da der Haupt-Kassieren-Button bei leerem Warenkorb deaktiviert ist, kann ohne gekaufte Artikel standardmäßig kein Checkout gestartet werden. <br>

<br>**Fehlend im Code:** Ein separater Einstiegspunkt ("Nur Pfand"-Button) für reine Auszahlungen. |
| **Offene Lücke** | Wischgeste (`SwipeKorbZeile`) | **Nicht getestet** | Die Swipe-to-Delete-Geste basiert auf nativen `PointerEvents`. Eine automatisierte Prüfung ist in der reinen `jsdom`-Testumgebung ohne visuelle/E2E-Frameworks (wie Playwright) kaum umsetzbar. |
| **Offene Lücke** | Ladezustände (`busy`-State) | **Nicht getestet** | Überprüfung, ob während eines laufenden API-Requests alle relevanten Buttons blockiert werden, um Doppelklicks zu verhindern. |

# Dokumentation: Frontend-Tests (`Artikel.tsx` / `Artikel.test.tsx`)

| Kategorie / Feature | Getesteter Aspekt | Test-Status | Beschreibung & Technische Details |
| --- | --- | --- | --- |
| **Rendering & Initialisierung** | Artikelliste laden | **Bestanden** | Prüft, ob bestehende Artikel, Kategorien und Preise beim Komponentenstart fehlerfrei in der Tabelle angezeigt werden. |
| **Fehlerbehandlung** | Initialer Ladefehler | **Bestanden** | Überprüft die korrekte Anzeige der Fehlermeldung ("Fehler beim Laden."), falls die API beim Start fehlschlägt. |
| **Artikel-Erstellung** | Neuen Artikel anlegen | **Bestanden** | Simuliert das Öffnen des Formulars, Ausfüllen der Pflichtfelder (Name, Preis, Kategorie) und Verifiziert den korrekten API-Aufruf (`artikelAnlegen`). |
| **Artikel-Erstellung** | Validierungsfehler (Leeres Formular) | **Bestanden** | Testet, dass das Absenden ohne Namen oder mit ungültigem Preis ("abc") entsprechende Fehlermeldungen ausgibt. |
| **Artikel-Bearbeitung** | Artikel bearbeiten | **Bestanden** | Öffnet den Bearbeitungsdialog für einen Artikel, ändert den Namen ("Stilles Wasser") und prüft den API-Aufruf (`artikelAendern`). |
| **Artikel-Bearbeitung** | Validierungsfehler beim Bearbeiten | **Bestanden** | Stellt sicher, dass das Leeren des Namensfelds im Dialog einen Validierungsfehler triggert und die API nicht aufgerufen wird. |
| **Artikel-Bearbeitung** | Fehlerhandling beim Speichern | **Bestanden** | Simuliert einen Serverfehler (`ApiError(500)`) beim Speichern, prüft die Fehlerausgabe im Dialog und hält das Fenster offen. |
| **Status & Verwaltung** | Aktiv/Inaktiv-Schalter | **Bestanden** | Klickt auf den Aktiv-Toggle eines Artikels und verifiziert die Deaktivierung (`aktiv: false`). |
| **Status & Verwaltung** | Artikel archivieren | **Bestanden** | Testet das Auslösen der Archivierungsfunktion über den entsprechenden Aktionsbutton. |
| **Status & Verwaltung** | Artikel duplizieren | **Bestanden** | Simuliert das Kopieren eines bestehenden Artikels an die API (`artikelKopieren`). |
| **Wartungsaktionen** | Alle Artikel archivieren | **Bestanden** | Simuliert das Bestätigen des Browser-Dialogs (`window.confirm`) und das globale Archivieren über das Wartungs-Feature. |
| **Wartungsaktionen** | Pfandzuordnungen zurücksetzen | **Bestanden** | Bestätigt den Sicherheitsdialog und prüft das Zurücksetzen aller Pfandzuordnungen im Profil. |
| **CSV-Import** | Erfolgreicher Import | **Bestanden** | Simuliert den Upload einer CSV-Datei, verifiziert die API-Parameter und die Erfolgsmeldung ("1 Artikel angelegt"). |
| **CSV-Import** | Fehlgeschlagener Import | **Bestanden** | Fängt einen API-Fehler beim Datei-Upload ab und prüft die Ausgabe der generischen Fehlermeldung. |
| **Pfand-Integration** | Pfand-Menge ändern (`menge_pro_einheit`) | **Fehlgeschlagen (`test` schlägt fehl)** | **Status:** Der Test `should handle deposit quantity changes in the create form` schlägt fehl, da beim Tippen von `12` in das numerische Pfand-Feld fälschlicherweise `112` an die API übergeben wird.<br>

<br>**Ursache im Code:** Der `onChange`-Handler interpretiert ein kurzes Leeren (`user.clear`) vorübergehend als `0`, das durch `Math.max(1, ...)` auf `1` gesetzt wird. Beim anschließenden Tippen wird die `1` angehängt.<br>

<br>**Lösung:** Den `onChange`-Handler in `Artikel.tsx` so anpassen, dass leere Strings (`''`) temporär als `1` bzw. als unbearbeiteter Zustand akzeptiert werden: |

```tsx
onChange={(e) => {
  const val = e.target.value;
  setPfand((s) => ({ ...s, [p.id]: val === '' ? 1 : Math.max(1, Number(val)) }));
}}
``` |

```





# Dokumentation: Frontend-Tests (`Auswertung.tsx` / `Auswertung.test.tsx`)

| Kategorie / Feature | Getesteter Aspekt | Test-Status | Beschreibung & Technische Details |
| --- | --- | --- | --- |
| **Rendering & Initialisierung** | Dashboard & Kennzahlen laden | **Bestanden** | Prüft, ob das Dashboard fehlerfrei lädt, die initiale API-Abfrage (`zeitreihe`) ausführt und KPIs wie Gesamtumsatz korrekt anzeigt. |
| **Fehlerbehandlung** | API-Fehler bei Datenabruf | **Bestanden** | Simuliert einen serverseitigen Fehler (`ApiError`) beim Laden der Zeitreihe und stellt sicher, dass die Fehlermeldung ausgegeben wird. |
| **Filter & Parameter** | Granularität ändern | **Bestanden** | Überprüft, ob das Umschalten des Zeitintervalls (z. B. auf "Tag") einen neuen API-Aufruf mit korrekten Parametern auslöst. |
| **Filter & Parameter** | Datumsbereich (Preset / Benutzerdefiniert) | **Bestanden** | Testet das Wechseln zu vordefinierten Bereichen ("Gestern") sowie die Eingabe benutzerdefinierter Start- und Enddaten. |
| **Filter & Parameter** | Metrik umschalten | **Bestanden** | Überprüft das Ändern der Kennzahl (z. B. "Anzahl Verkäufe") und den darauffolgenden Datenabruf. |
| **Vergleichsmodus** | Zeitraumvergleich aktivieren | **Bestanden** | Aktiviert den Vergleichsmodus ("Vergleichen") und prüft, ob die API korrekt für beide Zeiträume abgefragt wird. |
| **Interaktionen** | Drill-down über Top-Artikel | **Bestanden** | Klickt auf einen Artikel in der Drill-down-Liste und verifiziert, dass die Verkaufsliste entsprechend gefiltert wird (Beleg B-1 bleibt, B-2 wird ausgeblendet). |
| **Interaktionen** | Diagrammsegment-Klick | **Geskippt (`test.skip`)** | **Status:** Der Test `should filter sales list when a chart segment is clicked` ist derzeit übersprungen.<br>

<br>**Ursache:** Der initiale `gruppierung`-Status in `Auswertung.tsx` stand standardmäßig auf `"artikel"`. Beim ersten Klick auf den "Top-Artikel"-Button änderte sich der Status nicht, weshalb der `useEffect`-Hook für den erneuten API-Abruf leer blieb und keine Segmente im Chart gerendert wurden.<br>

<br>**Lösung / Fix:** |

1. Den initialen State in `Auswertung.tsx` von `"artikel"` auf `"keine"` setzen:
```tsx
const [gruppierung, setGruppierung] = useState<Gruppierung>("keine");

```


2. Im Test das initiale Klicken auf den "Top-Artikel"-Button explizit als User-Aktion einbauen, um den Status und den API-Aufruf für das Chart-Segment auszulösen. |



# Dokumentation: Frontend-Tests (`Belege.tsx` / `Belege.test.tsx`)

| Kategorie / Feature | Getesteter Aspekt | Test-Status | Beschreibung & Technische Details |
| --- | --- | --- | --- |
| **Rendering & Initialisierung** | Belegliste laden & anzeigen | **Bestanden** | Überprüft, ob beim Laden der Komponente die API-Methode `verkaeufe` mit der passenden Kassenprofil-ID aufgerufen wird und Belegnummer sowie Gesamtbetrag korrekt im UI gerendert werden. |
| **Interaktionen** | Belegdetails ein- und ausblenden | **Bestanden** | Testet das Aufklappen der Detailansicht eines Belegs per Klick auf "Details" (Prüfung von Positionen und gegebenem Betrag) sowie das erneute Schließen über den "Zu"-Button. |
| **Aktionen** | Beleg nachdrucken | **Bestanden** | Simuliert den Klick auf den "Nachdruck"-Button, verifiziert den API-Aufruf von `nachdruck` mit der korrekten Beleg-ID und stellt sicher, dass die Erfolgsmeldung angezeigt wird. |
| **Fehlerbehandlung** | API-Fehler beim Laden | **Bestanden** | Fängt einen simulierten serverseitigen Fehler (`ApiError(500)`) beim Abrufen der Verkäufe ab und prüft, ob die Fehlermeldung ordnungsgemäß im UI ausgegeben wird. |
| **TypeScript / Typisierung** | Vollständige Typisierung der Mocks | **Bestanden** | Das im Test verwendete `mockVerkaeufe`-Objekt wurde vollständig um alle Pflichtfelder der Typen `Verkauf`, `ZahlungInfo` und `BerechnungPosition` erweitert, sodass keine TypeScript-Fehler mehr auftreten. |