FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ System dependencies:
# - CA certs + build tools (your existing)
# - PLUS WeasyPrint runtime deps (Cairo/Pango/GDK-PixBuf/GLib/GObject)
# WeasyPrint requires these OS libs on Linux; pip alone is not enough. [1](https://learn.microsoft.com/en-us/answers/questions/481534/cannot-intall-weasyprint-dependencies-for-python-w)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    curl \
    \
    # ✅ WeasyPrint required runtime libraries:
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libffi-dev \
    shared-mime-info \
    \
    # ✅ Fonts (avoid blank/missing glyphs in PDF):
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
