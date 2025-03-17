FROM python:3.9-slim-buster

# Instalar dependencias esenciales
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    fuse3 \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone (versión estable)
RUN curl https://rclone.org/install.sh | bash

# Configurar usuario y permisos
RUN useradd -m appuser && \
    mkdir -p /mnt/gdrive_{videos,sonidos,musica} && \
    chown -R appuser:appuser /mnt /home/appuser

WORKDIR /app

# Copiar todo el proyecto
COPY . .

# Configurar rclone como usuario no-root
RUN mkdir -p /home/appuser/.config/rclone && \
    mv rclone.conf /home/appuser/.config/rclone/rclone.conf && \
    chmod 600 /home/appuser/.config/rclone/rclone.conf && \
    chown -R appuser:appuser /home/appuser

# Variables críticas
ENV RCLONE_CONFIG=/home/appuser/.config/rclone/rclone.conf

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

USER appuser

# Comando de inicio optimizado
CMD sh -c "rclone mount --daemon --vfs-cache-mode full gdrive_videos: /mnt/gdrive_videos && \
          rclone mount --daemon --vfs-cache-mode full gdrive_sonidos: /mnt/gdrive_sonidos && \
          rclone mount --daemon --vfs-cache-mode full gdrive_musica: /mnt/gdrive_musica && \
          sleep 30 && \
          python main.py"
