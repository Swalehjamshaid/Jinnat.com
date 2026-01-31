FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python + system deps in one layer
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

# Working dir
WORKDIR /app

# Create + activate venv (PATH update is persistent)
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy & install deps (cache-friendly order)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir uvicorn[standard]  # force uvicorn if missing

# Copy app code
COPY . .

# Railway uses $PORT env var automatically
EXPOSE 8000

# CMD uses venv's uvicorn (adjust "main:app" → "app.main:app" if file is in /app/app/main.py)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
