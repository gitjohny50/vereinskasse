# Stresstest-Suite für die Vereinskasse

Diese Test-Suite dient dazu, die Stabilität und Performance des **Vereinskasse-Backends** unter Last zu prüfen und potenzielle Concurrency-Probleme (Race Conditions) zu identifizieren.

## 1. Komponenten

* **`seed_test_data.py`**: Initialisiert eine saubere Testumgebung (Admin-Login, Erstellung von Kassenprofil, Veranstaltungen, Artikeln und Test-Usern). Dies ist essenziell, da das Backend für valide Verkäufe spezifische Stammdaten benötigt.
* **`locustfile.py`**: Definiert das Lastprofil. Es simuliert reale Anwendungsfälle (Verkauf tätigen, Historie einsehen, Druckwarteschlange verwalten).
* **`stress-test.yml`**: Die GitHub Actions Konfiguration für die automatisierte Pipeline.

## 2. Lokaler Start

Bevor du den Test startest, muss das Backend laufen.

1. **Backend starten**:
```bash
# Im Verzeichnis /vereinskasse/backend
VK_INITIAL_ADMIN_PIN=123456 VK_DATA_DIR=$(mktemp -d) uvicorn app.main:app --reload

```


2. **Test-Daten vorbereiten** (Einmalig pro Backend-Start):
```bash
python tests/stresstests/seed_test_data.py

```


3. **Locust starten**:
```bash
locust -f tests/stresstests/locustfile.py --host=http://127.0.0.1:8000

```


4. **Web-UI bedienen**:
* Öffne `[http://0.0.0.0:8089](http://0.0.0.0:8089)` im Browser.
* **Number of users**: z.B. `50`
* **Spawn rate**: z.B. `5`
* Klicke auf **"Start swarming"**.



## 3. Automatisierte CI/CD Pipeline

Die Pipeline ist so konfiguriert, dass sie bei jedem manuellen Start (`workflow_dispatch`) die Umgebung vollständig isoliert aufbaut.

* **Isolierung**: Es wird bei jedem Lauf ein frischer temporärer Datenbank-Ordner (`mktemp -d`) erstellt.
* **Seeding**: Das Skript `seed_test_data.py` stellt sicher, dass alle für den Stresstest notwendigen Abhängigkeiten in der frischen DB existieren.
* **Fehlertoleranz**: In der `locustfile.py` ist ein Listener implementiert. Wenn die Fehlerrate **über 60 %** liegt, bricht die Pipeline mit Fehlercode `1` ab. Bei einer Fehlerrate unter 60 % gilt der Test als "bestanden" (Exit-Code `0`), um trotz bekannter Concurrency-Bugs (wie bei der `belegnummer`) eine grüne Pipeline für weitere Features zu erhalten.

## 4. Funktionsweise der Tests

Der Stresstest nutzt den `OperatorUser`, welcher:

* Sich beim Start (`on_start`) mit einem zufälligen Benutzer aus dem Pool authentifiziert.
* Authentifizierte Requests mit `Bearer Token` sendet.
* Über das `@task`-System zufällig verschiedene Aktionen ausführt, wobei der **Verkaufsprozess** (`create_sale`) mit der höchsten Priorität (`@task(15)`) gewichtet ist, um gezielt Last auf die Datenbank-Schreibvorgänge (Race Conditions) zu erzeugen.

---

**Hinweis zur Fehlerbehebung**: Solltest du im CI-Log "500 Internal Server Error" sehen, deutet dies auf eine `IntegrityError` in der Datenbank hin. Dies ist bei einer Last von 50 gleichzeitigen Benutzern ein erwartetes Verhalten bei der aktuellen `belegnummer`-Generierung und wurde im Rahmen der Test-Strategie bewusst als akzeptiertes Risiko definiert.