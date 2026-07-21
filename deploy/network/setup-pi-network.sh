#!/usr/bin/env bash
set -euo pipefail

# Richtet den Pi so ein, dass die Kasse per mDNS erreichbar ist.
# WLAN wird bewusst nicht als sichtbarer Hotspot aktiviert.

HOSTNAME="${1:-kasse}"
AP_SSID="${2:-Vereinskasse-${HOSTNAME}}"
AP_PASSWORD="${3:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Bitte mit sudo ausführen." >&2
  exit 1
fi

apt-get update
apt-get install -y avahi-daemon avahi-utils chrony network-manager curl

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
    nmcli connection modify vereinskasse-local-ap 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared ipv6.method disabled
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

cat <<EOF

Netzwerk-Basis ist eingerichtet.

mDNS-Adresse:
  http://${HOSTNAME}.local:8000

Internetstatus testen:
  curl -I --connect-timeout 3 https://github.com

Optionaler lokaler iPad-Zugang ohne externes Netzwerk:
  sudo nmcli connection up vereinskasse-local-ap
  sudo nmcli connection down vereinskasse-local-ap

WLAN-Zugangsdaten, falls Profil erzeugt wurde:
  sudo cat /etc/vereinskasse/local-ap.txt

EOF
