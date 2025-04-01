import os
import random
import subprocess
import logging
import time
import requests
import hashlib
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import Flask
from waitress import serve
from urllib.parse import urlparse
import threading

app = Flask(__name__)

# Configuración logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configuración
RTMP_URL = os.getenv("RTMP_URL")
MEDIOS_URL = "https://raw.githubusercontent.com/n14-py/RelaxStationBot/master/medios.json"
YOUTUBE_CREDS = {
    'client_id': os.getenv("YOUTUBE_CLIENT_ID"),
    'client_secret': os.getenv("YOUTUBE_CLIENT_SECRET"),
    'refresh_token': os.getenv("YOUTUBE_REFRESH_TOKEN")
}

PALABRAS_CLAVE = {
    'lluvia': ['lluvia', 'rain', 'storm'],
    'fuego': ['fuego', 'fire', 'chimenea'],
    'bosque': ['bosque', 'jungla', 'forest'],
    'rio': ['rio', 'river', 'cascada'],
    'noche': ['noche', 'night', 'luna']
}

class GestorContenido:
    def __init__(self):
        self.media_cache_dir = os.path.abspath("./media_cache")
        os.makedirs(self.media_cache_dir, exist_ok=True)
        self.medios = self.cargar_medios()
    
    def obtener_extension_segura(self, url):
        try:
            parsed = urlparse(url)
            return os.path.splitext(parsed.path)[1].lower() or '.mp3'
        except:
            return '.mp3'

    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            ruta_local = os.path.join(self.media_cache_dir, f"{nombre_hash}.wav")
            
            if os.path.exists(ruta_local):
                return ruta_local
                
            temp_path = os.path.join(self.media_cache_dir, f"temp_{nombre_hash}.mp3")
            
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_path,
                "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
                ruta_local
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            os.remove(temp_path)
            return ruta_local
        except Exception as e:
            logging.error(f"Error procesando {url}: {str(e)}")
            return None

    def cargar_medios(self):
        try:
            datos = requests.get(MEDIOS_URL, timeout=10).json()
            for medio in datos['sonidos_naturaleza']:
                medio['local_path'] = self.descargar_audio(medio['url'])
            return datos
        except Exception as e:
            logging.error(f"Error cargando medios: {str(e)}")
            return {"videos": [], "musica": [], "sonidos_naturaleza": []}

class YouTubeManager:
    def __init__(self):
        self.youtube = self.autenticar()
    
    def autenticar(self):
        try:
            creds = Credentials(
                token="",
                refresh_token=YOUTUBE_CREDS['refresh_token'],
                client_id=YOUTUBE_CREDS['client_id'],
                client_secret=YOUTUBE_CREDS['client_secret'],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=['https://www.googleapis.com/auth/youtube']
            )
            creds.refresh(Request())
            return build('youtube', 'v3', credentials=creds)
        except Exception as e:
            logging.error(f"Error autenticación YouTube: {str(e)}")
            return None
    
    def actualizar_transmision(self, titulo, video_url):
        try:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet", broadcastStatus="active").execute()
            
            if broadcasts.get('items'):
                broadcast_id = broadcasts['items'][0]['id']
                self.youtube.liveBroadcasts().update(
                    part="snippet",
                    body={
                        "id": broadcast_id,
                        "snippet": {
                            "title": titulo,
                            "description": "Streaming 24/7 - Sonidos Naturales Relajantes",
                            "categoryId": "22"
                        }
                    }
                ).execute()
                logging.info(f"Actualizado YouTube: {titulo}")
        except Exception as e:
            logging.error(f"Error actualizando YouTube: {str(e)}")

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    while True:
        try:
            video = random.choice(gestor.medios['videos'])
            categoria = next((k for k,v in PALABRAS_CLAVE.items() if any(p in video['name'].lower() for p in v)), random.choice(list(PALABRAS_CLAVE.keys())))
            audio = random.choice([a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']])
            titulo = f"Sonidos de {categoria.capitalize()} 🌿 24/7"
            
            # Configuración FFmpeg Ultra-Optimizada
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-stream_loop", "-1",
                "-i", audio['local_path'],
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v", "libx264",
                "-preset", "fast",
                "-tune", "film",
                "-x264-params", "nal-hrd=cbr:keyint=60:min-keyint=60:scenecut=0",
                "-b:v", "5000k",
                "-maxrate", "5000k",
                "-bufsize", "7500k",
                "-g", "60",
                "-r", "30",
                "-vsync", "cfr",
                "-threads", "2",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "48000",
                "-af", "aresample=async=1:min_hard_comp=0.100000:first_pts=0",
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info(f"""
            🚀 TRANSMISIÓN ULTRA FLUIDA 1080p 🚀
            📺 Video: {video['name']}
            🔊 Audio: {audio['name']}
            ⚙️ Configuración profesional:
               - Resolución: 1920x1080
               - Bitrate: 5000k CBR
               - Preset: fast
               - Buffer: 7500k
               - FPS: 30 constante
               - Audio: AAC 128k @48kHz
            """)
            
            # Buffer inicial de 30 segundos
            logging.info("🔄 Cargando buffer inicial (30s)...")
            with open(os.devnull, 'w') as devnull:
                subprocess.run(cmd + ["-t", "30"], stdout=devnull, stderr=devnull)
            
            proceso = subprocess.Popen(cmd)
            start_time = time.time()
            
            def actualizar_youtube():
                time.sleep(600)
                if youtube.youtube:
                    youtube.actualizar_transmision(titulo, video['url'])
            
            threading.Thread(target=actualizar_youtube, daemon=True).start()
            
            # Ciclo de 8 horas con monitoreo activo
            while (time.time() - start_time) < 28800:
                if proceso.poll() is not None:
                    logging.warning("⚡ Reconectando FFmpeg...")
                    proceso = subprocess.Popen(cmd)
                time.sleep(15)
            
            proceso.terminate()
            logging.info("⏳ Ciclo completado. Esperando 10 minutos...")
            time.sleep(600)
            
        except Exception as e:
            logging.error(f"🚨 Error crítico: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
