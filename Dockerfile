# Dockerfile optimizado para streaming con Python + Node.js
FROM python:3.9-slim

# Instalar dependencias principales
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js 16.x
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@latest

# Configurar entorno
WORKDIR /app

# Copiar primero los requisitos para cachear dependencias
COPY requirements.txt .
COPY package*.json ./

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt && \
    npm install --production

# Copiar toda la aplicación
COPY . .

# Crear directorios para medios
RUN mkdir -p videos musica_jazz

# Puerto para el servidor Node.js
EXPOSE 3000

# Comando de inicio optimizado
CMD ["sh", "-c", "python main.py & node server.js"]
