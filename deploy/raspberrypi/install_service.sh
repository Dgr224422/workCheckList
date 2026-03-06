#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as a regular user (not root)." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_TEMPLATE="$ROOT_DIR/deploy/systemd/workchecklist-bot.service"
SERVICE_RENDERED="/tmp/workchecklist-bot.service"
SERVICE_NAME="workchecklist-bot.service"
BOT_USER="${SUDO_USER:-$USER}"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo ".env not found in $ROOT_DIR" >&2
  exit 1
fi

sed \
  -e "s|__BOT_USER__|$BOT_USER|g" \
  -e "s|__BOT_WORKDIR__|$ROOT_DIR|g" \
  "$SERVICE_TEMPLATE" > "$SERVICE_RENDERED"

echo "Installing $SERVICE_NAME"
sudo cp "$SERVICE_RENDERED" "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Service installed and restarted."
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

echo
echo "Useful commands:"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
