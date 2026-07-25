# Netzwerkverbesserung: Nginx, HTTPS und lokales Backend

## Ziel

Die Kasse soll im lokalen Netzwerk sauber ueber `https://kasse.local`
erreichbar sein, waehrend das FastAPI-Backend nicht mehr direkt im LAN haengt.
Nginx ist der einzige oeffentliche Einstiegspunkt und leitet API-Anfragen intern
an Uvicorn weiter.

## Umgesetzte Struktur

```text
iPad/Mac
  -> https://kasse.local
  -> Nginx :443
  -> /api/ nach http://127.0.0.1:8000
  -> Frontend aus /opt/vereinskasse/frontend/dist
```

Das Backend laeuft weiterhin lokal fuer den Kiosk:

```text
http://127.0.0.1:8000
```

## Dateien

- `deploy/nginx/vereinskasse.conf`
  Versionierte Nginx-Konfiguration fuer Frontend, HTTPS und API-Proxy.
- `deploy/network/setup-nginx-proxy.sh`
  Installiert Nginx/OpenSSL, erzeugt ein lokales Zertifikat und aktiviert die
  Konfiguration.
- `deploy/vereinskasse-backend.service`
  Bindet Uvicorn nur noch an `127.0.0.1:8000` und setzt `VK_PUBLIC_URL`.
- `docs/NETZWERKFUNKTION.md`
  Beschreibt die Zielarchitektur inklusive optionalem lokalen iPad-Hotspot.

## Installation auf dem Pi

Im Projektordner:

```bash
cd /opt/vereinskasse
sudo ./deploy/network/setup-pi-network.sh kasse
sudo ./deploy/network/setup-nginx-proxy.sh kasse
```

Backend-Service neu installieren bzw. aktualisieren:

```bash
sudo cp /opt/vereinskasse/deploy/vereinskasse-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart vereinskasse-backend.service
sudo systemctl reload nginx
```

## Pruefung

```bash
curl -s http://127.0.0.1:8000/api/health
curl -k https://kasse.local/api/health
sudo nginx -t
systemctl status nginx
systemctl status vereinskasse-backend.service
```

## Zertifikat

Das Setup erzeugt ein selbstsigniertes Zertifikat fuer:

- `<hostname>.local`
- `kasse.local`
- `vereinskasse.local`
- `127.0.0.1`

Auf iPads/Macs kann beim ersten Aufruf eine Zertifikatswarnung erscheinen.
Fuer einen reinen lokalen Kassenbetrieb ist das erwartbar. Wenn die Warnung
stoert, muss das Zertifikat auf den Geraeten als vertrauenswuerdig installiert
werden.

## Warum diese Umstellung?

- Uvicorn ist nicht mehr direkt im LAN erreichbar.
- Frontend-Dateien werden effizient von Nginx ausgeliefert.
- `/api/` bleibt fuer das React-Frontend unveraendert.
- Die Nginx-Konfiguration liegt versioniert im Repository.
- Der Startbeleg kann per `VK_PUBLIC_URL` direkt auf die richtige Adresse
  verweisen.

## Kein Captive Portal

Ein Captive Portal wird bewusst nicht eingesetzt. Es belegt auf dem iPad
Bildschirmflaeche und macht den Start unruhiger. Der Zugriff erfolgt ueber den
QR-Code auf dem Startbeleg oder direkt ueber:

```text
https://kasse.local
```
