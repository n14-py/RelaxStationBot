FROM python:3.9-slim

# 1. Actualizar repositorios y añadir multiverse
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common && \
    add-apt-repository universe && \
    add-apt-repository multiverse && \
    apt-get update

# 2. Instalar dependencias principales
RUN apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    libx264-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Instalar Node.js 18.x
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

# Resto del Dockerfile permanece igual...
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p videos musica_jazz && \
    chmod -R 755 videos musica_jazz

ENV LD_PRELOAD=libgomp.so.1
ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "main.py"]
