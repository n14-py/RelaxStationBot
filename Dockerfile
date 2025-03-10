FROM python:3.9-slim

# Habilitar repositorios necesarios
RUN echo "deb http://deb.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security buster/updates main contrib non-free" >> /etc/apt/sources.list

# Instalar dependencias base
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gnupg2 \
    ca-certificates \
    software-properties-common \
    && apt-get update

# Instalar paquetes multimedia
RUN apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    libx264-dev \
    libfdk-aac-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar entorno
WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación y medios
COPY . .
RUN mkdir -p videos musica_jazz && \
    chmod -R 755 videos musica_jazz

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libgomp.so.1

CMD ["python", "-u", "main.py"]
