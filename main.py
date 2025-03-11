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
        "-stream_loop", "-1",
        "-i", "",  # Video
        "-stream_loop", "-1",
        "-i", "",  # Audio
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-x264-params", "keyint=30:min-keyint=15:scenecut=0",
        "-b:v", "800k",        
        "-maxrate", "1000k",
        "-bufsize", "2000k",
        "-vf", "scale=854:480:force_original_aspect_ratio=decrease", 
        "-r", "20",            
        "-g", "20",
        "-c:a", "aac",
        "-b:a", "48k",         
        "-ac", "1",
        "-ar", "22050",
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
