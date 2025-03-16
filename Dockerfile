FROM python:3.9-slim-buster

# 1. Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# 3. Crear usuario y directorios para appuser
RUN useradd -m appuser && \
    mkdir -p /home/appuser/.config/rclone && \
    chown -R appuser:appuser /home/appuser

WORKDIR /app

# 4. Copiar archivos (incluyendo rclone.conf desde la raíz del repo)
COPY . .

# 5. Mover configuración al home de appuser
RUN mv rclone.conf /home/appuser/.config/rclone/rclone.conf && \
    chown -R appuser:appuser /home/appuser/.config && \
    chmod 600 /home/appuser/.config/rclone/rclone.conf

# 6. Variables clave
ENV RCLONE_CONFIG=/home/appuser/.config/rclone/rclone.conf

# 7. Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# 8. Cambiar a usuario no-root
USER appuser

# 9. Comando de inicio (ejecuta todo como appuser)
CMD sh -c "rclone mount --config $RCLONE_CONFIG gdrive_videos: /mnt/gdrive_videos --daemon && \
          rclone mount --config $RCLONE_CONFIG gdrive_sonidos: /mnt/gdrive_sonidos --daemon && \
          rclone mount --config $RCLONE_CONFIG gdrive_musica: /mnt/gdrive_musica --daemon && \
          sleep 15 && \
          python main.py"
