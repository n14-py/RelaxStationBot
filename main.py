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
        "-loglevel", "warning",
        "-threads", "1",
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
        "-x264-params", "keyint=48:min-keyint=24",
        "-b:v", "1000k",
        "-maxrate", "1200k",
        "-bufsize", "2400k",
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease",
        "-r", "24",
        "-g", "48",
        "-c:a", "aac",
        "-b:a", "64k",
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
            cmd[7] = video  # Índice corregido para input video
            cmd[10] = audio  # Índice corregido para input audio
            
            logging.info(f"🚀 Iniciando stream:\nVideo: {video}\nAudio: {audio}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            # Manejo optimizado de logs
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if "frame=" in line:
                    logging.info(line.strip())
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, ' '.join(cmd))
            
        except Exception as e:
            logging.error(f"❌ Error: {str(e)}")
            logging.info("🕒 Reintentando en 30 segundos...")
            time.sleep(30)

if __name__ == "__main__":
    start_stream()
