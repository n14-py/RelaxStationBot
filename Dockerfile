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

# Instalar rclone y PM2
RUN curl https://rclone.org/install.sh | bash && \
    npm install pm2 -g

# Configurar usuario y directorios
RUN useradd -m renderuser && \
    mkdir -p \
    /mnt/gdrive_videos \
    /mnt/gdrive_sonidos \
    /mnt/gdrive_musica \
    /app && \
    chown -R renderuser:renderuser /app /mnt

WORKDIR /app

# Copiar configuración rclone
COPY rclone.conf /home/renderuser/.config/rclone/rclone.conf
RUN chown -R renderuser:renderuser /home/renderuser/.config

# Copiar código
COPY . .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt && \
    npm install

USER renderuser

# Puerto expuesto (Render necesita este puerto)
EXPOSE 10000

# Comando optimizado
CMD [ "pm2-runtime", "start", "ecosystem.config.js" ]
