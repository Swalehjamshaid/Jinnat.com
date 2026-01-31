# Use a suitable base image (choose one that matches your needs)
# Options: debian:bookworm-slim, python:3.11-slim, node:20-slim, etc.
FROM ubuntu:22.04

# Optional: set working directory early
WORKDIR /app

# Your original package installations
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    openssl \
    curl \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ... rest of your Dockerfile (COPY, RUN pip/npm install, CMD, etc.)
