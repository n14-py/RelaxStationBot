FROM python:3.9-slim

# Configurar repositorios esenciales
RUN echo "deb http://deb.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security buster/updates main contrib non-free" >> /etc/apt/sources.list

# Instalar dependencias base
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    ffmpeg \
    libx264-dev \
    libgomp1 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js 18.x
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g pm2

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias Node.js
COPY package*.json ./
RUN npm install --production

# Copiar aplicación
COPY . .

# Configurar permisos y estructura de directorios
RUN mkdir -p videos musica_jazz sonidos_naturaleza thumbs && \
    chmod -R 755 videos musica_jazz sonidos_naturaleza thumbs

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV RTMP_URL=${RTMP_URL}

EXPOSE 3000 1935 8080

CMD ["pm2-runtime", "ecosystem.config.js"]
