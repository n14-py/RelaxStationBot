FROM python:3.9-slim-buster

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Configurar usuario
RUN useradd -m appuser && \
    mkdir -p /mnt/gdrive_{videos,sonidos,musica} && \
    chown -R appuser:appuser /mnt

WORKDIR /app

# Copiar configuración rclone
COPY rclone.conf /home/appuser/.config/rclone/rclone.conf
RUN chmod 600 /home/appuser/.config/rclone/rclone.conf && \
    chown -R appuser:appuser /home/appuser/.config

# Variables críticas
ENV RCLONE_CONFIG=/home/appuser/.config/rclone/rclone.conf

COPY . .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

USER appuser

CMD sh -c "rclone mount gdrive_videos: /mnt/gdrive_videos --daemon && \
          rclone mount gdrive_sonidos: /mnt/gdrive_sonidos --daemon && \
          rclone mount gdrive_musica: /mnt/gdrive_musica --daemon && \
          python main.py"
