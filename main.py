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
    return {
        'videos': [os.path.join(VIDEO_DIR, f) for f in os.listdir(VIDEO_DIR) 
                  if f.lower().endswith((".mp4", ".mkv"))],
        'audios': [os.path.join(AUDIO_DIR, f) for f in os.listdir(AUDIO_DIR) 
                  if f.lower().endswith((".mp3", ".aac"))]
    }

def start_stream():
    media = load_media()
    
ffmpeg_base = [
    "ffmpeg",
    "-loglevel", "error",
    "-threads", "1",
    "-re",
    "-i", "",  # Video (eliminar stream_loop)
    "-stream_loop", "-1",
    "-i", "",  # Audio
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-x264-params", "keyint=30:min-keyint=15:no-scenecut=1",
    "-b:v", "600k",  # Reducción adicional
    "-maxrate", "800k",
    "-bufsize", "1600k",
    "-vf", "scale=640:360:force_original_aspect_ratio=decrease",  # 360p
    "-r", "15",  # 15 FPS
    "-g", "30",
    "-c:a", "aac",
    "-b:a", "32k",  # Calidad mínima
    "-ac", "1",
    "-ar", "16000",
    "-f", "flv",
    RTMP_URL
]
    
    while True:
        try:
            video = random.choice(media['videos'])
            audio = random.choice(media['audios'])
            
            cmd = ffmpeg_base.copy()
            cmd[6] = video  # Índice para video
            cmd[9] = audio  # Índice para audio
            
            logging.info(f"🚀 Iniciando stream:\nVideo: {video}\nAudio: {audio}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if "frame=" in line:
                    logging.info(line.strip())
            
            if process.returncode != 0:
                error_msg = f"FFmpeg Error (Code {process.returncode}): {line.strip()}"
                raise subprocess.CalledProcessError(process.returncode, error_msg)
            
        except Exception as e:
            logging.error(f"❌ Error: {str(e)}")
            logging.info("🕒 Reintentando en 30 segundos...")
            time.sleep(30)

if __name__ == "__main__":
    start_stream()
