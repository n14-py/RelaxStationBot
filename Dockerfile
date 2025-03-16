FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    rclone \
    fuse \
    && rm -rf /var/lib/apt/lists/*

COPY rclone.conf /root/.config/rclone/rclone.conf
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "rclone mount gdrive_videos: /media/videos --daemon && \
                  rclone mount gdrive_sonidos: /media/sonidos_naturaleza --daemon && \
                  rclone mount gdrive_musica: /media/musica_jazz --daemon && \
                  python -u main.py"]
