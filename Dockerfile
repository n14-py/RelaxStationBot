FROM python:3.9-slim-buster

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Crear usuario y estructura de carpetas
RUN useradd -m appuser && \
    mkdir -p /mnt/gdrive_{videos,sonidos,musica} && \
    mkdir -p /home/appuser/.config/rclone && \
    chown -R appuser:appuser /mnt /home/appuser

WORKDIR /app

# Copiar todo el proyecto
COPY . .

# Mover configuración de rclone
RUN mv rclone.conf /home/appuser/.config/rclone/rclone.conf && \
    chown -R appuser:appuser /home/appuser/.config && \
    chmod 600 /home/appuser/.config/rclone/rclone.conf

# Variables críticas
ENV RCLONE_CONFIG=/home/appuser/.config/rclone/rclone.conf

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

USER appuser

# Comando de inicio
CMD sh -c "rclone mount --config $RCLONE_CONFIG gdrive_videos: /mnt/gdrive_videos --daemon && \
          rclone mount --config $RCLONE_CONFIG gdrive_sonidos: /mnt/gdrive_sonidos --daemon && \
          rclone mount --config $RCLONE_CONFIG gdrive_musica: /mnt/gdrive_musica --daemon && \
          sleep 20 && \
          python main.py"
