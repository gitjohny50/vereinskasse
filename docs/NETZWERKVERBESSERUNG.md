# Setup-Guide: Sichere Netzwerk- & Proxy-Konfiguration (Raspberry Pi)

Diese Anleitung beschreibt, wie das FastAPI-Backend und das React-Frontend der Vereinskasse auf einem Raspberry Pi sicher über Nginx bereitgestellt werden.

## Warum ist diese Umstellung so wichtig?

*   **Sicherheit (Verschlüsselung):** Ohne HTTPS werden sensible Daten wie Admin-PINs, Benutzer-Tokens und Kassenbestände im Klartext durch das lokale WLAN/LAN gesendet und könnten mitgelesen werden.
*   **Netzwerk-Isolation:** Ein reiner Application-Server wie Uvicorn (FastAPI) sollte niemals direkt dem Netzwerk (über `0.0.0.0`) ausgesetzt sein. Er ist nicht dafür gebaut, direkte Client-Verbindungen aus dem Internet/LAN abzusichern.
*   **Performance:** Nginx ist extrem hochoptimiert für die Auslieferung von statischen Dateien. Das fertig kompilierte React-Frontend wird dadurch wesentlich schneller geladen, als wenn das Python-Backend dies übernehmen müsste.
*   **Infrastructure as Code:** Indem die Nginx-Konfiguration direkt im Git-Repository liegt, ist sie versioniert. Bei einem Absturz des PIs oder einem Hardwarewechsel ist das Setup in Sekunden wiederhergestellt.

---

## Schritt 1: Nginx-Konfiguration im Repository anlegen

Erstelle im Repository einen neuen Ordner (z.B. `deployment/` oder `config/`) und darin eine Datei namens `nginx.conf`. 

**Inhalt der `nginx.conf`:**

```nginx
# Leitet alle unverschlüsselten HTTP-Anfragen automatisch auf HTTPS um
server {
    listen 80;
    server_name vereinskasse.local; 
    
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name vereinskasse.local;

    # Pfade zu den lokalen SSL-Zertifikaten
    ssl_certificate /etc/ssl/certs/vereinskasse.crt;
    ssl_certificate_key /etc/ssl/private/vereinskasse.key;

    # Sichere SSL-Einstellungen
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    # 1. Frontend: Statische React-Dateien ausliefern
    location / {
        # WICHTIG: Pfad anpassen zum tatsächlichen 'dist' Ordner des Repos
        root /home/USER/vereinskasse/frontend/dist; 
        index index.html;
        
        # Für React-Router: Leitet alle Routen intern an die index.html weiter
        try_files $uri$uri/ /index.html;
    }

    # 2. Backend: API-Anfragen an FastAPI (Uvicorn) weiterleiten
    location /api/ {
        proxy_pass [http://127.0.0.1:8000](http://127.0.0.1:8000);
        
        # Originale Client-IPs und Host-Header an das Backend durchreichen
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket-Support (z.B. für Live-Druckstatus)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

```

---

## Schritt 2: Backend-Dienst absichern (Uvicorn)

Das Backend darf nicht mehr auf `0.0.0.0` laufen, sondern darf nur noch Verbindungen vom eigenen Gerät (`127.0.0.1`), also von Nginx, akzeptieren.

1. Öffne den systemd-Service für das Backend auf dem Pi (z. B. `sudo nano /etc/systemd/system/vereinskasse-backend.service`).
2. Passe den `ExecStart`-Befehl an, sodass der Host `127.0.0.1` ist:

```ini
ExecStart=/home/USER/vereinskasse/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

```

3. Lade die Dienste neu und starte das Backend neu:

```bash
sudo systemctl daemon-reload
sudo systemctl restart vereinskasse-backend

```

---

## Schritt 3: Lokale SSL-Zertifikate generieren

Damit Nginx über HTTPS (Port 443) lauschen kann, benötigen wir ein Zertifikat. Für ein lokales Netzwerk reicht ein selbstsigniertes Zertifikat aus (Gültigkeit hier: 10 Jahre).

Führe folgenden Befehl auf dem Pi aus:

```bash
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/private/vereinskasse.key \
  -out /etc/ssl/certs/vereinskasse.crt \
  -subj "/C=DE/ST=BW/L=Esslingen/O=Vereinskasse/CN=vereinskasse.local"

```

---

## Schritt 4: Nginx verknüpfen (Symlinks erstellen)

Damit Nginx die Datei aus unserem Repository nutzt, erstellen wir Verknüpfungen (Symlinks). So muss die Datei nach einem `git pull` nicht manuell kopiert werden.

*(Hinweis: Ersetze `/home/USER/vereinskasse/...` mit dem echten Pfad auf dem Pi)*

```bash
# 1. Verknüpfung im sites-available Ordner anlegen
sudo ln -s /home/USER/vereinskasse/deployment/nginx.conf /etc/nginx/sites-available/vereinskasse

# 2. Die Konfiguration aktivieren (Link in sites-enabled setzen)
sudo ln -s /etc/nginx/sites-available/vereinskasse /etc/nginx/sites-enabled/

# 3. Die Standard-Seite von Nginx deaktivieren, um Konflikte zu vermeiden
sudo rm /etc/nginx/sites-enabled/default

```

---

## Schritt 5: Testen und Neustarten

Bevor Nginx neu gestartet wird, sollte die Syntax der Konfigurationsdatei überprüft werden, um Ausfälle zu vermeiden.

```bash
# Syntax-Check durchführen
sudo nginx -t

# Wenn "syntax is ok" und "test is successful" ausgegeben wird:
sudo systemctl restart nginx

```

---

## Zukünftige Updates

Wenn die `nginx.conf` in Zukunft im Code-Editor angepasst und via GitHub auf den Pi gepullt wird, muss lediglich Nginx angewiesen werden, die Konfiguration neu zu laden:

```bash
# Auf dem Pi ausführen nach einem git pull:
sudo systemctl reload nginx

```

```

```