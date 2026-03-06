#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as a regular user (not root)." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Installing system packages"
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  libzbar0 libglib2.0-0 libgl1 \
  tzdata git

echo "[2/5] Setting timezone to Europe/Moscow"
sudo timedatectl set-timezone Europe/Moscow

echo "[3/5] Creating virtual environment"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

echo "[4/5] Installing Python dependencies"
pip install -r requirements.txt

echo "[5/5] Creating runtime directories"
mkdir -p data logs media

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Fill BOT_TOKEN and SYSTEM_ADMIN_ID."
fi

echo
echo "Setup complete."
echo "Next:"
echo "  1) edit $ROOT_DIR/.env"
echo "  2) install service: bash deploy/raspberrypi/install_service.sh"
