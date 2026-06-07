#!/usr/bin/env bash
# Install the Pi VPN web dashboard (run after install-wireguard.sh)
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV_DIR="${REPO_DIR}/.venv"
ENV_FILE="/etc/wireguard/dashboard.env"
SERVICE_NAME="pi-vpn-dashboard"
PORT="${DASHBOARD_PORT:-8080}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo REPO_DIR=${REPO_DIR} $0"
  exit 1
fi

echo "==> Installing Python dashboard dependencies"
apt-get update
apt-get install -y python3-venv python3-pip

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${REPO_DIR}/requirements.txt"

if [[ ! -f "${ENV_FILE}" ]]; then
  PASS="$(openssl rand -base64 18)"
  echo "==> Creating ${ENV_FILE}"
  cat > "${ENV_FILE}" <<EOF
DASHBOARD_PASSWORD="${PASS}"
ENDPOINT="yourname.duckdns.org:51820"
SESSION_SECRET="$(openssl rand -hex 32)"
EOF
  chmod 600 "${ENV_FILE}"
  echo
  echo "Dashboard login password (save this): ${PASS}"
  echo "Update ENDPOINT in the dashboard Settings page or edit ${ENV_FILE}"
  echo
fi

UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
cat > "${UNIT}" <<EOF
[Unit]
Description=Pi VPN Dashboard
After=network-online.target wg-quick@wg0.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
Environment=PYTHONPATH=${REPO_DIR}
ExecStart=${VENV_DIR}/bin/uvicorn dashboard.server:app --host 0.0.0.0 --port ${PORT}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

LAN_IP="$(hostname -I | awk '{print $1}')"
echo
echo "Dashboard running at: http://${LAN_IP}:${PORT}"
echo "Tip: only use this on your home network, or put it behind a reverse proxy."
echo "Check status: systemctl status ${SERVICE_NAME}"
