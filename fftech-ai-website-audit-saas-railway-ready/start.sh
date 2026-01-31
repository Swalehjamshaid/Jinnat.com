#!/bin/sh
set -e

echo "Starting application..."
echo "PORT is: ${PORT:-8080}"

python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port ${PORT:-8080}
