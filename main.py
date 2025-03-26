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
    
    def obtener_url_real(self, url):
        try:
            if 'drive.google.com' in url:
                query = parse_qs(urlparse(url).query)
                file_id = query.get('id', [None])[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            return url
        except:
            return url
    
    def descargar_archivo(self, url):
        try:
            url_real = self.obtener_url_real(url)
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            ruta_local = os.path.join(self.media_cache_dir, nombre_hash)
            
            if os.path.exists(ruta_local) and os.path.getsize(ruta_local) > 1024:
                return ruta_local
                
            session = requests.Session()
            response = session.get(url_real, stream=True, timeout=30)
            response.raise_for_status()
            
            # Obtener extensión del Content-Type
            content_type = response.headers.get('Content-Type', '')
            if 'video' in content_type:
                extension = '.mp4'
            elif 'audio' in content_type:
                extension = '.mp3'
            else:
                extension = '.bin'
            
            ruta_local += extension
            
            with open(ruta_local, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if os.path.getsize(ruta_local) < 1024:
                raise ValueError("Archivo demasiado pequeño")
            
            return ruta_local
        except Exception as e:
            logging.error(f"Error descargando {url}: {str(e)}")
            return None
    
    def verificar_archivo(self, ruta):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', ruta],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            for categoria in ['videos', 'musica', 'sonidos_naturaleza']:
                for medio in datos[categoria]:
                    local_path = self.descargar_archivo(medio['url'])
                    if local_path and self.verificar_archivo(local_path):
                        medio['local_path'] = local_path
                    else:
                        medio['local_path'] = None
                        logging.warning(f"Archivo inválido: {medio['name']}")
            
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
    
    def actualizar_transmision(self, titulo):
        try:
            for _ in range(3):  # 3 intentos
                broadcasts = self.youtube.liveBroadcasts().list(
                    part="id,snippet",
                    broadcastStatus="active"
                ).execute()
                
                if broadcasts.get('items'):
                    broadcast_id = broadcasts['items'][0]['id']
                    
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
                    logging.info(f"Título actualizado: {titulo}")
                    return True
                
                time.sleep(5)
            
            logging.error("No se encontró transmisión activa")
            return False
        except Exception as e:
            logging.error(f"Error YouTube API: {str(e)}")
            return False

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
            # Selección de contenido
            fase = random.choice([0, 1, 2])
            videos_validos = [v for v in gestor.medios['videos'] if v['local_path']]
            if not videos_validos:
                logging.error("No hay videos válidos")
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
                logging.error("No hay audios válidos")
                time.sleep(60)
                continue
            
            # Generar playlist
            playlist_path = "/tmp/playlist.txt"
            with open(playlist_path, 'w') as f:
                for audio in audios:
                    f.write(f"file '{audio['local_path']}'\n")
            
            # Generar título
            titulo = generar_titulo(video['name'], fase)
            
            # Comando FFmpeg optimizado
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-protocol_whitelist", "file,http,https,tcp,tls",
                "-i", video['local_path'],
                "-f", "concat",
                "-safe", "0",
                "-protocol_whitelist", "file,http,https,tcp,tls",
                "-i", playlist_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "160k",
                "-ar", "48000",
                "-t", "28800",  # 8 horas
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info("🚀 Iniciando transmisión...")
            proceso = subprocess.Popen(cmd)
            
            # Esperar inicialización
            time.sleep(30)
            if proceso.poll() is None:
                logging.info("🔴 Stream activo")
                youtube.actualizar_transmision(titulo)
                proceso.wait()
            else:
                logging.error("❌ Fallo al iniciar stream")
            
            # Limpieza
            if os.path.exists(playlist_path):
                os.remove(playlist_path)
            
            logging.info("⏹️ Ciclo completado\n")
            
        except Exception as e:
            logging.error(f"Error crítico: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    import threading
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
