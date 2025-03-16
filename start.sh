#!/bin/bash

# Montar drives usando la variable de entorno
rclone mount --config $RCLONE_CONFIG gdrive_videos: /mnt/gdrive_videos --daemon
rclone mount --config $RCLONE_CONFIG gdrive_sonidos: /mnt/gdrive_sonidos --daemon
rclone mount --config $RCLONE_CONFIG gdrive_musica: /mnt/gdrive_musica --daemon

sleep 10  # Esperar montaje

python main.py
