# Netzwerkfunktion der Vereinskasse

## Ziel

Der Raspberry Pi übernimmt neben der Kassenanwendung auch die lokale
Netzwerkbereitstellung. Die Kasse muss immer offline funktionieren. Internet ist
nur ein Zusatz, wenn per Ethernet eine Verbindung vorhanden ist.

## Zielverhalten

- Standardmäßig ist kein eigenes WLAN sichtbar.
- Die Kasse ist lokal per mDNS/Bonjour erreichbar, z. B. `https://kasse.local`.
- Nginx ist der öffentliche Einstiegspunkt; Uvicorn/FastAPI läuft nur intern
  auf `127.0.0.1:8000`.
- Ethernet wird automatisch per DHCP genutzt, wenn ein Kabel steckt.
- Bei vorhandener Internetverbindung können externe Dienste genutzt werden.
- Ohne Internet läuft die Kasse unverändert offline weiter.
- Ein lokaler iPad-Zugang ohne externes Netzwerk ist als optionales Profil
  vorbereitet, aber nicht automatisch aktiv.

## Warum kein dauerhaft sichtbares WLAN?

Ein dauerhaft sichtbarer Hotspot ist bequem, bringt aber Nachteile:

- zusätzliche Angriffsfläche
- unnötiger Funkbetrieb im Normalfall
- Verwechslungsgefahr bei mehreren Kassen
- iPads verbinden sich eventuell mit dem falschen Netz

Darum bleibt WLAN im Standardbetrieb aus. Für Einsätze ohne vorhandenes Netzwerk
kann ein lokaler Kassen-Hotspot gezielt aktiviert werden.

## Empfohlene Betriebsarten

### 1. Normalbetrieb mit Ethernet

Der Pi hängt per LAN-Kabel im vorhandenen Netzwerk.

- iPad/Mac öffnet `https://kasse.local`
- Internet wird automatisch erkannt
- SumUp oder andere externe Dienste können bei Internet genutzt werden
- Bei Internet-Ausfall arbeitet die Kasse offline weiter

### 2. Offline-Betrieb ohne Netzwerk

Kein LAN, kein WLAN.

- Verkauf, Belege, Drucker und Schublade laufen lokal
- Zugriff ist nur direkt am Pi/Kiosk möglich
- Die Uhr läuft über die Systemzeit des Pi

### 3. Optionaler lokaler iPad-Zugang

Wenn kein externes Netzwerk vorhanden ist, kann der Pi gezielt einen lokalen
Hotspot starten.

- SSID z. B. `Vereinskasse-kasse`
- iPad verbindet sich mit diesem Netz
- Kasse ist dann über `https://kasse.local` erreichbar
- Internet ist in dieser Betriebsart normalerweise nicht vorhanden

Dieser Hotspot ist nicht automatisch aktiv und wird nur bei Bedarf gestartet.

## Installation auf dem Pi

Script ausführen:

```bash
cd /home/admin/vereinskasse
sudo ./deploy/network/setup-pi-network.sh kasse
```

Danach den HTTPS-Proxy aktivieren:

```bash
sudo ./deploy/network/setup-nginx-proxy.sh kasse
```

Danach ist die Kasse erreichbar unter:

```text
https://kasse.local
```

Falls der Hostname anders sein soll:

```bash
sudo ./deploy/network/setup-pi-network.sh kasse2
sudo ./deploy/network/setup-nginx-proxy.sh kasse2
```

Dann:

```text
https://kasse2.local
```

## Optionalen lokalen iPad-Hotspot aktivieren

Das Setup-Script legt ein deaktiviertes NetworkManager-Profil an. Es sendet also
standardmäßig kein WLAN.

Aktivieren:

```bash
sudo nmcli connection up vereinskasse-local-ap
```

Deaktivieren:

```bash
sudo nmcli connection down vereinskasse-local-ap
```

Zugangsdaten anzeigen:

```bash
sudo cat /etc/vereinskasse/local-ap.txt
```

Hinweis: Das iPad kann sich später automatisch wieder mit dieser SSID verbinden,
wenn das Netz einmal gespeichert wurde. Das ist die sauberste Variante für
"automatisch verbinden", ohne im Normalbetrieb dauerhaft ein WLAN zu senden.

## Internetprüfung

Der Pi bekommt bei Ethernet seine IP automatisch per DHCP. Die Anwendung prüft
beim Start zusätzlich, ob eine Internetverbindung besteht. Der Startbeleg zeigt:

- QR-Code auf die primäre Kassenadresse
- lokale IP-Adressen
- mDNS-Adresse
- Internetstatus `online` oder `offline`
- Hostname
- lokale Uhrzeit
- Backend-, Frontend- und Datenbankstatus
- angelegte Benutzer

Manuell prüfen:

```bash
hostname -I
avahi-resolve-host-name kasse.local
curl -I --connect-timeout 3 https://github.com
```

## systemd-Konfiguration

Für Zugriff aus dem LAN lauscht **Nginx** auf Port 80/443. Das Backend selbst
lauscht nur lokal, damit Uvicorn nicht direkt im Netzwerk hängt:

```ini
Environment=VK_HOST=127.0.0.1
Environment=VK_PORT=8000
Environment=VK_MDNS_NAME=kasse
Environment=VK_PUBLIC_URL=https://kasse.local
Environment=VK_TIMEZONE=Europe/Berlin
ExecStart=/home/admin/vereinskasse/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Danach:

```bash
sudo systemctl daemon-reload
sudo systemctl restart vereinskasse-backend.service
sudo systemctl reload nginx
```

Die versionierte Nginx-Konfiguration liegt unter
`deploy/nginx/vereinskasse.conf`. Sie liefert `frontend/dist` aus und leitet
`/api/` an `http://127.0.0.1:8000` weiter. Das lokale Zertifikat wird durch
`deploy/network/setup-nginx-proxy.sh` erzeugt.

## Uhrzeit: sinnvolle Quelle

Die Anwendung sollte fachlich immer so arbeiten:

- Speicherung in der Datenbank: UTC
- Anzeige und Druck: lokale Kassenzeit, standardmäßig `Europe/Berlin`
- Systemzeit des Pi als führende Quelle

Für den Pi heißt das:

```bash
sudo timedatectl set-timezone Europe/Berlin
sudo timedatectl set-ntp true
timedatectl
```

Wenn Ethernet mit Internet vorhanden ist, synchronisiert der Pi die Uhr per NTP.
Ohne Internet läuft die Uhr lokal weiter. Für lange Offline-Zeiträume ist die
interne RTC des Raspberry Pi 5 mit Batterie sinnvoll, damit die Uhr nach
Stromverlust nicht falsch startet.

Auf Raspberry Pi 5 wird die interne RTC verwendet. Es ist kein externes
DS3231-Overlay nötig. Wenn `hwclock` installiert ist, schreibt die Kasse beim
Setzen der Uhrzeit im Servicebereich die Systemzeit zusätzlich in die RTC.

```bash
sudo apt install -y util-linux util-linux-extra
cat /sys/class/rtc/rtc0/name
sudo hwclock -r
```

Empfehlung:

- Normalbetrieb: Systemzeit + NTP über Ethernet
- Offline-Fest über mehrere Tage: interne Raspberry-Pi-5-RTC mit Batterie
- Keine Zeit aus dem iPad beziehen; das iPad ist nur Client
- Keine Zeit aus SumUp beziehen; SumUp ist externer Dienst und nicht immer da

## Grenzen

Ein lokaler Hotspot ohne externes Netzwerk löst nur den Zugriff vom iPad auf die
Kasse. Er ersetzt kein Internet. Externe Dienste funktionieren dann nur, wenn der
Pi zusätzlich eine echte Internetverbindung hat.

Ein Captive Portal wird bewusst nicht eingesetzt, weil es auf dem iPad
zusätzliche Bildschirmfläche belegt und den Kassenstart unnötig kompliziert
macht. Der Zugriff erfolgt direkt über `https://kasse.local` oder über den
QR-Code auf dem Startbeleg.
