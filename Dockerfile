# Dockerfile corregido y compatible
FROM python:3.9-slim

# 1. Instalar dependencias base
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalar Node.js 18.x (LTS) con npm compatible
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@9

# 3. Configurar entorno
WORKDIR /app

# 4. Instalar dependencias Python primero
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar toda la aplicación
COPY . .

# 6. Instalar dependencias Node.js después de copiar package.json
COPY package*.json ./
RUN npm install --production

# 7. Crear directorios para medios
RUN mkdir -p videos musica_jazz

# 8. Puerto para el servidor Node.js
EXPOSE 3000

# 9. Comando de inicio
CMD ["sh", "-c", "python main.py & node server.js"]
