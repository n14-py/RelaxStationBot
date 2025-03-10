import os
import random
import subprocess

# Configuración
VIDEOS_DIR = "videos"
MUSIC_DIR = "musica_jazz"
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"

# Verificar y cargar medios
def load_media():
    videos = [os.path.join(VIDEOS_DIR, f) for f in os.listdir(VIDEOS_DIR) if f.endswith(".mp4")]
    music = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.endswith(".mp3")]
    
    if not videos:
        raise FileNotFoundError(f"No se encontraron videos en {VIDEOS_DIR}")
    if not music:
        raise FileNotFoundError(f"No se encontró música en {MUSIC_DIR}")
    
    return videos, music

def main():
    videos, music = load_media()
    
    # Selección aleatoria
    video_path = random.choice(videos)
    audio_path = random.choice(music)
    
    # Configuración FFmpeg
    command = [
        "ffmpeg",
        "-re",
        "-stream_loop", "-1",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "2500k",
        "-maxrate", "3000k",
        "-bufsize", "6000k",
        "-pix_fmt", "yuv420p",
        "-g", "50",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-f", "flv",
        RTMP_URL
    ]
    
    # Ejecutar transmisión
    try:
        print("Iniciando transmisión con:")
        print("Video:", video_path)
        print("Audio:", audio_path)
        print("Comando FFmpeg:", " ".join(command))
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Mostrar logs en tiempo real
        for line in process.stdout:
            print(line.strip())
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if process:
            process.terminate()

if __name__ == "__main__":
    main()
