import os
import random
from datetime import datetime

# Carpetas con videos y audios
videos_departamento = []  # No tienes videos, lo dejamos vacío
videos_cabana = ["videos/cabana1.mp4"]
videos_departamento_lluvia = ["videos/departamento_lluvia1.mp4"]

musica_jazz = ["musica_jazz/jazz1.mp3"]  # Corregido el nombre de la carpeta
sonidos_naturaleza = ["musica_jazz/lluvia1.mp3"]  # Corregido el nombre de la carpeta

def get_today_video_and_audio():
    """Selecciona un video y música aleatorios para el día"""
    available_videos = []
    
    # Agregar las listas de videos que sí tienes disponibles
    if videos_departamento:
        available_videos.append(videos_departamento)
    if videos_cabana:
        available_videos.append(videos_cabana)
    if videos_departamento_lluvia:
        available_videos.append(videos_departamento_lluvia)

    if not available_videos:
        return None, None, None, "No hay videos disponibles"

    # Aleatorizar qué tipo de video y música se elige
    video_type = random.choice(available_videos)
    video = random.choice(video_type)
    
    # Título dinámico basado en el tipo de video
    if video in videos_departamento:
        title = "Departamento con música de jazz relajante"
        audio_jazz = random.choice(musica_jazz)
        audio_naturaleza = None
    elif video in videos_cabana:
        title = "Cabaña con sonido de fuego relajante"
        audio_jazz = None  # No música de jazz en este caso
        audio_naturaleza = None  # No sonido de lluvia ni naturaleza
    elif video in videos_departamento_lluvia:
        title = "Departamento con música jazz y sonido de lluvia relajante"
        audio_jazz = random.choice(musica_jazz)
        audio_naturaleza = random.choice(sonidos_naturaleza)
    
    return video, audio_jazz, audio_naturaleza, title

# Obtiene el video, audio y título para hoy
video, audio_jazz, audio_naturaleza, title = get_today_video_and_audio()

# Si no hay videos disponibles
if video is None:
    print("No hay videos disponibles para la transmisión")
else:
    # Preparamos el comando de FFmpeg para mezclar ambos audios y el video
    if audio_jazz and audio_naturaleza:
        # Si hay dos audios, mezclamos ambos
        command = f'ffmpeg -re -stream_loop -1 -i {video} -i {audio_jazz} -i {audio_naturaleza} -filter_complex "[1][2]amix=inputs=2:duration=longest[a]" -map 0 -map "[a]" -c:v libx264 -preset veryfast -maxrate 3000k -bufsize 6000k -pix_fmt yuv420p -g 50 -b:v 2500k -c:a aac -b:a 128k -f flv "rtmp://a.rtmp.youtube.com/live2/91cs-hmzg-9y50-g7q8-2m9j"'
    else:
        # Si solo hay un audio
        audio = audio_jazz if audio_jazz else audio_naturaleza
        command = f'ffmpeg -re -stream_loop -1 -i {video} -i {audio} -c:v libx264 -preset veryfast -maxrate 3000k -bufsize 6000k -pix_fmt yuv420p -g 50 -b:v 2500k -c:a aac -b:a 128k -f flv "rtmp://a.rtmp.youtube.com/live2/91cs-hmzg-9y50-g7q8-2m9j"'

    # Ejecutar transmisión en vivo
    os.system(command)

    print(f"Transmisión en vivo: {title}")
