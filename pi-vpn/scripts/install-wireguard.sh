#!/usr/bin/env bash
# WireGuard server setup for Raspberry Pi 3 (Raspberry Pi OS / Debian)
set -euo pipefail

WG_DIR="/etc/wireguard"
WG_IF="wg0"
WG_PORT="${WG_PORT:-51820}"
WG_NET="${WG_NET:-10.8.0.0/24}"
WG_SERVER_IP="${WG_SERVER_IP:-10.8.0.1/24}"
LAN_IF="${LAN_IF:-$(ip route | awk '/default/ {print $5; exit}')}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

if [[ -z "${LAN_IF}" ]]; then
  echo "Could not detect network interface. Set LAN_IF=eth0 or wlan0 and retry."
  exit 1
fi

echo "==> Installing packages"
apt-get update
apt-get install -y wireguard qrencode

echo "==> Enabling IP forwarding"
sysctl -w net.ipv4.ip_forward=1
grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

mkdir -p "${WG_DIR}"
chmod 700 "${WG_DIR}"

if [[ ! -f "${WG_DIR}/server.key" ]]; then
  echo "==> Generating server keys"
  wg genkey | tee "${WG_DIR}/server.key" | wg pubkey > "${WG_DIR}/server.pub"
  chmod 600 "${WG_DIR}/server.key"
fi

SERVER_PRIV="$(cat "${WG_DIR}/server.key")"
SERVER_PUB="$(cat "${WG_DIR}/server.pub")"

if [[ ! -f "${WG_DIR}/${WG_IF}.conf" ]]; then
  echo "==> Writing ${WG_DIR}/${WG_IF}.conf"
  cat > "${WG_DIR}/${WG_IF}.conf" <<EOF
[Interface]
Address = ${WG_SERVER_IP}
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIV}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${LAN_IF} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${LAN_IF} -j MASQUERADE
EOF
  chmod 600 "${WG_DIR}/${WG_IF}.conf"
fi

systemctl enable "wg-quick@${WG_IF}"
systemctl restart "wg-quick@${WG_IF}"

echo
echo "WireGuard server is up on UDP port ${WG_PORT}."
echo "Server public key: ${SERVER_PUB}"
echo
echo "Next steps:"
echo "  1. Forward UDP ${WG_PORT} on your router to this Pi."
echo "  2. Install the web dashboard: sudo ./scripts/install-dashboard.sh"
echo "  3. Open http://<pi-ip>:8080 — add clients and scan QR codes from your phone."
echo
