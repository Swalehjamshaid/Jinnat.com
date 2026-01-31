# ✅ Stable Debian base to avoid package name changes
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ System dependencies:
# - SSL: ca-certificates + openssl (prevents CERTIFICATE_VERIFY_FAILED)
# - WeasyPrint deps: cairo / pango / gdk-pixbuf / fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    openssl \
    \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libffi-dev \
    shared-mime-info \
    \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ✅ Force Python/Requests to use system CA bundle
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway will inject PORT, but we keep a fallback.
EXPOSE 8080

# ✅ IMPORTANT:
# Use shell form so ${PORT} is expanded.
# This avoids Uvicorn receiving "$PORT" as a literal string.
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
