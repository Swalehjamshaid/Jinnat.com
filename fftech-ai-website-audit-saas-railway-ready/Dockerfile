# ✅ Pin to Debian Bookworm to avoid package-name churn in testing (trixie)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ Install system deps required by WeasyPrint (Cairo/Pango/GDK-PixBuf/GLib…)
# WeasyPrint requires OS libraries on Linux; pip alone is not enough. [1](https://learn.microsoft.com/en-us/answers/questions/481534/cannot-intall-weasyprint-dependencies-for-python-w)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    curl \
    \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    \
    # ✅ Correct Debian package name (Bookworm)
    libgdk-pixbuf-2.0-0 \
    \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libffi-dev \
    shared-mime-info \
    \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
