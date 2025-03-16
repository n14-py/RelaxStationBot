import os
import re
import random
import subprocess
import logging
import time
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Configuración básica
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

SCOPES = ['https://www.googleapis.com/auth/youtube']
CLIENT_SECRETS_FILE = 'client_secret.json'
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"

# Diccionario de detección de temas
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
            # Cargar archivos
            self.media['videos'] = self._get_files('videos', ('.mp4', '.mkv'))
            self.media['jazz'] = self._get_files('musica_jazz', ('.mp3'))
            
            # Cargar y clasificar sonidos
            sonidos_files = self._get_files('sonidos_naturaleza', ('.mp3', '.wav'))
            self.media['sonidos'] = {theme: [] for theme in THEME_KEYWORDS}
            self.media['sonidos']['otros'] = []
            
            for file in sonidos_files:
                filename = os.path.basename(file).lower()
                theme = next((t for t, keys in THEME_KEYWORDS.items() 
                            if any(k in filename for k in keys)), 'otros')
                self.media['sonidos'][theme].append(file)
            
            # Mapear temas de videos
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
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            self.credentials = flow.run_local_server(port=8080)
            self.youtube = build('youtube', 'v3', credentials=self.credentials)
            logging.info("✅ Autenticación con YouTube exitosa")
        except Exception as e:
            logging.error(f"❌ Error de autenticación: {str(e)}")
            raise

    def update_stream_info(self, title, thumbnail_path=None):
        try:
            request = self.youtube.liveBroadcasts().update(
                part="snippet,status",
                body={
                    "id": self.live_broadcast_id,
                    "snippet": {
                        "title": title,
                        "description": "Relájate con sonidos naturales y música suave las 24 horas del día",
                        "categoryId": "22"
                    },
                    "status": {
                        "privacyStatus": "public"
                    }
                }
            )
            response = request.execute()
            
            if thumbnail_path:
                self.youtube.thumbnails().set(
                    videoId=response['id'],
                    media_body=thumbnail_path
                ).execute()
                logging.info(f"✅ Miniatura actualizada: {thumbnail_path}")
                
            return True
        except Exception as e:
            logging.error(f"❌ Error actualizando stream: {str(e)}")
            return False

def generate_title(video_path):
    try:
        base_name = os.path.basename(video_path)
        clean_name = re.sub(r'\d+|[()]', ' ', base_name)
        
        # Extraer ubicación y tema
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

def generate_thumbnail(video_path):
    try:
        output_path = "thumbnail.jpg"
        subprocess.run([
            "ffmpeg",
            "-i", video_path,
            "-ss", "00:01:00",
            "-vframes", "1",
            "-y", output_path
        ], check=True, capture_output=True)
        return output_path
    except Exception as e:
        logging.error(f"❌ Error generando miniatura: {str(e)}")
        return None

def start_stream():
    content = ContentManager()
    youtube = YouTubeManager()
    
    content.load_media()
    youtube.authenticate()
    
    schedule = [
        ('jazz', timedelta(hours=8)),
        ('naturaleza', timedelta(hours=8)),
        ('combinado', timedelta(hours=8))
    ]
    current_phase = 0
    phase_start = datetime.now()
    
    while True:
        try:
            # Actualizar contenido cada hora
            if time.time() - content.last_update > 3600:
                content.load_media()
            
            # Determinar fase actual
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
                audio_files = content.media['sonidos'].get(video_theme, [])
                audio = random.choice(audio_files) if audio_files else ""
                if not audio:
                    logging.warning("⚠️ No hay sonidos para el tema del video, usando aleatorio")
                    audio = random.choice(sum(content.media['sonidos'].values(), []))
            elif theme == 'jazz':
                audio = random.choice(content.media['jazz'])
            else:
                audio_jazz = random.choice(content.media['jazz'])
                audio_nat = random.choice(content.media['sonidos'].get(video_theme, []))
                audio = f"concat:{audio_jazz}|{audio_nat}"
            
            # Generar metadatos
            title = generate_title(video)
            thumbnail = generate_thumbnail(video)
            
            # Actualizar YouTube
            if youtube.update_stream_info(title, thumbnail):
                logging.info(f"📺 Título actualizado: {title}")
            
            # Configurar FFmpeg
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
            
            # Monitorear transmisión
            start_time = time.time()
            while time.time() - start_time < 28800:  # 8horas
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
