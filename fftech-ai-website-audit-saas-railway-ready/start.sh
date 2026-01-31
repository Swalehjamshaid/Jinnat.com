#!/bin/sh
set -e

# Railway sets PORT automatically. Default to 8080 for local/dev.
PORT="${PORT:-8080}"

echo "Starting Uvicorn on port: $PORT"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
