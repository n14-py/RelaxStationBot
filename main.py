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
    
    # Parámetros críticos para low-end
    ffmpeg_base = [
        "ffmpeg",
        "-loglevel", "warning",  # Reducir logs
        "-threads", "1",         # Limitar a 1 hilo
        "-re",
        "-stream_loop", "-1",
        "-i", "",  # Video
        "-stream_loop", "-1",
        "-i", "",  # Audio
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-x264-params", "threads=1:keyint=48:min-keyint=24",
        "-b:v", "1200k",        # Bitrate reducido
        "-maxrate", "1400k",
        "-bufsize", "2800k",     # 2x maxrate
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:-2",  # Escalar a 720p
        "-r", "24",              # FPS reducidos
        "-g", "48",              # Grupo GOP más largo
        "-c:a", "aac",
        "-b:a", "64k",           # Audio mono de baja calidad
        "-ac", "1",
        "-ar", "44100",
        "-f", "flv",
        RTMP_URL
    ]
    
    while True:
        try:
            video = random.choice(media['videos'])
            audio = random.choice(media['audios'])
            
            cmd = ffmpeg_base.copy()
            cmd[7] = video  # Índice para input video
            cmd[10] = audio  # Índice para input audio
            
            logging.info(f"🚀 Iniciando stream:\nVideo: {video}\nAudio: {audio}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            # Manejo ligero de logs
            for line in process.stdout:
                if "frame=" in line:
                    logging.info(line.strip())
            
            if process.wait() != 0:
                raise subprocess.CalledProcessError(process.returncode, ' '.join(cmd))
            
        except Exception as e:
            logging.error(f"❌ Error: {str(e)}")
            logging.info("🕒 Reintentando en 30 segundos...")
            time.sleep(30)

if __name__ == "__main__":
    start_stream()
