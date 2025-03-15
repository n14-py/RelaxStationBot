FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libx264-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requisitos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p videos musica_jazz sonidos_naturaleza

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV CLIENT_ID=""
ENV CLIENT_SECRET=""
ENV YOUTUBE_REFRESH_TOKEN=""
ENV RTMP_URL=""

CMD ["python3", "-u", "main.py"]
