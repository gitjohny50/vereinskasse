#!/usr/bin/env bash
set -euo pipefail

# Aktiviert Nginx als lokalen HTTPS-Reverse-Proxy.
# Uvicorn bleibt auf 127.0.0.1:8000, iPads/Macs greifen ueber https://<host>.local zu.

HOSTNAME="${1:-kasse}"
APP_DIR="${APP_DIR:-/opt/vereinskasse}"
CERT_DAYS="${CERT_DAYS:-3650}"
CERT_NAME="vereinskasse"
CERT_CRT="/etc/ssl/certs/${CERT_NAME}.crt"
CERT_KEY="/etc/ssl/private/${CERT_NAME}.key"
NGINX_AVAILABLE="/etc/nginx/sites-available/vereinskasse"
NGINX_ENABLED="/etc/nginx/sites-enabled/vereinskasse"
REPO_CONF="${APP_DIR}/deploy/nginx/vereinskasse.conf"
BACKEND_DROPIN_DIR="/etc/systemd/system/vereinskasse-backend.service.d"
BACKEND_DROPIN="${BACKEND_DROPIN_DIR}/20-network.conf"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Bitte mit sudo ausfuehren." >&2
  exit 1
fi

if [[ ! -f "${REPO_CONF}" ]]; then
  echo "Nginx-Konfiguration nicht gefunden: ${REPO_CONF}" >&2
  exit 1
fi

apt-get update
apt-get install -y nginx openssl

install -d -m 0755 /etc/ssl/certs
install -d -m 0710 /etc/ssl/private

TMP_CONF="$(mktemp)"
trap 'rm -f "${TMP_CONF}"' EXIT

cat > "${TMP_CONF}" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = DE
ST = BW
L = Lokal
O = Vereinskasse
CN = ${HOSTNAME}.local

[v3_req]
subjectAltName = @alt_names
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = ${HOSTNAME}.local
DNS.2 = kasse.local
DNS.3 = vereinskasse.local
IP.1 = 127.0.0.1
EOF

openssl req -x509 -nodes -days "${CERT_DAYS}" -newkey rsa:2048 \
  -keyout "${CERT_KEY}" \
  -out "${CERT_CRT}" \
  -config "${TMP_CONF}"

chmod 0644 "${CERT_CRT}"
chmod 0640 "${CERT_KEY}"

ln -sf "${REPO_CONF}" "${NGINX_AVAILABLE}"
ln -sf "${NGINX_AVAILABLE}" "${NGINX_ENABLED}"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable --now nginx
systemctl reload nginx

install -d -m 0755 "${BACKEND_DROPIN_DIR}"
cat > "${BACKEND_DROPIN}" <<EOF
[Service]
Environment=VK_MDNS_NAME=${HOSTNAME}
Environment=VK_PUBLIC_URL=https://${HOSTNAME}.local
EOF

systemctl daemon-reload
if systemctl list-unit-files vereinskasse-backend.service >/dev/null 2>&1; then
  systemctl restart vereinskasse-backend.service || true
fi

cat <<EOF

Nginx-Proxy ist eingerichtet.

Oeffentliche Kassenadresse:
  https://${HOSTNAME}.local

Backend intern:
  http://127.0.0.1:8000

Backend-Umgebung:
  ${BACKEND_DROPIN}

Hinweis:
  Das Zertifikat ist lokal selbstsigniert. iPads/Macs zeigen beim ersten
  Aufruf ggf. eine Zertifikatswarnung oder muessen das Zertifikat manuell
  vertrauen.

EOF
