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
app = Flask(__name__)

@app.route('/health')
def health_check():
    try:
        # Verificar montajes
        required_dirs = ['/media/videos', '/media/sonidos_naturaleza', '/media/musica_jazz']
        for dir in required_dirs:
            if not os.path.ismount(dir):
                return "Mounts not ready", 503
                
        # Verificar archivos
        if not os.listdir('/media/videos'):
            return "No media files", 503
            
        return "OK", 200
    except Exception as e:
        return f"Error: {str(e)}", 500



# Configuración básica
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configuración Google Drive (Tu cuenta de archivos)
DRIVE_CREDS = {
    'client_id': '739473350205-4ma0u6tqp33sdug815b67n4qki69elop.apps.googleusercontent.com',
    'client_secret': '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',
    'refresh_token': '1//0hHhOR0N_GQkxCgYIARAAGBESNwF-L9IruyOLldAO6w5xmHBYPx_PFUKkT9kUjMHsPlKa_7T5YkegxaFmDfVDc-CD3r7iu2uiEHo'
}

# Configuración YouTube (Tu cuenta de streaming)
YOUTUBE_CREDS = {
    'client_id': '913486235878-8f86jgtuccrrcaai3456jab4ujbpan5s.apps.googleusercontent.com',  # Reemplazar con tus datos reales
    'client_secret': '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',  # Reemplazar con tus datos reales
    'refresh_token': '1//0hkLzswQpTRr3CgYIARAAGBESNwF-L9Ir8J2Bfhvmvgcw2RgCBi2LdNBd1DrEKJQCQoY8lj_sny5JfoUfgIe9MMcrpyHhvDfcOhk'  # Reemplazar con tus datos reales
}

RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"
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
            # Cargar desde Google Drive montado
            self.media['videos'] = self._get_files('/media/videos', ('.mp4', '.mkv'))
            self.media['jazz'] = self._get_files('/media/musica_jazz', ('.mp3',))
            
            sonidos_files = self._get_files('/media/sonidos_naturaleza', ('.mp3', '.wav'))
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
        
    def authenticate(self):
        try:
            self.credentials = Credentials(
                token=None,
                refresh_token=YOUTUBE_CREDS['refresh_token'],
                client_id=YOUTUBE_CREDS['client_id'],
                client_secret=YOUTUBE_CREDS['client_secret'],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=['https://www.googleapis.com/auth/youtube']
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
            broadcast = self.youtube.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="active"
            ).execute().get('items', [{}])[0]
            
            if not broadcast:
                logging.error("No hay transmisiones activas")
                return False
                
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast['id'],
                    "snippet": {
                        "title": title,
                        "description": "Relájate con sonidos naturales 24/7",
                        "categoryId": "22"
                    }
                }
            ).execute()
            return True
        except Exception as e:
            logging.error(f"❌ Error actualizando stream: {str(e)}")
            return False

def generate_title(video_path):
    try:
        base_name = os.path.basename(video_path)
        parts = re.split(r'[_.]', re.sub(r'\d+|[()]', ' ', base_name))
        location = next((p.capitalize() for p in parts if any(kw in p.lower() 
                       for kw in ['departamento', 'cabana', 'cueva', 'sala'])), "Ambiente")
        
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

    try:
        logging.info("🔍 Verificando logs de montaje Rclone...")
        if os.path.exists('/tmp/rclone.log'):
            with open('/tmp/rclone.log', 'r') as f:
                logs = f.read()
                logging.info(f"📄 Logs de Rclone:\n{logs}")
        else:
            logging.warning("⚠️ Archivo de logs de Rclone no encontrado")
    except Exception as e:
        logging.error(f"❌ Error leyendo logs: {str(e)}")
    
    content = ContentManager()
    youtube = YouTubeManager()
    
    if not youtube.authenticate():
        return
    
    content.load_media()
    
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
            
            if theme == 'naturaleza':
                audio = random.choice(content.media['sonidos'].get(video_theme, []))
            elif theme == 'jazz':
                audio = random.choice(content.media['jazz'])
            else:
                audio = f"concat:{random.choice(content.media['jazz'])}|{random.choice(content.media['sonidos'].get(video_theme, []))}"
            
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
            
            logging.info(f"🎬 Iniciando transmisión {theme.upper()}:\n📹 {video}\n🔊 {audio}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            start_time = time.time()
            while time.time() - start_time < 28800:
                output = process.stdout.readline()
                if output: logging.info(output.strip())
                time.sleep(1)
            
            process.terminate()
            logging.info("🔄 Preparando siguiente transmisión...")
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"🔥 Error crítico: {str(e)}")
            time.sleep(60)
            content.load_media()

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    start_stream()
