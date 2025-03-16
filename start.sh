#!/bin/bash

# Montar drives con rclone
rclone mount gdrive_videos: /mnt/gdrive_videos --daemon
rclone mount gdrive_sonidos: /mnt/gdrive_sonidos --daemon
rclone mount gdrive_musica: /mnt/gdrive_musica --daemon

# Esperar montaje
sleep 5

# Iniciar streaming
python main.py
