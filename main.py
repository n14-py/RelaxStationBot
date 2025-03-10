import os
import random
import subprocess
import logging
import time

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Constantes
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tu-clave-secreta"
VIDEO_DIR = "videos"
AUDIO_DIR = "musica_jazz"

class StreamManager:
    def __init__(self):
        self.process = None
        self.current_video = None
        self.current_audio = None
        
    def load_media(self):
        """Cargar archivos multimedia válidos"""
        def get_files(directory, extensions):
            media_files = []
            for root, _, files in os.walk(directory):
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        media_files.append(os.path.join(root, file))
            return media_files
        
        videos = get_files(VIDEO_DIR, (".mp4", ".mkv", ".mov"))
        audios = get_files(AUDIO_DIR, (".mp3", ".wav", ".aac"))
        
        if not videos:
            raise FileNotFoundError(f"No se encontraron videos en {VIDEO_DIR}")
        if not audios:
            raise FileNotFoundError(f"No se encontraron audios en {AUDIO_DIR}")
            
        return videos, audios

    def create_stream_command(self, video_path, audio_path):
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

    def start_stream(self, video, audio):
        """Iniciar transmisión"""
        self.current_video = video
        self.current_audio = audio
        
        cmd = self.create_stream_command(video, audio)
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        
        # Monitorear salida
        while True:
            output = self.process.stdout.readline()
            if output == '' and self.process.poll() is not None:
                break
            if output:
                logging.info(output.strip())
                
        return self.process.returncode

    def restart_stream(self):
        """Reiniciar transmisión"""
        if self.process:
            self.process.terminate()
        return self.run()

    def run(self):
        """Ejecutar flujo principal"""
        videos, audios = self.load_media()
        
        while True:
            try:
                video = random.choice(videos)
                audio = random.choice(audios)
                
                logging.info(f"Iniciando transmisión:\nVideo: {video}\nAudio: {audio}")
                
                return_code = self.start_stream(video, audio)
                
                if return_code != 0:
                    raise subprocess.CalledProcessError(return_code, "ffmpeg")
                    
            except Exception as e:
                logging.error(f"Error: {str(e)}")
                logging.info("Reintentando en 30 segundos...")
                time.sleep(30)

if __name__ == "__main__":
    stream_manager = StreamManager()
    stream_manager.run()
