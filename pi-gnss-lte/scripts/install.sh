#!/usr/bin/env bash
# Install GNSS/LTE lab on Raspberry Pi 3
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV_DIR="${REPO_DIR}/.venv"
GPS_DEVICE="${GPS_DEVICE:-/dev/ttyUSB0}"
PORT="${LAB_PORT:-8090}"
SERVICE_NAME="pi-gnss-lte-lab"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo REPO_DIR=${REPO_DIR} $0"
  exit 1
fi

echo "==> Installing gpsd + Python dependencies"
apt-get update
apt-get install -y gpsd gpsd-clients python3-venv

# Configure gpsd for USB GPS (adjust GPS_DEVICE if needed)
if [[ ! -f /etc/default/gpsd.bak ]]; then
  cp /etc/default/gpsd /etc/default/gpsd.bak 2>/dev/null || true
fi
cat > /etc/default/gpsd <<EOF
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="${GPS_DEVICE}"
USBAUTO="true"
EOF

systemctl enable gpsd
systemctl restart gpsd

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${REPO_DIR}/requirements.txt"

UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
cat > "${UNIT}" <<EOF
[Unit]
Description=Pi GNSS/LTE Lab
After=network-online.target gpsd.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${REPO_DIR}
Environment=PYTHONPATH=${REPO_DIR}
ExecStart=${VENV_DIR}/bin/uvicorn gnss_lte.server:app --host 0.0.0.0 --port ${PORT}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

LAN_IP="$(hostname -I | awk '{print $1}')"
echo
echo "GNSS/LTE lab running at: http://${LAN_IP}:${PORT}"
echo "On your Pixel 5: open that URL → menu → Install app / Add to Home screen"
echo
echo "Hardware:"
echo "  GPS: USB dongle (set GPS_DEVICE=${GPS_DEVICE} if not ttyUSB0)"
echo "  LTE: optional USB modem + SIM (install modemmanager for mmcli)"
