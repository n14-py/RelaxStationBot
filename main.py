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

# Configuración básica
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

SCOPES = ['https://www.googleapis.com/auth/youtube']
CLIENT_SECRETS_FILE = 'client_secret.json'
RTMP_URL = os.getenv("RTMP_URL")

THEME_KEYWORDS = {
    'lluvia': ['lluvia', 'rain', 'chuva', 'lluvialoop'],
    'fuego': ['fuego', 'fire', 'fogata', 'chimenea', 'fogue'],
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
        self.last_update = time.time()
        
    def load_media(self):
        try:
            self.media['videos'] = self._get_files('videos', ('.mp4', '.mkv'))
            self.media['jazz'] = self._get_files('musica_jazz', ('.mp3',))
            
            sonidos_files = self._get_files('sonidos_naturaleza', ('.mp3', '.wav'))
            self.media['sonidos'] = {theme: [] for theme in THEME_KEYWORDS}
            self.media['sonidos']['otros'] = []
            
            for file in sonidos_files:
                filename = os.path.basename(file).lower()
                theme = next((t for t, keys in THEME_KEYWORDS.items() 
                            if any(k in filename for k in keys)), 'otros')
                self.media['sonidos'][theme].append(file)
            
            self.media['video_themes'] = {}
            for video in self.media['videos']:
                self.media['video_themes'][video] = self._detect_video_theme(video)
            
            self.last_update = time.time()
            logging.info("✅ Medios actualizados correctamente")
        except Exception as e:
            logging.error(f"❌ Error cargando medios: {str(e)}")

    def _get_files(self, folder, extensions):
        return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) 
                if f.lower().endswith(extensions) and not f.startswith('.')]

    def _detect_video_theme(self, video_path):
        filename = os.path.basename(video_path).lower()
        return next((theme for theme, keywords in THEME_KEYWORDS.items() 
                    if any(k in filename for k in keywords)), 'otros')

class YouTubeManager:
    def __init__(self):
        self.credentials = None
        self.youtube = None
        self.live_broadcast_id = None
        
    def authenticate(self):
        try:
            self.credentials = Credentials(
                token=None,
                refresh_token=os.getenv('YOUTUBE_REFRESH_TOKEN'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv('CLIENT_ID'),
                client_secret=os.getenv('CLIENT_SECRET')
            )
            
            if not self.credentials.valid:
                self.credentials.refresh(Request())
                
            self.youtube = build('youtube', 'v3', credentials=self.credentials)
            logging.info("✅ Autenticación con YouTube exitosa")
            return True
        except Exception as e:
            logging.error(f"❌ Error de autenticación: {str(e)}")
            return False

    def update_stream_info(self, title):
        try:
            request = self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": self.get_live_broadcast_id(),
                    "snippet": {
                        "title": title,
                        "description": "Relájate con sonidos naturales y música suave las 24 horas del día",
                        "categoryId": "22"
                    }
                }
            )
            request.execute()
            return True
        except Exception as e:
            logging.error(f"❌ Error actualizando stream: {str(e)}")
            return False
    
    def get_live_broadcast_id(self):
        if not self.live_broadcast_id:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="active"
            ).execute()
            
            if broadcasts['items']:
                self.live_broadcast_id = broadcasts['items'][0]['id']
            else:
                logging.error("No se encontró transmisión activa")
                raise Exception("No active live stream found")
        
        return self.live_broadcast_id

def generate_title(video_path):
    try:
        base_name = os.path.basename(video_path)
        clean_name = re.sub(r'\d+|[()]', ' ', base_name)
        
        parts = re.split(r'[_.]', clean_name)
        location = next((p.capitalize() for p in parts if any(kw in p.lower() for kw in 
                     ['departamento', 'cabana', 'cueva', 'sala'])), "Ambiente")
        
        theme_keyword = next((p.lower() for p in parts if any(
            k in p.lower() for k in sum(THEME_KEYWORDS.values(), []))), "")
        
        theme_map = {
            'lluvia': 'Lluvia Relajante',
            'fuego': 'Fuego Cremoso',
            'viento': 'Viento Fresco',
            'bosque': 'Bosque Tropical'
        }
        theme = theme_map.get(next((t for t, keys in THEME_KEYWORDS.items() 
                                  if any(k in theme_keyword for k in keys)), 'otros'), 
                                  'Sonidos Naturales')
        
        return f"{location} • {theme} • Transmisión 24/7"
    except:
        return "Ambiente Relajante en Vivo 24/7"

def start_stream():
    content = ContentManager()
    youtube = YouTubeManager()
    
    content.load_media()
    
    if not youtube.authenticate():
        return
    
    schedule = [
        ('jazz', timedelta(hours=8)),
        ('naturaleza', timedelta(hours=8)),
        ('combinado', timedelta(hours=8))
    ]
    current_phase = 0
    phase_start = datetime.now()
    
    while True:
        try:
            if time.time() - content.last_update > 3600:
                content.load_media()
            
            elapsed = datetime.now() - phase_start
            if elapsed >= schedule[current_phase][1]:
                current_phase = (current_phase + 1) % 3
                phase_start = datetime.now()
                logging.info(f"🔄 Cambiando a fase: {schedule[current_phase][0].upper()}")
            
            theme = schedule[current_phase][0]
            video = random.choice(content.media['videos'])
            video_theme = content.media['video_themes'][video]
            
            # Selección de audio
            if theme == 'naturaleza':
                audio = random.choice(content.media['sonidos'].get(video_theme, []))
            elif theme == 'jazz':
                audio = random.choice(content.media['jazz'])
            else:
                audio_jazz = random.choice(content.media['jazz'])
                audio_nat = random.choice(content.media['sonidos'].get(video_theme, []))
                audio = f"concat:{audio_jazz}|{audio_nat}"
            
            title = generate_title(video)
            youtube.update_stream_info(title)
            
            cmd = [
                "ffmpeg",
                "-loglevel", "warning",
                "-re",
                "-stream_loop", "-1",
                "-i", video,
                "-i", audio,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-b:v", "2000k",
                "-maxrate", "2500k",
                "-bufsize", "5000k",
                "-pix_fmt", "yuv420p",
                "-g", "50",
                "-r", "25",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-t", "08:00:00",
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info(f"🎬 Iniciando transmisión {theme.upper()}:\n📹 Video: {video}\n🔊 Audio: {audio}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            start_time = time.time()
            while time.time() - start_time < 28800:  # 8 horas
                output = process.stdout.readline()
                if output:
                    logging.info(output.strip())
                time.sleep(1)
            
            process.terminate()
            logging.info("🔄 Preparando siguiente transmisión...")
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"🔥 Error crítico: {str(e)}")
            time.sleep(60)
            content.load_media()

if __name__ == "__main__":
    start_stream()
