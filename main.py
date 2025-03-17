import os
import re
import random
import subprocess
import logging
import time
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from flask import Flask
from waitress import serve

app = Flask(__name__)

@app.route('/health')
def health_check():
    return "OK", 200

# Config logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Credenciales hardcodeadas
YOUTUBE_CREDS = {
    'client_id': '913486235878-8f86jgtuccrrcaai3456jab4ujbpan5s.apps.googleusercontent.com',
    'client_secret': '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',
    'refresh_token': '1//0hkLzswQpTRr3CgYIARAAGBESNwF-L9Ir8J2Bfhvmvgcw2RgCBi2LdNBd1DrEKJQCQoY8lj_sny5JfoUfgIe9MMcrpyHhvDfcOhk'
}

RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"

# Configuración rclone
RCLONE_CONFIG = {
    'videos': '/mnt/gdrive_videos',
    'sonidos': '/mnt/gdrive_sonidos',
    'musica': '/mnt/gdrive_musica'
}

THEME_KEYWORDS = {
    'lluvia': ['lluvia', 'rain', 'chuva', 'lluvialoop'],
    'fuego': ['fuego', 'fire', 'fogata', 'chimenea'],
    'viento': ['viento', 'wind', 'vent', 'ventisca'],
    'bosque': ['bosque', 'jungla', 'forest', 'selva']
}

class ContentManager:
    def __init__(self):
        self.media = {
            'videos': [],
            'jazz': [],
            'sonidos': {},
            'video_themes': {}
        }
        
    def load_media(self):
        try:
            # Cargar desde rclone
            # Modifica las rutas en ContentManager
            self.media['videos'] = self._get_files('/media/videos', ('.mp4', '.mkv'))
            self.media['jazz'] = self._get_files('/media/musica', ('.mp3',))
            
            if not self.media['videos']:
                raise Exception("No hay videos en Google Drive")
                
            # Procesar sonidos
            sonidos_files = self._get_files(RCLONE_CONFIG['sonidos'], ('.mp3', '.wav'))
            self.media['sonidos'] = {theme: [] for theme in THEME_KEYWORDS}
            self.media['sonidos']['otros'] = []
            
            for file in sonidos_files:
                filename = os.path.basename(file).lower()
                theme = next((t for t, keys in THEME_KEYWORDS.items() 
                            if any(k in filename for k in keys)), 'otros')
                self.media['sonidos'][theme].append(file)
            
            # Detectar temas de videos
            self.media['video_themes'] = {
                video: self._detect_video_theme(video) for video in self.media['videos']
            }
            
            logging.info("✅ Medios cargados correctamente")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error crítico: {str(e)}")
            return False

    def _get_files(self, folder, extensions):
        try:
            return [os.path.join(folder, f) for f in os.listdir(folder) 
                   if f.lower().endswith(extensions) and not f.startswith('.')]
        except FileNotFoundError:
            logging.error(f"❌ Carpeta no encontrada: {folder}")
            return []

    def _detect_video_theme(self, video_path):
        filename = os.path.basename(video_path).lower()
        return next((t for t, keys in THEME_KEYWORDS.items() 
                    if any(k in filename for k in keys)), 'otros')

class YouTubeManager:
    def __init__(self):
        self.youtube = None
        
    def authenticate(self):
        try:
            creds = Credentials(
                token=None,
                refresh_token=YOUTUBE_CREDS['refresh_token'],
                client_id=YOUTUBE_CREDS['client_id'],
                client_secret=YOUTUBE_CREDS['client_secret'],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=['https://www.googleapis.com/auth/youtube']
            )
            
            if not creds.valid:
                creds.refresh(Request())
                
            self.youtube = build('youtube', 'v3', credentials=creds)
            logging.info("✅ Autenticación YouTube OK")
            return True
        except Exception as e:
            logging.error(f"❌ Fallo autenticación: {str(e)}")
            return False

    def update_stream(self, title):
        try:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="active"
            ).execute()
            
            if not broadcasts.get('items'):
                logging.error("⚠️ Crea una transmisión ACTIVA en YouTube Studio")
                return False
                
            broadcast_id = broadcasts['items'][0]['id']
            
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_id,
                    "snippet": {
                        "title": title,
                        "description": "Streaming 24/7 de sonidos naturales",
                        "categoryId": "22"
                    }
                }
            ).execute()
            return True
        except Exception as e:
            logging.error(f"❌ Error actualizando stream: {str(e)}")
            return False

def generar_titulo(video_path):
    try:
        nombre = os.path.basename(video_path)
        partes = re.split(r'[_.-]', nombre)
        # Corregido: Paréntesis bien cerrados
        ubicacion = next(
            (p.capitalize() for p in partes 
             if any(kw in p.lower() 
                    for kw in ['cabana', 'bosque', 'rio', 'montana'])),  # Eliminada 'ñ' por seguridad
            "Ambiente"
        )
                        
        tema = next((t for t in THEME_KEYWORDS if t in nombre.lower()), 'relax')
        return f"{ubicacion} • {tema.capitalize()} • Streaming 24/7"
    except:
        return "Sonidos Naturales en Vivo"

def iniciar_stream():
    contenido = ContentManager()
    youtube = YouTubeManager()
    
    if not youtube.authenticate():
        return
    
    if not contenido.load_media():
        return
    
    secuencia = [
        ('jazz', 8), 
        ('naturaleza', 8),
        ('combinado', 8)
    ]
    fase_actual = 0
    inicio_fase = datetime.now()
    
    while True:
        try:
            # Rotar fases cada 8 horas
            if (datetime.now() - inicio_fase).total_seconds() >= secuencia[fase_actual][1] * 3600:
                fase_actual = (fase_actual + 1) % len(secuencia)
                inicio_fase = datetime.now()
                logging.info(f"🔄 Cambiando a fase: {secuencia[fase_actual][0].upper()}")
            
            # Seleccionar medios
            tema = secuencia[fase_actual][0]
            video = random.choice(contenido.media['videos'])
            video_tema = contenido.media['video_themes'][video]
            
            if tema == 'naturaleza':
                audio = random.choice(contenido.media['sonidos'].get(video_tema, []))
            elif tema == 'jazz':
                audio = random.choice(contenido.media['jazz'])
            else:
                audio = f"concat:{random.choice(contenido.media['jazz'])}|{random.choice(contenido.media['sonidos'].get(video_tema, []))}"
            
            # Actualizar YouTube
            titulo = generar_titulo(video)
            youtube.update_stream(titulo)
            
            # Comando FFmpeg
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video,
                "-i", audio,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-b:v", "2500k",
                "-maxrate", "3000k",
                "-bufsize", "5000k",
                "-pix_fmt", "yuv420p",
                "-g", "60",
                "-r", "30",
                "-c:a", "aac",
                "-b:a", "160k",
                "-ar", "48000",
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info(f"▶️ Iniciando {tema.upper()}\nVideo: {os.path.basename(video)}\nAudio: {os.path.basename(audio)}")
            
            proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            
            # Mantener proceso activo
            inicio = time.time()
            while time.time() - inicio < 28800:  # 8 horas
                time.sleep(10)
                
            proceso.terminate()
            logging.info("⏭️ Preparando siguiente transmisión...")
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"🔥 Error grave: {str(e)}")
            time.sleep(60)
            contenido.load_media()

def run_server():
    port = int(os.environ.get('PORT', 10000))
    serve(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    import threading
    
    # Servidor web en segundo plano
    threading.Thread(target=run_server, daemon=True).start()
    
    # Esperar montaje de rclone
    time.sleep(15)
    
    # Iniciar streaming
    iniciar_stream()
