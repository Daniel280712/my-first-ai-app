#!/usr/bin/env bash
# Add a WireGuard client and print config + QR code for phone import
set -euo pipefail

WG_DIR="/etc/wireguard"
WG_IF="wg0"
CLIENTS_DIR="${WG_DIR}/clients"
DNS="${DNS:-1.1.1.1}"
ENDPOINT="${ENDPOINT:-YOUR_PUBLIC_IP_OR_DDNS:51820}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0 <client-name>"
  exit 1
fi

CLIENT_NAME="${1:-}"
if [[ -z "${CLIENT_NAME}" ]]; then
  echo "Usage: sudo $0 <client-name>"
  echo "Example: sudo ENDPOINT=home.example.duckdns.org:51820 $0 pixel5"
  exit 1
fi

if [[ "${ENDPOINT}" == "YOUR_PUBLIC_IP_OR_DDNS:51820" ]]; then
  echo "Set ENDPOINT to your public IP or DDNS hostname, e.g.:"
  echo "  sudo ENDPOINT=203.0.113.10:51820 $0 ${CLIENT_NAME}"
  exit 1
fi

if [[ ! -f "${WG_DIR}/server.pub" ]]; then
  echo "Server not installed. Run: sudo ./scripts/install-wireguard.sh"
  exit 1
fi

mkdir -p "${CLIENTS_DIR}"

# Pick next free IP in 10.8.0.0/24
USED=$(grep -oP 'AllowedIPs = \K10\.8\.0\.\d+' "${WG_DIR}/${WG_IF}.conf" 2>/dev/null || true)
for i in $(seq 2 254); do
  IP="10.8.0.${i}"
  if ! echo "${USED}" | grep -qx "${IP}"; then
    CLIENT_IP="${IP}"
    break
  fi
done

if [[ -z "${CLIENT_IP:-}" ]]; then
  echo "No free client IPs left in 10.8.0.0/24"
  exit 1
fi

CLIENT_PRIV="$(wg genkey)"
CLIENT_PUB="$(echo "${CLIENT_PRIV}" | wg pubkey)"
SERVER_PUB="$(cat "${WG_DIR}/server.pub")"

CLIENT_CONF="${CLIENTS_DIR}/${CLIENT_NAME}.conf"
cat > "${CLIENT_CONF}" <<EOF
[Interface]
PrivateKey = ${CLIENT_PRIV}
Address = ${CLIENT_IP}/32
DNS = ${DNS}

[Peer]
PublicKey = ${SERVER_PUB}
Endpoint = ${ENDPOINT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF
chmod 600 "${CLIENT_CONF}"

# Register peer on server
cat >> "${WG_DIR}/${WG_IF}.conf" <<EOF

[Peer]
# ${CLIENT_NAME}
PublicKey = ${CLIENT_PUB}
AllowedIPs = ${CLIENT_IP}/32
EOF

wg syncconf "${WG_IF}" <(wg-quick strip "${WG_IF}")

echo "Client '${CLIENT_NAME}' added at ${CLIENT_IP}"
echo
echo "=== Config: ${CLIENT_CONF} ==="
cat "${CLIENT_CONF}"
echo
echo "=== Scan with WireGuard app on your phone ==="
qrencode -t ansiutf8 < "${CLIENT_CONF}"
