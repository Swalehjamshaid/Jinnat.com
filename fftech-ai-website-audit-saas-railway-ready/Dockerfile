# Use Ubuntu 22.04 as base (good for your WeasyPrint system deps)
FROM ubuntu:22.04

# Avoid interactive prompts during apt
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (your original + Python essentials)
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
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create virtual environment (best practice for isolation)
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Copy and install Python dependencies first (cache layer optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir uvicorn[standard]  # ensure uvicorn is there

# Copy the rest of your application code
COPY . .

# Expose the port (Railway uses $PORT anyway, but good habit)
EXPOSE 8000

# Start the app with uvicorn (use full path or rely on venv PATH)
# Adjust "main:app" if your file is app/main.py → use "app.main:app"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
