# ✅ Pin to stable Debian release to avoid package-name changes
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ Install system dependencies
# NOTE: WeasyPrint requires OS libraries on Linux (Cairo, Pango, GDK-PixBuf, etc.)
# pip alone is NOT enough. [1](https://learn.microsoft.com/en-us/answers/questions/481534/cannot-intall-weasyprint-dependencies-for-python-w)[2](https://itsfoss.com/solve-open-shared-object-file-quick-tip/)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    curl \
    \
    # ✅ WeasyPrint runtime dependencies
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    \
    # ✅ Image decoding support required by WeasyPrint for PNG/JPEG/SVG images
    libgdk-pixbuf-2.0-0 \
    \
    # ✅ GLib (includes the GObject runtime on Debian Bookworm)
    # IMPORTANT: Do NOT install libgobject-2.0-0 (it doesn't exist on Bookworm)
    libglib2.0-0 \
    \
    libffi-dev \
    shared-mime-info \
    \
    # ✅ Fonts (prevents blank/missing text in generated PDFs)
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
