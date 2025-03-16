FROM python:3.9-slim

# Instalar dependencias
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    rclone \
    fuse \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Configurar Rclone
COPY rclone.conf /etc/rclone/rclone.conf
RUN chmod 600 /etc/rclone/rclone.conf

# Copiar aplicación
WORKDIR /app
COPY . .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Puerto obligatorio
EXPOSE 10000

# Entrypoint mejorado
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Script de inicio
CMD ["sh", "-c", "rclone mount gdrive_videos: /media/videos --config /etc/rclone/rclone.conf --daemon --log-file /tmp/rclone.log && \
                  rclone mount gdrive_sonidos: /media/sonidos_naturaleza --config /etc/rclone/rclone.conf --daemon --log-file /tmp/rclone.log && \
                  rclone mount gdrive_musica: /media/musica_jazz --config /etc/rclone/rclone.conf --daemon --log-file /tmp/rclone.log && \
                  sleep 20 && \
                  python -u main.py"]
