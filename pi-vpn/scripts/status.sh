#!/usr/bin/env bash
# Quick health check for the Pi VPN
set -euo pipefail

WG_IF="${WG_IF:-wg0}"

echo "=== WireGuard interface ==="
if command -v wg >/dev/null; then
  wg show "${WG_IF}" 2>/dev/null || echo "Interface ${WG_IF} not running."
else
  echo "wireguard-tools not installed"
fi

echo
echo "=== IP forwarding ==="
sysctl net.ipv4.ip_forward

echo
echo "=== Listening on UDP 51820 ==="
ss -ulnp | grep 51820 || echo "Nothing listening on 51820 yet."

echo
echo "=== Recent client configs ==="
ls -1 /etc/wireguard/clients/*.conf 2>/dev/null || echo "No clients in /etc/wireguard/clients/"
