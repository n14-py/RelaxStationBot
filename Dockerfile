FROM python:3.9-slim-buster

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Crear usuario y directorios
RUN useradd -m appuser && \
    mkdir -p /mnt/gdrive_{videos,sonidos,musica} && \
    chown -R appuser:appuser /mnt

WORKDIR /app

# Copiar TODO desde la raíz del repo
COPY . .

# Configurar rclone
RUN mkdir -p /home/appuser/.config/rclone && \
    cp rclone.conf /home/appuser/.config/rclone/rclone.conf && \
    chown -R appuser:appuser /home/appuser/.config && \
    chmod 600 /home/appuser/.config/rclone/rclone.conf

# Variables críticas
ENV RCLONE_CONFIG="/home/appuser/.config/rclone/rclone.conf"

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

USER appuser

# Comando de inicio optimizado
CMD sh -c "rclone mount gdrive_videos: /mnt/gdrive_videos --daemon && \
          rclone mount gdrive_sonidos: /mnt/gdrive_sonidos --daemon && \
          rclone mount gdrive_musica: /mnt/gdrive_musica --daemon && \
          sleep 15 && \
          python main.py"
