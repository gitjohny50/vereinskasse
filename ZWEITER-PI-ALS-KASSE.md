# Zweiten Raspberry Pi als weitere Kasse aufsetzen

Diese Anleitung richtet einen zweiten Pi frisch aus der aktuellen `main`-Version
von GitHub ein. Der zweite Pi läuft als eigene Kasse mit eigener lokaler
Datenbank.

Wichtig: Eine laufende SQLite-Datenbank sollte nicht zwischen zwei aktiven Pis
gespiegelt werden. Nutze pro Pi ein eigenes Datenverzeichnis. Stammdaten wie
Artikel kannst du per CSV oder Backup vor dem Einsatz übernehmen, Verkäufe und
Belege sollten nicht live per Dateisync zusammengeführt werden.

## 1. Pi vorbereiten

Auf dem zweiten Pi anmelden und Grundpakete installieren:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm rsync
```

Optional den Hostnamen eindeutig setzen:

```bash
sudo hostnamectl set-hostname kasse2
sudo reboot
```

Danach ist der Pi im Netzwerk meist als `kasse2.local` erreichbar.

## 2. Projekt von GitHub holen

```bash
cd /home/admin
git clone https://github.com/gitjohny50/vereinskasse.git
cd vereinskasse
git switch main
git pull origin main
```

## 3. Backend installieren

```bash
cd /home/admin/vereinskasse/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 4. Frontend bauen

```bash
cd /home/admin/vereinskasse/frontend
npm install
npm run build
```

## 5. Datenverzeichnis anlegen

```bash
mkdir -p /home/admin/vereinskasse-daten
```

Beim ersten Start legt die Anwendung dort automatisch die Datenbank an. Danach
im UI als Admin die Kassenprofile, Artikel, Pfand und Zahlarten einrichten oder
Artikel per CSV importieren.

## 6. systemd-Service einrichten

```bash
sudo tee /etc/systemd/system/vereinskasse-backend.service > /dev/null << 'EOF'
[Unit]
Description=Vereinskasse Backend
After=network-online.target
Wants=network-online.target

[Service]
User=admin
WorkingDirectory=/home/admin/vereinskasse/backend
Environment=VK_DATA_DIR=/home/admin/vereinskasse-daten
Environment=VK_HOST=0.0.0.0
Environment=VK_PORT=8000
ExecStart=/home/admin/vereinskasse/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now vereinskasse-backend.service
sudo systemctl status vereinskasse-backend.service
```

Der Status sollte `active (running)` zeigen.

## 7. Aufrufen und prüfen

Vom iPad oder Mac im gleichen Netzwerk:

```text
http://kasse2.local:8000
```

Falls `kasse2.local` nicht auflöst, die IP prüfen:

```bash
hostname -I
```

Dann im Browser öffnen:

```text
http://IP-DES-PI:8000
```

## 8. Drucker und Schublade einrichten

Im UI als Service/Admin anmelden und unter `Service` bzw. `Drucke` prüfen:

- Testausdruck starten
- Kassenschublade öffnen
- Druckwarteschlange prüfen
- Bonvorschub und Schnitt testen

Wenn der zweite Pi einen eigenen Drucker nutzt, müssen die Druckereinstellungen
auf diesem Pi separat passen.

## Updates später einspielen

```bash
cd /home/admin/vereinskasse
git fetch origin
git switch main
git pull origin main

cd frontend
npm install
npm run build

cd ../backend
.venv/bin/pip install -r requirements.txt
sudo systemctl restart vereinskasse-backend.service
```

## Betriebsregel für mehrere Kassen

Für ein Fest mit mehreren Kassen ist am saubersten:

- Jeder Pi hat eine eigene Datenbank und ein eigenes Kassenprofil.
- Stammdaten werden vor Veranstaltungsbeginn auf alle Pis übertragen.
- Nach dem Fest werden Abschlüsse und CSV-Exporte je Pi ausgewertet.
- Keine aktive Live-Synchronisation der SQLite-Datei während Verkäufe laufen.
