#!/bin/sh
set -e

echo "Starting FastAPI on PORT=${PORT:-8080}"

# Run FastAPI via Python so PORT is read correctly
python app/main.py
