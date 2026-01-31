FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python + system dependencies (for WeasyPrint/PDF rendering, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
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
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Set working directory
WORKDIR /app

# Create virtual environment and activate it persistently for runtime
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy requirements first for better caching during builds
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir uvicorn[standard]  # ensure uvicorn is available

# Copy the rest of your application code
COPY . .

# Expose port (informational only — Railway uses $PORT env var)
EXPOSE 8000

# ────────────────────────────────────────────────────────────────
# IMPORTANT FIX: Use SHELL FORM (no []) so $PORT expands at runtime
# ${PORT:-8000} → uses Railway's PORT if set, else 8000 for local docker run
# ────────────────────────────────────────────────────────────────
# Adjust module path if needed:
#   - If main.py is directly in /app → keep main:app
#   - If main.py is in /app/app/main.py → change to app.main:app
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
