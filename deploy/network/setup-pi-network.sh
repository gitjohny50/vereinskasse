#!/usr/bin/env bash
set -euo pipefail

# Richtet den Pi so ein, dass die Kasse per mDNS erreichbar ist.
# WLAN wird bewusst nicht als sichtbarer Hotspot aktiviert.

HOSTNAME="${1:-kasse}"
AP_SSID="${2:-Vereinskasse-${HOSTNAME}}"
AP_PASSWORD="${3:-}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AP_ADDRESS="10.42.0.1"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Bitte mit sudo ausführen." >&2
  exit 1
fi

apt-get update
apt-get install -y avahi-daemon avahi-utils chrony network-manager curl python3

hostnamectl set-hostname "${HOSTNAME}"
systemctl enable --now avahi-daemon
systemctl enable --now chrony
timedatectl set-timezone Europe/Berlin
timedatectl set-ntp true

# Raspberry Pi OS nutzt je nach Image dhcpcd oder NetworkManager. Für den
# optionalen lokalen iPad-Zugang legen wir nur ein deaktiviertes Profil an.
# Es sendet also standardmäßig kein WLAN und erfüllt damit den Offline-Betrieb.
systemctl enable --now NetworkManager || true

if command -v nmcli >/dev/null 2>&1; then
  if ! nmcli connection show vereinskasse-local-ap >/dev/null 2>&1; then
    if [[ -z "${AP_PASSWORD}" ]]; then
      AP_PASSWORD="$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 16)"
    fi
    nmcli connection add type wifi ifname wlan0 con-name vereinskasse-local-ap autoconnect no ssid "${AP_SSID}"
    nmcli connection modify vereinskasse-local-ap 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared ipv4.addresses "${AP_ADDRESS}/24" ipv6.method disabled
    nmcli connection modify vereinskasse-local-ap wifi-sec.key-mgmt wpa-psk wifi-sec.psk "${AP_PASSWORD}"
    install -d -m 0750 /etc/vereinskasse
    {
      echo "SSID=${AP_SSID}"
      echo "PASSWORT=${AP_PASSWORD}"
      echo "HINWEIS=Profil ist deaktiviert. Aktivieren mit: sudo nmcli connection up vereinskasse-local-ap"
    } > /etc/vereinskasse/local-ap.txt
    chmod 0600 /etc/vereinskasse/local-ap.txt
  fi
fi

# Captive Portal für iPad/Android/Windows: Im lokalen Hotspot beantworten wir
# alle DNS-Namen mit der Hotspot-Adresse und liefern auf Port 80 eine
# Weiterleitung zur Kasse aus. Das greift nur für Clients im AP-Netz.
install -d -m 0755 /etc/NetworkManager/dnsmasq-shared.d
cat > /etc/NetworkManager/dnsmasq-shared.d/99-vereinskasse-captive.conf <<EOF
address=/#/${AP_ADDRESS}
address=/${HOSTNAME}.local/${AP_ADDRESS}
EOF

install -d -m 0755 /etc/systemd/system
sed \
  -e "s#__PROJECT_DIR__#${PROJECT_DIR}#g" \
  -e "s#__HOSTNAME__#${HOSTNAME}#g" \
  "${PROJECT_DIR}/deploy/network/vereinskasse-captive-portal.service" \
  > /etc/systemd/system/vereinskasse-captive-portal.service

systemctl daemon-reload
systemctl enable --now vereinskasse-captive-portal.service
systemctl restart NetworkManager || true

cat <<EOF

Netzwerk-Basis ist eingerichtet.

mDNS-Adresse:
  http://${HOSTNAME}.local:8000

Internetstatus testen:
  curl -I --connect-timeout 3 https://github.com

Optionaler lokaler iPad-Zugang ohne externes Netzwerk:
  sudo nmcli connection up vereinskasse-local-ap
  sudo nmcli connection down vereinskasse-local-ap

Captive Portal:
  systemctl status vereinskasse-captive-portal.service
  Das iPad sollte nach Verbindung mit dem WLAN automatisch "Vereinskasse öffnen" anzeigen.

WLAN-Zugangsdaten, falls Profil erzeugt wurde:
  sudo cat /etc/vereinskasse/local-ap.txt

EOF
