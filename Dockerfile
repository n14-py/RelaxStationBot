FROM python:3.9-slim-buster

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    curl \
    unzip \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone y PM2 (para manejar múltiples procesos)
RUN curl https://rclone.org/install.sh | bash && \
    npm install pm2 -g

# Configurar directorios
RUN mkdir -p \
    /mnt/gdrive_videos \
    /mnt/gdrive_sonidos \
    /mnt/gdrive_musica \
    /app

WORKDIR /app

# Copiar archivos
COPY . .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt && \
    npm install

# Permisos y usuario
RUN chmod +x start.sh && \
    useradd -m renderuser && \
    chown -R renderuser:renderuser /app /mnt

USER renderuser

# Puerto expuesto (necesario para Render)
EXPOSE 10000

# Comando de inicio optimizado
CMD [ "pm2-runtime", "start", "ecosystem.config.js" ]
