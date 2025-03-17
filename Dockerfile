# Usar versión estable de Debian
FROM python:3.9-slim-bullseye

# Instalar dependencias esenciales
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Configurar entorno
WORKDIR /app
COPY . .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Puerto para health checks
EXPOSE 10000

# Comando de inicio
CMD ["python", "main.py"]
