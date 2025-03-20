import os
import re
import random
import subprocess
import logging
import time
import json
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import Flask
from waitress import serve

app = Flask(__name__)

@app.route('/health')
def health_check():
    return "OK", 200

# Configuración logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configuración de Google Drive
CARPETA_VIDEOS = '1uLrhXne1gAS26iuykRbfQJvCga9ND3K9'
CARPETA_SONIDOS = '1cbP-K-jTDh2J_jGJL4cDKNte6f8OIC6q'
CARPETA_MUSICA = '1xVXZAbgLSMtCY48jNT99XFQG2Pb_5gt9'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Configuración de YouTube
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"
YOUTUBE_CREDS = {
    'client_id': '913486235878-8f86jgtuccrrcaai3456jab4ujbpan5s.apps.googleusercontent.com',
    'client_secret': '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',
    'refresh_token': '1//0hkLzswQpTRr3CgYIARAAGBESNwF-L9Ir8J2Bfhvmvgcw2RgCBi2LdNBd1DrEKJQCQoY8lj_sny5JfoUfgIe9MMcrpyHhvDfcOhk'
}

THEME_KEYWORDS = {
    'lluvia': ['lluvia', 'rain', 'chuva', 'lluvialoop'],
    'fuego': ['fuego', 'fire', 'fogata', 'chimenea'],
    'viento': ['viento', 'wind', 'vent', 'ventisca'],
    'bosque': ['bosque', 'jungla', 'forest', 'selva']
}

def autenticar_google_drive():
    with open('credentials.json') as f:
        client_config = json.load(f)['web']
    
    creds = None
    if os.path.exists('token.json'):
        with open('token.json') as token:
            token_data = json.load(token)
            creds = Credentials(
                token=token_data['access_token'],
                refresh_token=token_data['refresh_token'],
                client_id=client_config['client_id'],
                client_secret=client_config['client_secret'],
                token_uri=client_config['token_uri'],
                scopes=SCOPES
            )
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json',
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f"\n🔑 Autenticación requerida: {auth_url}\n")
            code = input("Ingresa el código de autorización: ").strip()
            creds = flow.fetch_token(code=code)
        
        with open('token.json', 'w') as token:
            json.dump({
                'access_token': creds.token,
                'refresh_token': creds.refresh_token,
                'expiry_date': creds.expiry.timestamp() if creds.expiry else None
            }, token)
    
    return build('drive', 'v3', credentials=creds)

class ContentManager:
    def __init__(self):
        self.drive_service = autenticar_google_drive()
        self.media = {
            'videos': [],
            'jazz': [],
            'sonidos': {},
            'video_themes': {}
        }
        
    def listar_archivos(self, folder_id):
        results = self.drive_service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name, mimeType)",
            pageSize=1000
        ).execute()
        return results.get('files', [])
    
    def generar_url(self, file_id):
        return f"https://drive.google.com/uc?export=download&id={file_id}"
        
    def load_media(self):
        try:
            # Cargar videos
            videos = []
            for file in self.listar_archivos(CARPETA_VIDEOS):
                if file['name'].lower().endswith(('.mp4', '.mkv')):
                    videos.append({
                        'name': file['name'],
                        'url': self.generar_url(file['id'])
                    })
            self.media['videos'] = videos
            
            # Cargar música jazz
            jazz = []
            for file in self.listar_archivos(CARPETA_MUSICA):
                if file['name'].lower().endswith(('.mp3', '.wav')):
                    jazz.append({
                        'name': file['name'],
                        'url': self.generar_url(file['id'])
                    })
            self.media['jazz'] = jazz
            
            # Cargar y clasificar sonidos
            self.media['sonidos'] = {theme: [] for theme in THEME_KEYWORDS}
            self.media['sonidos']['otros'] = []
            
            for file in self.listar_archivos(CARPETA_SONIDOS):
                if file['name'].lower().endswith(('.mp3', '.wav')):
                    filename = file['name'].lower()
                    theme = next((t for t, keys in THEME_KEYWORDS.items() 
                                if any(k in filename for k in keys)), 'otros')
                    self.media['sonidos'][theme].append({
                        'name': file['name'],
                        'url': self.generar_url(file['id'])
                    })
            
            # Detectar temas de videos
            for video in self.media['videos']:
                self.media['video_themes'][video['url']] = self._detect_video_theme(video['name'])
            
            logging.info("✅ Medios cargados correctamente")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error cargando medios: {str(e)}")
            return False
    
    def _detect_video_theme(self, filename):
        filename = filename.lower()
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
            logging.info("✅ Autenticación YouTube exitosa")
            return True
        except Exception as e:
            logging.error(f"❌ Fallo en autenticación YouTube: {str(e)}")
            return False

    def update_stream(self, title):
        try:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="active"
            ).execute()
            
            if not broadcasts.get('items'):
                logging.error("⚠️ No hay transmisiones activas en YouTube")
                return False
                
            broadcast_id = broadcasts['items'][0]['id']
            
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_id,
                    "snippet": {
                        "title": title,
                        "description": "Transmisión 24/7 de sonidos naturales y relajantes",
                        "categoryId": "22"
                    }
                }
            ).execute()
            
            logging.info(f"📺 Título actualizado: {title}")
            return True
        except Exception as e:
            logging.error(f"❌ Error actualizando stream: {str(e)}")
            return False

def generar_titulo(video_name):
    try:
        partes = re.split(r'[_.-]', video_name)
        ubicacion = next(
            (p.capitalize() for p in partes 
             if any(kw in p.lower() for kw in ['cabana', 'bosque', 'rio', 'montana'])),
            "Naturaleza"
        )
        tema = next((t for t in THEME_KEYWORDS if t in video_name.lower()), 'relax')
        return f"{ubicacion} • Sonidos de {tema.capitalize()} • 24/7 Live"
    except:
        return "Sonidos Naturales en Vivo 🌿"

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
            if (datetime.now() - inicio_fase).total_seconds() >= secuencia[fase_actual][1] * 3600:
                fase_actual = (fase_actual + 1) % len(secuencia)
                inicio_fase = datetime.now()
                logging.info(f"🔄 Cambiando a fase: {secuencia[fase_actual][0].upper()}")
            
            # Selección de medios
            tema = secuencia[fase_actual][0]
            video = random.choice(contenido.media['videos'])
            video_tema = contenido.media['video_themes'][video['url']]
            
            if tema == 'naturaleza':
                audio = random.choice(contenido.media['sonidos'].get(video_tema, []))
            elif tema == 'jazz':
                audio = random.choice(contenido.media['jazz'])
            else:
                audio_jazz = random.choice(contenido.media['jazz'])
                audio_naturaleza = random.choice(contenido.media['sonidos'].get(video_tema, []))
                audio = f"concat:{audio_jazz['url']}|{audio_naturaleza['url']}"
            
            # Actualizar YouTube
            titulo = generar_titulo(video['name'])
            youtube.update_stream(titulo)
            
            # Comando FFmpeg
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-i", audio['url'] if isinstance(audio, dict) else audio,
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
            
            logging.info(f"▶️ Iniciando transmisión {tema.upper()}\nVideo: {video['name']}\nAudio: {audio['name'] if isinstance(audio, dict) else 'Combinado'}")
            
            proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            
            # Mantener proceso activo 8 horas
            inicio = time.time()
            while time.time() - inicio < 28800:
                time.sleep(10)
                
            proceso.terminate()
            logging.info("⏭️ Preparando siguiente transmisión...")
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"🔥 Error crítico: {str(e)}")
            time.sleep(60)
            contenido.load_media()

def run_server():
    port = int(os.environ.get('PORT', 10000))
    serve(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_server, daemon=True).start()
    time.sleep(5)
    iniciar_stream()
