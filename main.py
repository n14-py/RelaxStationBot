import os
import random

# Carpetas con videos y audios
videos_cabana = ["videos/cabana1.mp4"]
musica_jazz = ["musica_jazz/jazz1.mp3"]

def get_today_video_and_audio():
    """Selecciona un video y música de jazz para el día"""
    # Seleccionamos el video y la música de jazz
    video = random.choice(videos_cabana)
    audio_jazz = random.choice(musica_jazz)
    title = "Cabaña con música de jazz relajante"
    
    return video, audio_jazz, title

# Obtiene el video, audio y título para hoy
video, audio_jazz, title = get_today_video_and_audio()

# Preparamos el comando de FFmpeg para transmitir el video con la música de jazz
command = f'ffmpeg -re -stream_loop -1 -i {video} -i {audio_jazz} -c:v libx264 -preset veryfast -maxrate 3000k -bufsize 6000k -pix_fmt yuv420p -g 50 -b:v 2500k -c:a aac -b:a 128k -f flv "rtmp://a.rtmp.youtube.com/live2/91cs-hmzg-9y50-g7q8-2m9j"'

# Ejecutar transmisión en vivo
os.system(command)

print(f"Transmisión en vivo: {title}")
