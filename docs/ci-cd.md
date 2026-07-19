# CI/CD Pipeline Dokumentation

Dieses Dokument beschreibt die Continuous Integration (CI) Pipeline des Projekts, die mit [GitHub Actions](https://github.com/features/actions) realisiert wird. Die Pipeline dient dazu, die Code-Qualität bei jeder Code-Änderung automatisch zu überprüfen und sicherzustellen, dass das Projekt stabil und fehlerfrei bleibt.

Die Konfiguration befindet sich in der Datei `.github/workflows/ci.yml`.

## Auslöser der Pipeline

Die Pipeline wird automatisch in den folgenden Fällen gestartet:

- Bei jedem **Push** auf den `main`-Branch.
- Beim Erstellen oder Aktualisieren eines **Pull Requests**, der auf den `main`-Branch zielt.

## Übersicht der Jobs

Die Pipeline besteht aus zwei unabhängigen Jobs, die parallel ausgeführt werden, um die Durchlaufzeit zu verkürzen:

1.  `backend-ci`: Überprüft das Python-Backend.
2.  `frontend-ci`: Überprüft das TypeScript/React-Frontend.

Wenn einer dieser Jobs fehlschlägt, wird der gesamte Pipeline-Lauf als fehlgeschlagen markiert.

---

## Backend-Pipeline (`backend-ci`)

Dieser Job stellt sicher, dass der Backend-Code korrekt, sauber formatiert und gut getestet ist. Er läuft auf einer `ubuntu-latest` Umgebung.

**Schritte im Detail:**

1.  **Code auschecken:** Lädt die aktuellste Version des Codes in die virtuelle Umgebung von GitHub.
2.  **Python einrichten:** Installiert die für das Projekt spezifizierte Python-Version (z.B. 3.12).
3.  **Abhängigkeiten installieren:** Installiert alle für das Projekt notwendigen Python-Pakete aus der `backend/requirements.txt` sowie die für die Tests und das Linting benötigten Tools (`pytest`, `pytest-cov`, `ruff`).
4.  **Code-Stil prüfen (Linting):** Führt `ruff check` aus, um den Code auf Stilfehler, Inkonsistenzen und potenzielle Probleme zu überprüfen. Dies sorgt für einen konsistenten und lesbaren Code.
5.  **Tests & Coverage ausführen:** Startet die Test-Suite mit `pytest`. Gleichzeitig wird mit `pytest-cov` gemessen, wie viel Prozent des Anwendungscodes (`app/`) durch die Tests abgedeckt sind. Das Ergebnis wird als `coverage.xml`-Datei gespeichert.
6.  **Coverage-Bericht hochladen:** Sendet den `coverage.xml`-Bericht an den Dienst Codecov.io. Dies ermöglicht eine visuelle Analyse der Testabdeckung und deren Entwicklung über die Zeit.

### Voraussetzungen für den Backend-Job

Damit der Upload zu Codecov funktioniert, muss ein **Repository Secret** in den GitHub-Einstellungen angelegt werden:
- **Name:** `CODECOV_TOKEN`
- **Wert:** Das von Codecov bereitgestellte Upload-Token.

---

## Frontend-Pipeline (`frontend-ci`)

Dieser Job validiert den Frontend-Code und stellt sicher, dass die Anwendung fehlerfrei gebaut werden kann. Er läuft ebenfalls auf einer `ubuntu-latest` Umgebung.

**Schritte im Detail:**

1.  **Code auschecken:** Lädt die aktuellste Version des Codes herunter.
2.  **Node.js einrichten:** Installiert die spezifizierte Node.js-Version (z.B. 20). Der `npm`-Cache wird wiederhergestellt, um die Installationszeiten bei wiederholten Läufen zu beschleunigen.
3.  **Abhängigkeiten installieren:** Führt `npm ci` aus. Dieser Befehl ist schneller und sicherer für CI-Umgebungen als `npm install`, da er die exakten Versionen aus der `package-lock.json` installiert.
4.  **Code-Stil prüfen (Linting):** Führt `npm run lint` aus, was wiederum ESLint startet. ESLint überprüft den TypeScript- und React-Code auf Fehler und Stilprobleme gemäß der Konfiguration in `.eslintrc.cjs`.
5.  **Projekt bauen (Build):** Führt `npm run build` aus. Dieser Schritt kompiliert den TypeScript- und React-Code in statische HTML-, CSS- und JavaScript-Dateien. Ein erfolgreicher Build bestätigt, dass es keine Typfehler oder Syntaxfehler im Code gibt, die die Kompilierung verhindern würden.