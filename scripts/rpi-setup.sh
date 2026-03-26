#!/usr/bin/env bash
# ------------------------------------------------------------------
# Cot-ExplorerV2 — Raspberry Pi setup script
#
# Installs system dependencies, creates directories, sets up a
# Python venv, installs the project, and optionally installs the
# systemd service unit.
#
# Usage:
#   chmod +x scripts/rpi-setup.sh
#   sudo ./scripts/rpi-setup.sh
# ------------------------------------------------------------------

set -euo pipefail

APP_DIR="/opt/cot-explorer"
DATA_DIR="/opt/cot-explorer/data"
VENV_DIR="/opt/cot-explorer/venv"
SERVICE_USER="cotexplorer"
SERVICE_FILE="/etc/systemd/system/cot-explorer.service"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Cot-ExplorerV2 RPI Setup ==="
echo "Repository: $REPO_DIR"
echo "Install to: $APP_DIR"
echo ""

# ---------- 1. System dependencies ----------
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl

# ---------- 2. Create service user ----------
echo "[2/7] Creating service user '$SERVICE_USER'..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "  Created user $SERVICE_USER"
else
    echo "  User $SERVICE_USER already exists"
fi

# ---------- 3. Create directories ----------
echo "[3/7] Creating directories..."
mkdir -p "$APP_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/prices"
mkdir -p "$DATA_DIR/timeseries"
mkdir -p "$DATA_DIR/combined"
mkdir -p "$DATA_DIR/macro"
mkdir -p "$DATA_DIR/calendar"
mkdir -p "$DATA_DIR/signals"
mkdir -p "$APP_DIR/logs"

# ---------- 4. Copy application ----------
echo "[4/7] Copying application files..."
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='node_modules' --exclude='.env' --exclude='data/' \
      --exclude='.pytest_cache' --exclude='.mypy_cache' \
      "$REPO_DIR/" "$APP_DIR/"

# ---------- 5. Python virtual environment ----------
echo "[5/7] Setting up Python venv..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$APP_DIR"

# ---------- 6. Set permissions ----------
echo "[6/7] Setting permissions..."
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod 700 "$DATA_DIR"

# ---------- 7. Install systemd service ----------
echo "[7/7] Installing systemd service..."
cp "$REPO_DIR/scripts/cot-explorer.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable cot-explorer.service
echo "  Service installed and enabled (not started yet)"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Copy your .env file:  sudo cp .env $APP_DIR/.env"
echo "  2. Start the service:    sudo systemctl start cot-explorer"
echo "  3. Check status:         sudo systemctl status cot-explorer"
echo "  4. View logs:            sudo journalctl -u cot-explorer -f"
echo "  5. Install crontab:      sudo crontab -u $SERVICE_USER scripts/crontab.example"
echo ""
