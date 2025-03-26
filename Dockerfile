# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Crear directorios necesarios con permisos adecuados
RUN mkdir -p /app/media_cache && chmod 777 /app/media_cache

# Copiar requirements primero para aprovechar la cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos
COPY . .

# Variables de entorno (puedes sobreescribirlas al ejecutar)
ENV PORT=10000

# Exponer puerto y comando de ejecución
EXPOSE $PORT
CMD ["python", "main.py"]
