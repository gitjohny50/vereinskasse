# CI/CD Pipeline Dokumentation

Dieses Dokument beschreibt die Continuous Integration (CI) Pipeline des Projekts, die mit [GitHub Actions](https://github.com/features/actions) eingesetzt und implementiert wird. Die Pipeline dient dazu, die Code-Qualität bei jeder Code-Änderung automatisch zu überprüfen, Sicherheitslücken aufzudecken und sicherzustellen, dass das Projekt stabil und fehlerfrei bleibt.

Die Konfiguration befindet sich in der Datei `.github/workflows/ci.yml`.

## Auslöser der Pipeline

Die Pipeline wird automatisch in den folgenden Fällen gestartet:

* Bei jedem **Push** auf die Branches `main`, `dev` und `cicd-pipline`.
* Beim Erstellen oder Aktualisieren eines **Pull Requests**, der auf die Branches `main`, `dev` oder `cicd-pipline` zielt.

## Übersicht der Jobs

Die Pipeline besteht aus zwei unabhängigen Jobs, die parallel ausgeführt werden, um die Durchlaufzeit zu verkürzen:

1. `backend-ci`: Überprüft das Python-Backend und scannt nach Schwachstellen.
2. `frontend-ci`: Überprüft das TypeScript/React-Frontend und scannt nach Schwachstellen.

Wenn einer dieser Jobs fehlschlägt, wird der gesamte Pipeline-Lauf als fehlgeschlagen markiert.

---

## Backend-Pipeline (`backend-ci`)

Dieser Job stellt sicher, dass der Backend-Code korrekt, sauber formatiert, gut getestet und frei von bekannten Sicherheitslücken in den Abhängigkeiten ist. Er läuft auf einer `ubuntu-latest` Umgebung im Verzeichnis `./backend`.

**Schritte im Detail:**

1. **Code auschecken:** Lädt die aktuellste Version des Codes in die virtuelle Umgebung von GitHub.
2. **Python einrichten:** Installiert die für das Projekt spezifizierte Python-Version (3.12).
3. **Abhängigkeiten installieren:** Installiert alle für das Projekt notwendigen Python-Pakete aus der `requirements.txt` sowie die für die Tests und das Linting benötigten Tools (`pytest`, `pytest-cov`, `ruff`).
4. **Code-Stil prüfen (Linting):** Führt `ruff check` aus, um den Code auf Stilfehler, Inkonsistenzen und ungenutzte Importe zu überprüfen. Dies sorgt für einen konsistenten und lesbaren Code.
5. **Tests & Coverage ausführen:** Startet die Test-Suite mit `pytest`. Gleichzeitig wird mit `pytest-cov` ein XML-Report über die Testabdeckung generiert.
6. **SBOM generieren:** Nutzt das Tool Syft (via `anchore/sbom-action`), um eine Software Bill of Materials (SBOM) im standardisierten CycloneDX-Format (`backend.cdx.json`) zu erstellen. Diese Liste erfasst alle verwendeten Software-Komponenten.
7. **Sicherheits-Scan durchführen:** Lädt das aktuelle Binary des Google OSV-Scanners herunter und prüft die generierte SBOM automatisch auf bekannte Sicherheitslücken (Vulnerabilities).

---

## Frontend-Pipeline (`frontend-ci`)

Dieser Job validiert den Frontend-Code, prüft die NPM-Abhängigkeiten auf Sicherheit und stellt sicher, dass die Anwendung fehlerfrei gebaut werden kann. Er läuft ebenfalls auf einer `ubuntu-latest` Umgebung im Verzeichnis `./frontend`.

**Schritte im Detail:**

1. **Code auschecken:** Lädt die aktuellste Version des Codes herunter.
2. **SBOM generieren (Pre-Install):** Erstellt die Software Bill of Materials (SBOM) im CycloneDX-Format (`frontend.cdx.json`). *Hinweis: Dieser Schritt wird bewusst vor der Installation der NPM-Pakete ausgeführt. So wird verhindert, dass interne Compiler-Werkzeuge aus dem `node_modules`-Ordner das Scan-Ergebnis verfälschen.*
3. **Sicherheits-Scan durchführen:** Prüft die generierte SBOM mit dem Google OSV-Scanner auf bekannte Sicherheitslücken in den projektspezifischen Frontend-Abhängigkeiten.
4. **Node.js einrichten:** Installiert die spezifizierte Node.js-Version (20). Der `npm`-Cache wird aktiviert, um die Installationszeiten bei wiederholten Läufen zu beschleunigen.
5. **Abhängigkeiten installieren:** Führt `npm ci` aus. Dieser Befehl ist schneller und sicherer für CI-Umgebungen als `npm install`, da er zwingend die exakten Versionen aus der `package-lock.json` installiert.
6. **Code-Stil prüfen (Linting):** Führt `npm run lint` aus, was wiederum ESLint startet. ESLint überprüft den Code auf Fehler und Stilprobleme.
7. **Projekt bauen (Build):** Führt `npm run build` aus. Dieser Schritt kompiliert den Code für die Produktion. Ein erfolgreicher Build bestätigt, dass es keine Typ- oder Syntaxfehler gibt, die die Kompilierung verhindern würden.





## Geplante Erweiterungen (Future Work)

Um die CI/CD-Pipeline in Zukunft noch robuster und näher an der Produktionsumgebung zu gestalten, sind folgende Ausbaustufen möglich:

### 1. Datenbank-Integration für Integrationstests
- **Service Container:** Einbindung einer echten temporären Datenbank (z. B. PostgreSQL oder SQLite/MySQL) über GitHub Actions Service Container.
- **Isolierte Testumgebung:** Die Pipeline startet den Datenbank-Container vor den Backend-Tests, führt `pytest` gegen diese echte Datenbank aus und löscht sie nach dem Job restlos.
- **Vorteil:** Echte Integrationstests statt simulierter (gemockter) Datenbankverbindungen.

### 2. Deployment-Vorbereitung für Raspberry Pi (ARM-Architektur)
- **Option A - Cross-Compiling:** Nutzung von Tools wie *Docker Buildx* innerhalb der Ubuntu-Runner, um den Code explizit für die ARM-Architektur (`arm64`) des Raspberry Pi zu bauen.
- **Option B - Self-Hosted Runner:** Registrierung des Ziel-Raspberry-Pi als eigenen Runner in GitHub Actions (`runs-on: self-hosted`).
- **Vorteil:** Die Pipeline-Jobs oder Deployment-Schritte laufen direkt auf der echten Hardware ab, was Architektur-Konflikte ausschließt.
### 3. Containerisierung (Docker)
- **Automatisierte Image-Builds:** Erweiterung der Pipeline um Schritte, die aus dem getesteten Code fertige Docker-Images für Backend und Frontend bauen.
- **Image-Registry:** Hochladen (Push) der fertigen Images in eine Registry wie GitHub Packages oder Docker Hub.
- **Vorteil:** Extrem leichtes und konsistentes Deployment auf dem Zielsystem (Raspberry Pi), da alle Abhängigkeiten gekapselt sind.

### 4. Continuous Deployment (CD)
- **Automatisches Ausrollen:** Einrichtung eines CD-Jobs, der nur bei einem Push auf den `main`-Branch aktiv wird und die neue Version automatisch auf den Raspberry Pi überträgt (z.B. via SSH, Ansible oder Watchtower).
- **Vorteil:** Der manuelle Aufwand für Updates entfällt komplett; jede freigegebene Änderung ist sofort live.

### 5. End-to-End (E2E) Testing
- **Browser-Automatisierung:** Integration von Tools wie *Playwright* oder *Cypress* in einem separaten Pipeline-Job.
- **Zusammenspiel testen:** Starten von Frontend, Backend und Datenbank in der CI, um echte Klickpfade von Benutzern im Browser zu simulieren.
- **Vorteil:** Stellt sicher, dass nicht nur isolierte Funktionen (Unit-Tests), sondern das gesamte System im Zusammenspiel fehlerfrei funktioniert.

### 6. Static Application Security Testing (SAST)
- **Erweiterte Code-Analyse:** Einbindung von Tools wie *GitHub CodeQL* oder *SonarQube*.
- **Vorteil:** Während der aktuelle OSV-Scanner Fremdpakete auf Schwachstellen prüft, scannen SAST-Tools deinen *selbstgeschriebenen* Quellcode auf logische Sicherheitslücken (z.B. SQL-Injections) und Architekturfehler, die über einfaches Linting hinausgehen.
### 7. Hardware-Integration & Hardware-in-the-Loop (HIL)
- **Drucker-Simulation (Mocking):** Erweiterung der Backend-Tests (`pytest`), um die `pyusb`-Aufrufe zu simulieren. So wird die Kassenlogik für den USB-Bondrucker in der Cloud-CI getestet, ohne dass physische Hardware angeschlossen sein muss.
- **Physische Hardware-Tests (HIL):** Nutzung eines Self-Hosted Runners (Raspberry Pi) mit lokal angeschlossenem USB-Bondrucker. Die Pipeline kann so konfiguriert werden, dass sie nach erfolgreichem Deployment verifiziert, ob die `libusb`-Abhängigkeiten sowie die `udev`-Rechte korrekt gesetzt sind, und automatisiert eine Testseite druckt.
- **Validierung von Systemdateien:** Die CI kann automatisiert prüfen, ob Dateien wie die `99-vereinskasse-usb.rules` syntaktisch korrekt formatiert sind, bevor sie auf das Zielsystem ausgerollt werden.