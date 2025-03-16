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

# Copiar código (usando main.py en lugar de app.py)
COPY requirements.txt .
COPY main.py .  # 👈 Cambio clave aquí

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Configuración de seguridad
RUN useradd -m streamer && chown -R streamer:streamer /app
USER streamer

# Puerto y ejecución
EXPOSE 10000
CMD ["python", "main.py"]  # 👈 Y aquí también
