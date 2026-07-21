# Netzwerkfunktion der Vereinskasse

## Ziel

Der Raspberry Pi übernimmt neben der Kassenanwendung auch die lokale
Netzwerkbereitstellung. Die Kasse muss immer offline funktionieren. Internet ist
nur ein Zusatz, wenn per Ethernet eine Verbindung vorhanden ist.

## Zielverhalten

- Standardmäßig ist kein eigenes WLAN sichtbar.
- Die Kasse ist lokal per mDNS/Bonjour erreichbar, z. B. `http://kasse.local:8000`.
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

- iPad/Mac öffnet `http://kasse.local:8000`
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
- Kasse ist dann über `http://kasse.local:8000` erreichbar
- Internet ist in dieser Betriebsart normalerweise nicht vorhanden

Dieser Hotspot ist nicht automatisch aktiv und wird nur bei Bedarf gestartet.

## Installation auf dem Pi

Script ausführen:

```bash
cd /home/admin/vereinskasse
sudo ./deploy/network/setup-pi-network.sh kasse
```

Danach ist die Kasse erreichbar unter:

```text
http://kasse.local:8000
```

Falls der Hostname anders sein soll:

```bash
sudo ./deploy/network/setup-pi-network.sh kasse2
```

Dann:

```text
http://kasse2.local:8000
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

- lokale IP-Adressen
- mDNS-Adresse
- Internetstatus `online` oder `offline`
- Hostname
- lokale Uhrzeit

Manuell prüfen:

```bash
hostname -I
avahi-resolve-host-name kasse.local
curl -I --connect-timeout 3 https://github.com
```

## systemd-Konfiguration

Für Zugriff aus dem LAN muss das Backend auf allen Interfaces lauschen:

```ini
Environment=VK_HOST=0.0.0.0
Environment=VK_PORT=8000
Environment=VK_MDNS_NAME=kasse
Environment=VK_TIMEZONE=Europe/Berlin
ExecStart=/home/admin/vereinskasse/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Danach:

```bash
sudo systemctl daemon-reload
sudo systemctl restart vereinskasse-backend.service
```

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
Ohne Internet läuft die Uhr lokal weiter. Für lange Offline-Zeiträume ist ein
RTC-Modul sinnvoll, z. B. DS3231, damit die Uhr nach Stromverlust nicht falsch
startet.

Empfehlung:

- Normalbetrieb: Systemzeit + NTP über Ethernet
- Offline-Fest über mehrere Tage: zusätzlich RTC-Modul
- Keine Zeit aus dem iPad beziehen; das iPad ist nur Client
- Keine Zeit aus SumUp beziehen; SumUp ist externer Dienst und nicht immer da

## Grenzen

Ein lokaler Hotspot ohne externes Netzwerk löst nur den Zugriff vom iPad auf die
Kasse. Er ersetzt kein Internet. Externe Dienste funktionieren dann nur, wenn der
Pi zusätzlich eine echte Internetverbindung hat.
