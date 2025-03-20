import os
import re
import random
import subprocess
import logging
import time
import json
import warnings
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import Flask
from waitress import serve

# Configurar warnings
warnings.filterwarnings("ignore", message="file_cache is only supported with oauth2client<4.0.0")

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

# ========== CONFIGURACIÓN GOOGLE DRIVE ==========
CARPETA_VIDEOS = '1uLrhXne1gAS26iuykRbfQJvCga9ND3K9' 
CARPETA_SONIDOS = '1cbP-K-jTDh2J_jGJL4cDKNte6f8OIC6q'
CARPETA_MUSICA = '1xVXZAbgLSMtCY48jNT99XFQG2Pb_5gt9'
SCOPES_DRIVE = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# ========== CONFIGURACIÓN YOUTUBE ==========
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2/tumy-gch3-dx73-cg5r-20dy"
SCOPES_YOUTUBE = ['https://www.googleapis.com/auth/youtube']
YOUTUBE_CREDS = {
    'client_id': '913486235878-8f86jgtuccrrcaai3456jab4ujbpan5s.apps.googleusercontent.com',
    'client_secret': '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',
    'refresh_token': '1//0hkLzswQpTRr3CgYIARAAGBESNwF-L9Ir8J2Bfhvmvgcw2RgCBi2LdNBd1DrEKJQCQoY8lj_sny5JfoUfgIe9MMcrpyHhvDfcOhk'
}

# Palabras clave para categorización
THEME_KEYWORDS = {
    'lluvia': ['lluvia', 'rain', 'chuva'],
    'fuego': ['fuego', 'fire', 'fogata'],
    'bosque': ['bosque', 'jungla', 'forest']
}

# ========== AUTENTICACIÓN GOOGLE DRIVE ==========
def autenticar_google_drive():
    try:
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
                    scopes=SCOPES_DRIVE
                )
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json',
                    SCOPES_DRIVE,
                    redirect_uri=client_config['redirect_uris'][0]
                )
                auth_url, _ = flow.authorization_url(prompt='consent')
                print(f"\n🔑 AUTENTICACIÓN REQUERIDA 🔑\nVisita esta URL:\n{auth_url}\n")
                code = input("Ingresa el código de autorización: ").strip()
                creds = flow.fetch_token(code=code)
            
            with open('token.json', 'w') as token:
                json.dump({
                    'access_token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'expiry_date': creds.expiry.timestamp() if creds.expiry else None
                }, token)
        
        return build('drive', 'v3', credentials=creds)
    
    except Exception as e:
        logging.error(f"🔥 Error fatal en autenticación Drive: {str(e)}")
        raise

# ========== GESTIÓN DE CONTENIDO ==========
class ContentManager:
    def __init__(self):
        self.drive_service = autenticar_google_drive()
        self.media = {'videos': [], 'jazz': [], 'sonidos': {}}
        self.load_media()

    def listar_archivos(self, folder_id):
        try:
            results = self.drive_service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="files(id, name, mimeType)",
                pageSize=1000
            ).execute()
            return results.get('files', [])
        except Exception as e:
            logging.error(f"📂 Error listando archivos: {str(e)}")
            return []

    def cargar_multimedia(self, folder_id, extensiones):
        try:
            return [
                {
                    'name': f['name'],
                    'url': f"https://drive.google.com/uc?export=download&id={f['id']}"
                } for f in self.listar_archivos(folder_id)
                if f['name'].lower().endswith(tuple(extensiones))
            ]
        except Exception as e:
            logging.error(f"🎵 Error cargando multimedia: {str(e)}")
            return []

    def load_media(self):
        try:
            # Cargar videos (MP4/MKV)
            self.media['videos'] = self.cargar_multimedia(CARPETA_VIDEOS, ['.mp4', '.mkv'])
            if not self.media['videos']:
                raise ValueError("🚫 No se encontraron videos en la carpeta especificada")
            
            # Cargar música (MP3/WAV)
            self.media['jazz'] = self.cargar_multimedia(CARPETA_MUSICA, ['.mp3', '.wav'])
            if not self.media['jazz']:
                raise ValueError("🎷 No se encontró música jazz")
            
            # Cargar y clasificar sonidos
            sonidos_brutos = self.cargar_multimedia(CARPETA_SONIDOS, ['.mp3', '.wav'])
            self.media['sonidos'] = {tema: [] for tema in THEME_KEYWORDS}
            self.media['sonidos']['otros'] = []
            
            for sonido in sonidos_brutos:
                nombre = sonido['name'].lower()
                tema = next((t for t, keys in THEME_KEYWORDS.items() if any(k in nombre for k in keys)), 'otros')
                self.media['sonidos'][tema].append(sonido)
            
            logging.info("✅ Medios cargados correctamente")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error crítico: {str(e)}")
            return False

# ========== GESTIÓN YOUTUBE ==========
class YouTubeManager:
    def __init__(self):
        self.youtube = None
        self.authenticate()

    def authenticate(self):
        try:
            creds = Credentials(
                token=None,
                refresh_token=YOUTUBE_CREDS['refresh_token'],
                client_id=YOUTUBE_CREDS['client_id'],
                client_secret=YOUTUBE_CREDS['client_secret'],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=SCOPES_YOUTUBE
            )
            creds.refresh(Request())
            self.youtube = build('youtube', 'v3', credentials=creds)
            logging.info("✅ Autenticación YouTube exitosa")
            return True
        except Exception as e:
            logging.error(f"❌ Fallo en autenticación YouTube: {str(e)}")
            return False

    def actualizar_transmision(self, titulo):
        try:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="snippet,status",
                broadcastStatus="active"
            ).execute()
            
            if not broadcasts.get('items'):
                logging.error("⚠️ Primero crea una transmisión ACTIVA en YouTube Studio")
                return False
                
            broadcast_id = broadcasts['items'][0]['id']
            
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_id,
                    "snippet": {
                        "title": titulo,
                        "description": "Streaming 24/7 de sonidos naturales • Relájate con nosotros",
                        "categoryId": "22"
                    }
                }
            ).execute()
            
            logging.info(f"📺 Título actualizado: {titulo}")
            return True
        except Exception as e:
            logging.error(f"❌ Error actualizando transmisión: {str(e)}")
            return False

# ========== FUNCIONES PRINCIPALES ==========
def generar_titulo(nombre_video):
    try:
        palabras = re.split(r'[_\-\s.]+', nombre_video)
        ubicacion = next((p.capitalize() for p in palabras if any(kw in p.lower() for kw in ['bosque', 'rio', 'montaña'])), "Naturaleza")
        tema = next((t for t in THEME_KEYWORDS if t in nombre_video.lower()), 'relax')
        return f"{ubicacion} • Sonidos de {tema.capitalize()} • 24/7"
    except:
        return "Sonidos Naturales en Vivo 🌿✨"

def ciclo_transmision():
    contenido = ContentManager()
    youtube = YouTubeManager()
    
    if not contenido.media['videos'] or not youtube.youtube:
        return
    
    secuencias = [('jazz', 2), ('naturaleza', 2), ('combinado', 2)]  # 2 horas cada fase para pruebas
    fase_actual = 0
    inicio_fase = datetime.now()
    
    while True:
        try:
            # Rotación de fases
            tiempo_transcurrido = (datetime.now() - inicio_fase).total_seconds()
            if tiempo_transcurrido >= secuencias[fase_actual][1] * 3600:
                fase_actual = (fase_actual + 1) % len(secuencias)
                inicio_fase = datetime.now()
                logging.info(f"🔄 Cambiando a fase: {secuencias[fase_actual][0].upper()}")
            
            # Selección de contenido
            fase = secuencias[fase_actual][0]
            video = random.choice(contenido.media['videos'])
            
            if fase == 'naturaleza':
                audio = random.choice(contenido.media['sonidos'].get('bosque', []) + contenido.media['sonidos'].get('lluvia', []))
            elif fase == 'jazz':
                audio = random.choice(contenido.media['jazz'])
            else:
                audio = f"concat:{random.choice(contenido.media['jazz'])['url']}|{random.choice(contenido.media['sonidos']['bosque'])['url']}"
            
            # Actualizar YouTube
            titulo = generar_titulo(video['name'])
            youtube.actualizar_transmision(titulo)
            
            # Iniciar FFmpeg
            comando = [
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
            
            logging.info(f"\n🎬 Iniciando {fase.upper()}:\nVideo: {video['name']}\nAudio: {audio['name'] if isinstance(audio, dict) else 'Mix'}")
            
            proceso = subprocess.Popen(comando)
            
            # Mantener transmisión por tiempo de fase
            time.sleep(secuencias[fase_actual][1] * 3600)
            proceso.terminate()
            logging.info("⏭️ Transición a siguiente fase...")
            
        except Exception as e:
            logging.error(f"🔥 Error en ciclo de transmisión: {str(e)}")
            time.sleep(60)

def ejecutar_servidor():
    port = int(os.environ.get('PORT', 10000))
    serve(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    import threading
    threading.Thread(target=ejecutar_servidor, daemon=True).start()
    time.sleep(2)
    ciclo_transmision()
