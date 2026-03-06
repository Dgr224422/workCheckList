#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[ERROR] .env not found in $ROOT_DIR" >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "[ERROR] Python venv is missing. Run deploy/raspberrypi/setup_pi.sh first." >&2
  exit 1
fi

mkdir -p logs data media
exec .venv/bin/python -m app.main
