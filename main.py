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
                "-loglevel", "info",
                "-re",
                "-stream_loop", "-1",
                "-i", video,
                "-stream_loop", "-1",
                "-i", audio,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-b:v", "2500k",
                "-maxrate", "3000k",
                "-bufsize", "5000k",
                "-pix_fmt", "yuv420p",
                "-g", "50",
                "-r", "30",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100",
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
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    logging.info(output.strip())
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, ' '.join(cmd))
            
        except Exception as e:
            logging.error(f"❌ Error: {str(e)}")
            logging.info("🕒 Reintentando en 30 segundos...")
            time.sleep(30)

if __name__ == "__main__":
    start_stream()
