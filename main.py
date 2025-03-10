FROM python:3.9-slim

# 1. Configurar repositorios y dependencias base
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gnupg2 \
    ca-certificates \
    && echo "deb http://deb.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security buster/updates main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update

# 2. Instalar paquetes multimedia
RUN apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    libx264-dev \
    libfdk-aac-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Continuar con el resto de la configuración
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p videos musica_jazz
CMD ["python", "-u", "main.py"]
