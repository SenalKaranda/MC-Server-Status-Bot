#!/usr/bin/env bash
set -euo pipefail

echo
echo "[*] Using docker-compose.yml in $(pwd)"
if [ ! -f ".env" ]; then
  echo "[!] .env not found. Copying from .env.example..."
  cp .env.example .env
  echo "[!] Edit the .env file and set WEBHOOK_URL before starting."
fi

echo
echo "[*] Building and starting containers..."
docker compose up -d --build

echo
echo "[ok] Running."
echo "    Banner:   http://localhost:8080/banner.png"
echo "    Discord:  refreshes every INTERVAL seconds via webhook edits."
