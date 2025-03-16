# Dockerfile
FROM python:3.9-slim-buster

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear estructura de directorios
RUN mkdir -p /app/media/{videos,musica_jazz,sonidos_naturaleza}
WORKDIR /app

# Copiar código y dependencias
COPY requirements.txt .
COPY app.py .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Crear usuario no root
RUN useradd -m streamer && chown -R streamer:streamer /app
USER streamer

# Configuración de puertos y punto de entrada
EXPOSE 10000
CMD ["python", "app.py"]
