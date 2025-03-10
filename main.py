import os
import random
import subprocess
import logging
import time

# Configuración
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"
VIDEO_DIR = "videos"
AUDIO_DIR = "musica_jazz"

def load_media():
    """Cargar archivos multimedia válidos"""
    videos = []
    audios = []
    
    for root, _, files in os.walk(VIDEO_DIR):
        for file in files:
            if file.endswith((".mp4", ".mkv", ".mov")):
                videos.append(os.path.join(root, file))
    
    for root, _, files in os.walk(AUDIO_DIR):
        for file in files:
            if file.endswith((".mp3", ".wav", ".aac")):
                audios.append(os.path.join(root, file))
    
    if not videos:
        raise FileNotFoundError(f"No videos found in {VIDEO_DIR}")
    if not audios:
        raise FileNotFoundError(f"No audio files found in {AUDIO_DIR}")
    
    return videos, audios

def create_stream_command(video_path, audio_path):
    """Generar comando FFmpeg optimizado"""
    return [
        "ffmpeg",
        "-loglevel", "info",
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

def main():
    videos, audios = load_media()
    
    while True:
        try:
            video = random.choice(videos)
            audio = random.choice(audios)
            
            logging.info(f"Iniciando transmisión con:\nVideo: {video}\nAudio: {audio}")
            
            cmd = create_stream_command(video, audio)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitorear salida
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    logging.info(output.strip())
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
                
        except Exception as e:
            logging.error(f"Error en transmisión: {str(e)}")
            logging.info("Reintentando en 30 segundos...")
            time.sleep(30)

if __name__ == "__main__":
    main()
