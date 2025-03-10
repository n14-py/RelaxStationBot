FROM python:3.9-slim

# Instalar dependencias base
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    git \
    build-essential \
    libx264-dev \
    libaac-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js 18.x
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación y medios
COPY . .
RUN mkdir -p videos musica_jazz && \
    chmod -R 755 videos musica_jazz

# Configuración de tiempo real para streaming
ENV LD_PRELOAD=libgomp.so.1
ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "main.py"]
