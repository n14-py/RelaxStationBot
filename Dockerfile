FROM python:3.9-slim-buster

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Crear estructura de carpetas
RUN mkdir -p /media/{videos,sonidos,musica}

# Copiar todo el proyecto
COPY . .

# Configurar rclone (usando tu archivo actualizado)
RUN mkdir -p /root/.config/rclone && \
    mv rclone.conf /root/.config/rclone/rclone.conf && \
    chmod 600 /root/.config/rclone/rclone.conf

# Sincronizar archivos durante el build
RUN rclone copy --verbose gdrive_videos: /media/videos && \
    rclone copy --verbose gdrive_sonidos: /media/sonidos && \
    rclone copy --verbose gdrive_musica: /media/musica

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Puerto expuesto
EXPOSE 10000

# Comando de inicio
CMD python main.py
