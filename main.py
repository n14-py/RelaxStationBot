import os
import random
from datetime import datetime

videos_departamento = ["videos/departamento_lluvia1.mp4"]
musica_jazz = ["musica_jazz/jazz1.mp3"]

def get_today_video_and_audio():
    video_type = random.choice([videos_departamento])
    video = random.choice(video_type)
    
    if video in videos_departamento:
        title = "Departamento con música jazz relajante"
        audio_jazz = random.choice(musica_jazz)
    
    return video, audio_jazz, title

video, audio_jazz, title = get_today_video_and_audio()

# Verificar archivos
audio_jazz_path = os.path.abspath(audio_jazz)
video_path = os.path.abspath(video)

if not os.path.exists(audio_jazz_path):
    print(f"Error audio: {audio_jazz_path}")
if not os.path.exists(video_path):
    print(f"Error video: {video_path}")

# Nuevo comando FFmpeg
command = (
    f'ffmpeg -re '
    f'-stream_loop -1 -i "{video_path}" '  # Video en loop infinito
    f'-stream_loop -1 -i "{audio_jazz_path}" '  # Audio en loop infinito
    f'-map 0:v:0 '  # Tomar video del primer input
    f'-map 1:a:0 '  # Tomar audio del segundo input
    f'-c:v libx264 -preset veryfast -b:v 2500k -maxrate 3000k -bufsize 6000k '
    f'-pix_fmt yuv420p -g 50 -r 30 '
    f'-c:a aac -b:a 192k -ar 44100 '
    f'-f flv "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"'
)

print("Ejecutando comando:", command)
os.system(command)
print(f"Transmitiendo: {title}")
