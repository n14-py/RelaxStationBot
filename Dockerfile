FROM python:3.9-slim-buster

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Copiar configuración actualizada
COPY rclone.conf /root/.config/rclone/rclone.conf
RUN chmod 600 /root/.config/rclone/rclone.conf

# Sincronizar archivos durante el build
RUN mkdir -p /media/{videos,sonidos,musica} && \
    rclone copy --progress --verbose gdrive_videos: /media/videos && \
    rclone copy --progress --verbose gdrive_sonidos: /media/sonidos && \
    rclone copy --progress --verbose gdrive_musica: /media/musica

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000

CMD ["python", "main.py"]
