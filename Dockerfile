# Usar versión estable de Debian con compiladores necesarios
FROM python:3.9-slim-bullseye

# Configurar entorno y dependencias del sistema
RUN echo "deb http://deb.debian.org/debian bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    wget \
    libx264-dev \
    libx265-dev \
    libvpx-dev \
    libmp3lame-dev \
    libopus-dev \
    libass-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV TZ=America/Mexico_City

COPY . /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt
    libsm6 \
    libxext6 \
    libgl1 \
    libpq5 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorios y permisos
RUN mkdir -p /app/media_cache && chmod -R 777 /app/media_cache
WORKDIR /app

# Copiar solo lo necesario
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Puerto para health checks
EXPOSE 10000

# Comando de inicio con logging mejorado
CMD ["python", "-u", "main.py"]
