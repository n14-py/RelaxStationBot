# Usar versión estable de Debian
FROM python:3.9-slim-bullseye

# Instalar dependencias con mirrors confiables
RUN echo "deb http://deb.debian.org/debian bullseye main" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian bullseye-updates main" >> /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security bullseye-security main" >> /etc/apt/sources.list && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Copiar configuración
COPY rclone.conf /root/.config/rclone/rclone.conf
RUN chmod 600 /root/.config/rclone/rclone.conf

# Sincronizar archivos
RUN mkdir -p /media/{videos,sonidos,musica} && \
    rclone copy --verbose --progress gdrive_videos: /media/videos && \
    rclone copy --verbose --progress gdrive_sonidos: /media/sonidos && \
    rclone copy --verbose --progress gdrive_musica: /media/musica

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000

CMD ["python", "main.py"]
