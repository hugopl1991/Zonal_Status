# ─────────────────────────────────────────────────────────────────────────────
# Imagem base: Python 3.13 slim (Debian Trixie) + GDAL via repos Debian
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependências de sistema + GDAL (Debian Trixie já tem GDAL 3.x nos repos)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libspatialindex-dev \
        python3-dev \
        build-essential \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# Dependências Python
# ─────────────────────────────────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && GDAL_VERSION=$(gdal-config --version) \
 && pip install --no-cache-dir "GDAL==${GDAL_VERSION}" \
 && pip install --no-cache-dir -r /tmp/requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Scripts
# ─────────────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY scripts/ /app/scripts/

CMD ["python", "scripts/Zonal_shp.py"]