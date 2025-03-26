
# Usar versión estable de Debian
FROM python:3.9-slim-bullseye

# Configurar mirrors confiables y resolver dependencias
RUN echo "deb http://deb.debian.org/debian bullseye main" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian bullseye-updates main" >> /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security bullseye-security main" >> /etc/apt/sources.list && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    && apt-get update && \
    apt-get install -y --fix-missing \
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
