#!/usr/bin/env bash
# Meeting Insights Platform — local launcher.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing Python dependencies"
pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example (edit it to set secrets / API key)"
  cp .env.example .env
fi

echo "==> Seeding database (idempotent — admin user + first meeting)"
python -m backend.seed

echo "==> Starting server on http://127.0.0.1:8000"
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
