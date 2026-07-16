#!/usr/bin/env bash
# Startet Chromium im Kioskmodus und zeigt die lokale Kassenoberfläche.
# Lastenheft 1: nach dem Einschalten automatisch die Kassenoberfläche; kein
# Zugriff auf den Linux-Desktop für den normalen Bediener.
set -euo pipefail

URL="http://127.0.0.1:8000/"

# Auf das Backend warten, bevor Chromium startet.
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null; then
    break
  fi
  sleep 1
done

# Bildschirmschoner/Energieverwaltung deaktivieren.
xset s off || true
xset -dpms || true
xset s noblank || true

# Reste eines vorherigen Absturzes unterdrücken, damit kein Wiederherstellen-Dialog erscheint.
PROFILE="/home/kasse/.config/chromium"
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PROFILE/Default/Preferences" 2>/dev/null || true
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PROFILE/Default/Preferences" 2>/dev/null || true

exec chromium-browser \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --app="$URL"
