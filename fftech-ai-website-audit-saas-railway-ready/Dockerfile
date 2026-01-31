FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python + system dependencies (needed for WeasyPrint / PDF generation)
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

# Create virtual environment and make it active for the rest of the build
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy requirements first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "uvicorn[standard]"

# Copy the entire application
COPY . .

# Expose port (informational – Railway ignores this and uses PORT env var)
EXPOSE 8000

# ────────────────────────────────────────────────────────────────
# FIXED: Shell form CMD (no []) so ${PORT} expands correctly at runtime
# Fallback to 8000 when running locally with docker run
# ────────────────────────────────────────────────────────────────
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
