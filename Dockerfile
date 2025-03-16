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
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js 18.x
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias Node.js
COPY package*.json ./
RUN npm install --production

# Copiar aplicación
COPY . .

# Configurar permisos
RUN chmod -R 755 videos musica_jazz

# Variables de entorno
ENV PYTHONUNBUFFERED=1

EXPOSE 3000

CMD ["sh", "-c", "python -u main.py & node server.js"]
