# Installation auf dem Raspberry Pi 5 (Phase 1)

Diese Anleitung richtet den technischen Prototyp ein: Backend, gebautes
Frontend und den Chromium-Kiosk als automatisch startende Dienste. Sie ersetzt
noch keine produktive, rechtskonforme Inbetriebnahme (siehe Lastenheft 26).

## 1. Grundsystem

- Raspberry Pi OS (64 Bit) auf die NVMe-SSD installieren.
- System aktualisieren:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip nodejs npm chromium-browser xserver-xorg xinit unclutter curl avahi-daemon avahi-utils chrony network-manager nginx openssl
```

- Dedizierten Benutzer `kasse` anlegen (falls nicht vorhanden):

```bash
sudo adduser --disabled-password --gecos "Vereinskasse" kasse
sudo usermod -aG lp,plugdev,dialout kasse   # Drucker/USB/serielle Zugriffe
```

## 2. Projekt kopieren

Projektordner nach `/opt/vereinskasse` kopieren und Datenverzeichnis anlegen:

```bash
sudo mkdir -p /opt/vereinskasse /opt/vereinskasse-daten
sudo cp -r vereinskasse/* /opt/vereinskasse/
sudo chown -R kasse:kasse /opt/vereinskasse /opt/vereinskasse-daten
```

Lokalen Netzwerknamen und mDNS einrichten:

```bash
sudo /opt/vereinskasse/deploy/network/setup-pi-network.sh kasse
```

Danach ist der lokale Netzwerkname vorbereitet.
Details zum optionalen iPad-Zugang ohne externes Netzwerk stehen in
`docs/NETZWERKFUNKTION.md`.

## 3. Backend einrichten

```bash
cd /opt/vereinskasse/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Für echten USB-Druck zusätzlich (erst wenn Gerät angeschlossen):
# .venv/bin/pip install pyusb
```

Kurztest ohne Hardware (Mock-Drucker):

```bash
VK_DATA_DIR=/opt/vereinskasse-daten .venv/bin/uvicorn app.main:app --port 8000 &
curl -s http://127.0.0.1:8000/api/health
```

## 4. Frontend bauen

```bash
cd /opt/vereinskasse/frontend
npm install
npm run build      # erzeugt frontend/dist, das Nginx ausliefert
```

## 5. HTTPS-Proxy aktivieren

Uvicorn bleibt nur lokal auf `127.0.0.1:8000` erreichbar. Nginx liefert das
Frontend aus und leitet `/api/` an das Backend weiter.

```bash
sudo chmod +x /opt/vereinskasse/deploy/network/setup-nginx-proxy.sh
sudo /opt/vereinskasse/deploy/network/setup-nginx-proxy.sh kasse
```

Danach ist die Kasse im LAN über diese Adresse erreichbar:

```text
https://kasse.local
```

Das Zertifikat ist lokal selbstsigniert. Auf iPads/Macs muss es beim ersten
Aufruf ggf. bestätigt bzw. manuell vertraut werden.

## 6. Dienste aktivieren

```bash
sudo cp /opt/vereinskasse/deploy/vereinskasse-backend.service /etc/systemd/system/
sudo cp /opt/vereinskasse/deploy/vereinskasse-kiosk.service /etc/systemd/system/
sudo cp /opt/vereinskasse/deploy/vereinskasse-time.sudoers /etc/sudoers.d/vereinskasse-time
sudo chmod 0440 /etc/sudoers.d/vereinskasse-time
sudo chmod +x /opt/vereinskasse/deploy/kiosk-start.sh
sudo systemctl daemon-reload
sudo systemctl enable --now vereinskasse-backend.service
sudo systemctl enable --now vereinskasse-kiosk.service
```

Nach einem Neustart startet der Pi direkt in die Kassenoberfläche.

Kurz prüfen:

```bash
curl -k https://kasse.local/api/health
curl -s http://127.0.0.1:8000/api/health
```

## 7. USB-Autostart des X-Servers (falls nötig)

Damit der Kiosk ohne Desktop-Anmeldung startet, kann `kasse` per Autologin in
die Konsole angemeldet werden und `.bash_profile` `startx` aufrufen. Alternativ
einen Login-Manager im Autologin-Modus konfigurieren. Details hängen vom
gewählten Raspberry-Pi-OS-Image ab.

## 8. Hardware prüfen

Erst nachdem der echte NetumScan NS-8360L angeschlossen ist:

1. Transport in den Einstellungen von `mock` auf `network` oder `usb` stellen.
2. Bei USB die IDs per `lsusb` ermitteln und in den Einstellungen hinterlegen.
3. Die Tests aus `docs/HARDWARE-TEST.md` durchführen.
