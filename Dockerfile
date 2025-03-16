FROM python:3.9-slim-buster

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    curl \
    unzip \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Crear estructura de directorios
RUN mkdir -p \
    /mnt/gdrive_videos \
    /mnt/gdrive_sonidos \
    /mnt/gdrive_musica \
    /app

WORKDIR /app

# Copiar configuración y código
COPY rclone.conf /root/.config/rclone/rclone.conf
COPY requirements.txt .
COPY main.py .
COPY server.js .
COPY package.json .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt && \
    npm install

# Configuración de seguridad
RUN useradd -m streamer && \
    chown -R streamer:streamer /app && \
    chown -R streamer:streamer /mnt

USER streamer

# Puerto y ejecución
EXPOSE 10000 3000

CMD sh -c "rclone mount gdrive_videos: /mnt/gdrive_videos --daemon && \
          rclone mount gdrive_sonidos: /mnt/gdrive_sonidos --daemon && \
          rclone mount gdrive_musica: /mnt/gdrive_musica --daemon && \
          python main.py & \
          node server.js"
