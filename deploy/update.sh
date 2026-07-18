#!/usr/bin/env bash
# Aktualisiert eine bereits installierte Vereinskasse auf den aktuellen Stand:
# Backend-Abhängigkeiten, Datenbank-Migrationen, Frontend-Build, Dienst-Neustart.
#
# Aufruf auf dem Pi:   sudo -u kasse /opt/vereinskasse/deploy/update.sh
# (oder automatisch aus dem post-receive-Hook beim 'git push').
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vereinskasse}"
DATA_DIR="${VK_DATA_DIR:-/opt/vereinskasse-daten}"

echo "== 1/4  Backend-Abhängigkeiten =="
cd "$APP_DIR/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "== 2/4  Datenbank =="
# Das Schema wird beim Start der App selbst angelegt/ergänzt (create_all +
# automatisches Nachrüsten fehlender Spalten). Kein separater Migrationsschritt nötig.
echo "   (Schema wird beim Dienststart automatisch aktualisiert)"

echo "== 3/4  Frontend bauen =="
cd "$APP_DIR/frontend"
if [ -f package-lock.json ]; then npm ci --silent; else npm install --silent; fi
npm run build

echo "== 4/4  Dienste neu starten =="
sudo systemctl restart vereinskasse-backend.service
sudo systemctl restart vereinskasse-kiosk.service || true

echo "Fertig. Aktueller Stand ist ausgerollt."
