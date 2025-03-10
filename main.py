import os
import random
from datetime import datetime

# Carpetas con videos y audios
videos_departamento = ["videos/departamento_lluvia1.mp4"]
musica_jazz = ["musica_jazz/jazz1.mp3"]

def get_today_video_and_audio():
    """Selecciona un video y música aleatorios para el día"""
    # Aleatorizar qué tipo de video y música se elige
    video = random.choice(videos_departamento)
    
    # Título dinámico basado en el tipo de video
    title = "Departamento con música jazz relajante"
    audio_jazz = random.choice(musica_jazz)
    
    return video, audio_jazz, title

# Obtiene el video, audio y título para hoy
video, audio_jazz, title = get_today_video_and_audio()

# Verifica que el archivo de audio exista
audio_jazz_path = os.path.abspath(audio_jazz)
if not os.path.exists(audio_jazz_path):
    print(f"Error: No se encuentra el archivo de audio en la ruta: {audio_jazz_path}")
else:
    print(f"Archivo de audio encontrado en: {audio_jazz_path}")

# Preparamos el comando de FFmpeg para mezclar ambos audios y el video
if audio_jazz:
    # Si solo hay un audio (música de jazz)
    command = f'ffmpeg -re -stream_loop -1 -i {video} -i {audio_jazz} -c:v libx264 -preset veryfast -maxrate 3000k -bufsize 6000k -pix_fmt yuv420p -g 50 -b:v 2500k -c:a aac -b:a 128k -f flv "rtmp://a.rtmp.youtube.com/live2/91cs-hmzg-9y50-g7q8-2m9j"'

# Ejecutar transmisión en vivo
os.system(command)

print(f"Transmisión en vivo: {title}")
