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
    curl \
    git \
    build-essential \
    libx264-dev \
    libfdk-aac-dev \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js 18.x
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# Configurar entorno
WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias Node.js
COPY package*.json ./
RUN npm install --production

# Copiar aplicación y medios
COPY . .
RUN mkdir -p videos musica_jazz public && \
    chmod -R 755 videos musica_jazz public

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libgomp.so.1
ENV PORT=3000

EXPOSE 3000

CMD ["sh", "-c", "python -u main.py & node server.js"]
