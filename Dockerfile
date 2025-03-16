FROM python:3.9-slim

# Instalar dependencias esenciales
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    rclone \
    fuse \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Configurar Rclone
COPY rclone.conf /root/.config/rclone/rclone.conf

# Copiar aplicación
WORKDIR /app
COPY . .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Puerto obligatorio para Render
EXPOSE 10000

# Usar dumb-init como entrypoint
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Comando de inicio mejorado
CMD ["sh", "-c", "rclone mount gdrive_videos: /media/videos --daemon && \
                  rclone mount gdrive_sonidos: /media/sonidos_naturaleza --daemon && \
                  rclone mount gdrive_musica: /media/musica_jazz --daemon && \
                  sleep 10 && \
                  python -u main.py"]
