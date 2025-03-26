import os
import random
import subprocess
import logging
import time
import json
import requests
import hashlib
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import Flask
from waitress import serve
from urllib.parse import urlparse, parse_qs

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
        os.makedirs(self.media_cache_dir, exist_ok=True, mode=0o777)
        self.medios = self.cargar_medios()
    
    def obtener_url_real(self, gdrive_url):
        try:
            file_id = parse_qs(urlparse(gdrive_url).query.get('id', [''])[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        except:
            return gdrive_url
    
    def verificar_formato_ffprobe(self, url):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name', '-of', 'default=nokey=1:noprint_wrappers=1', url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            ruta_local = os.path.join(self.media_cache_dir, f"{nombre_hash}.mp3")
            
            if os.path.exists(ruta_local):
                return ruta_local
                
            respuesta = requests.get(url, stream=True, timeout=30)
            respuesta.raise_for_status()
            
            with open(ruta_local, 'wb') as f:
                for chunk in respuesta.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return ruta_local
        except Exception as e:
            logging.error(f"Error descargando {url}: {str(e)}")
            return None

    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            for categoria in ['videos', 'musica', 'sonidos_naturaleza']:
                for medio in datos[categoria]:
                    url_real = self.obtener_url_real(medio['url'])
                    
                    if categoria == 'videos':
                        if self.verificar_formato_ffprobe(url_real):
                            medio['local_path'] = url_real
                        else:
                            medio['local_path'] = None
                            logging.warning(f"Video no válido: {medio['name']}")
                    else:
                        medio['local_path'] = self.descargar_audio(url_real)
            
            return datos
        except Exception as e:
            logging.error(f"Error cargando medios: {str(e)}")
            return {"videos": [], "musica": [], "sonidos_naturaleza": []}

class YouTubeManager:
    def __init__(self):
        self.youtube = self.autenticar()
        self.miniatura_default = "/app/fallback.jpg"
    
    def autenticar(self):
        try:
            creds = Credentials(
                token=None,
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
    
    def verificar_transmision(self):
        try:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="active"
            ).execute()
            return broadcasts.get('items', [])
        except Exception as e:
            logging.error(f"Error verificando transmisión: {str(e)}")
            return []
    
    def generar_miniatura(self, video_url):
        try:
            output_path = "/tmp/miniatura.jpg"
            subprocess.run([
                "ffmpeg",
                "-y", "-ss", "00:00:03",
                "-i", video_url,
                "-vframes", "1",
                "-q:v", "2",
                output_path
            ], check=True, timeout=15)
            return output_path
        except:
            return self.miniatura_default
    
    def actualizar_transmision(self, titulo, video_url):
        try:
            broadcasts = self.verificar_transmision()
            if not broadcasts:
                logging.error("Crea una transmisión ACTIVA en YouTube Studio primero!")
                return
                
            broadcast_id = broadcasts[0]['id']
            thumbnail_path = self.generar_miniatura(video_url)
            
            self.youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_id,
                    "snippet": {
                        "title": titulo,
                        "description": "Streaming 24/7 - Sonidos Naturales y Música Relajante",
                        "categoryId": "22"
                    }
                }
            ).execute()
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                self.youtube.thumbnails().set(
                    videoId=broadcast_id,
                    media_body=thumbnail_path
                ).execute()
            
            logging.info(f"Título actualizado: {titulo}")
        except Exception as e:
            logging.error(f"Error actualizando YouTube: {str(e)}")

def generar_titulo(nombre_video, fase):
    nombre = nombre_video.lower()
    ubicaciones = ['cabaña', 'sala', 'cueva', 'montaña', 'departamento', 'cafetería']
    ubicacion = next((p for p in ubicaciones if p in nombre), 'Entorno').capitalize()
    
    if fase == 0:
        return f"{ubicacion} • Música Relajante 🌿 24/7"
    elif fase == 1:
        tema = next((t for t, keys in PALABRAS_CLAVE.items() if any(k in nombre for k in keys)), 'Naturaleza')
        return f"{ubicacion} • Sonidos de {tema.capitalize()} 🌿 24/7"
    else:
        tema = next((t for t, keys in PALABRAS_CLAVE.items() if any(k in nombre for k in keys)), 'Naturaleza')
        return f"{ubicacion} • Música y Sonidos de {tema.capitalize()} 🌿 24/7"

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    while True:
        try:
            if not youtube.verificar_transmision():
                logging.error("Configura primero una transmisión ACTIVA en YouTube Studio!")
                time.sleep(300)
                continue
                
            fase = random.choice([0, 1, 2])
            videos_validos = [v for v in gestor.medios['videos'] if v['local_path']]
            if not videos_validos:
                logging.error("No hay videos válidos disponibles")
                time.sleep(60)
                continue
                
            video = random.choice(videos_validos)
            logging.info(f"🎥 Video seleccionado: {video['name']}")
            
            if fase == 0:
                audios = [a for a in gestor.medios['musica'] if a['local_path']]
            elif fase == 1:
                audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
            else:
                audios = [a for a in gestor.medios['musica'] + gestor.medios['sonidos_naturaleza'] if a['local_path']]
            
            if not audios:
                logging.error("No hay audios disponibles")
                time.sleep(60)
                continue
                
            titulo = generar_titulo(video['name'], fase)
            logging.info(f"🏷️ Título generado: {titulo}")
            
            playlist_path = "/tmp/playlist.txt"
            with open(playlist_path, 'w') as f:
                for audio in audios:
                    f.write(f"file '{audio['local_path']}'\n")
            
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['local_path'],
                "-f", "concat",
                "-safe", "0",
                "-i", playlist_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "160k",
                "-ar", "48000",
                "-t", "28800",
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info("🚀 Iniciando transmisión...")
            proceso = subprocess.Popen(cmd)
            time.sleep(30)
            
            if proceso.poll() is None:
                logging.info("🔴 Stream activo")
                youtube.actualizar_transmision(titulo, video['local_path'])
                proceso.wait()
            
            if os.path.exists(playlist_path):
                os.remove(playlist_path)
            
            logging.info("⏹️ Transmisión finalizada\n")
            
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    import threading
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
