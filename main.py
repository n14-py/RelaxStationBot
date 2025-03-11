import os
import random
import subprocess
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"
VIDEO_DIR = "videos"
AUDIO_DIR = "musica_jazz"

def load_media():
    media = {
        'videos': [os.path.join(VIDEO_DIR, f) for f in os.listdir(VIDEO_DIR) 
                  if f.endswith((".mp4", ".mkv"))],
        'audios': [os.path.join(AUDIO_DIR, f) for f in os.listdir(AUDIO_DIR) 
                  if f.endswith((".mp3", ".aac"))]
    }
    
    if not media['videos']:
        raise FileNotFoundError(f"No videos en {VIDEO_DIR}")
    if not media['audios']:
        raise FileNotFoundError(f"No audios en {AUDIO_DIR}")
    
    return media

def start_stream():
    media = load_media()
    
    while True:
        try:
            video = random.choice(media['videos'])
            audio = random.choice(media['audios'])
            
            cmd = [
                "ffmpeg",
                "-loglevel", "warning",  # Menos logs para reducir I/O
                "-re",
                "-stream_loop", "-1",
                "-i", video,
                "-stream_loop", "-1",
                "-i", audio,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",  # Más rápido que veryfast
                "-b:v", "1800k",         # Bitrate reducido
                "-maxrate", "2000k",
                "-bufsize", "4000k",
                "-pix_fmt", "yuv420p",
                "-g", "48",             # Grupo de imágenes más largo
                "-r", "24",             # FPS reducidos
                "-c:a", "aac",
                "-b:a", "96k",          # Audio más ligero
                "-ar", "22050",         # Muestreo reducido
                "-ac", "1",             # Audio mono
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info(f"🚀 Iniciando stream:\nVideo: {video}\nAudio: {audio}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            # Manejo eficiente de logs
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break
                if "frame=" in output:
                    logging.info(output.strip())
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, ' '.join(cmd))
            
        except Exception as e:
            logging.error(f"❌ Error: {str(e)}")
            logging.info("🕒 Reintentando en 30 segundos...")
            time.sleep(30)

if __name__ == "__main__":
    start_stream()
