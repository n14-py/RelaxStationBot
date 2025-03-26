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
                parsed = urlparse(url)
                file_id = parse_qs(parsed.query).get('id', [''])[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            return url
        except:
            return url
    
    def descargar_archivo(self, url):
    try:
        # Obtener ID real de Google Drive
        if 'drive.google.com' in url:
            file_id = url.split('id=')[-1].split('&')[0]
            url = f"https://drive.google.com/uc?export=download&id={file_id}"

        session = requests.Session()
        response = session.get(url, stream=True, timeout=30)
        
        # Manejar confirmación de descarga grande
        if 'drive.google.com' in url and 'confirm=' not in url:
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    confirm_url = f"{url}&confirm={value}"
                    response = session.get(confirm_url, stream=True, timeout=30)
                    break
        
        # Determinar extensión real
        content_disposition = response.headers.get('Content-Disposition', '')
        filename = re.findall('filename="(.+)"', content_disposition)
        extension = os.path.splitext(filename[0])[1] if filename else '.mp4'
        
        nombre_hash = hashlib.md5(url.encode()).hexdigest()
        ruta_local = os.path.join(self.media_cache_dir, f"{nombre_hash}{extension}")
        
        # Descargar archivo completo
        with open(ruta_local, 'wb') as f:
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    f.write(chunk)
            
            if total_size < 5 * 1024 * 1024:  # Mínimo 5MB
                raise ValueError("Archivo demasiado pequeño")
        
        return ruta_local
    except Exception as e:
        logging.error(f"Error descarga {url}: {str(e)}")
        return None
    
    def determinar_extension(self, content_type, url):
        extensiones = {
            'video/mp4': '.mp4',
            'video/quicktime': '.mov',
            'audio/mpeg': '.mp3',
            'video/x-matroska': '.mkv'
        }
        
        # Primero por content-type
        for ct, ext in extensiones.items():
            if ct in content_type:
                return ext
        
        # Luego por extensión en URL
        parsed_url = urlparse(url)
        path_ext = os.path.splitext(parsed_url.path)[1]
        if path_ext in ['.mp4', '.mov', '.mp3', '.mkv']:
            return path_ext
        
        # Default
        return '.mp4' if 'video' in content_type else '.mp3'
    
    def verificar_archivo(self, ruta):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', ruta],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                text=True
            )
            if result.returncode != 0:
                logging.error(f"Error ffprobe: {result.stderr.strip()}")
                return False
            return True
        except Exception as e:
            logging.error(f"Error verificación {ruta}: {str(e)}")
            return False
    
    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=15)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            for categoria in ['videos', 'musica', 'sonidos_naturaleza']:
                for medio in datos[categoria]:
                    medio['local_path'] = self.descargar_archivo(medio['url'])
                    if medio['local_path'] and not self.verificar_archivo(medio['local_path']):
                        logging.warning(f"Archivo inválido: {medio['name']}")
                        medio['local_path'] = None
            
            # Filtrar medios inválidos
            datos['videos'] = [v for v in datos['videos'] if v['local_path']]
            datos['musica'] = [m for m in datos['musica'] if m['local_path']]
            datos['sonidos_naturaleza'] = [s for s in datos['sonidos_naturaleza'] if s['local_path']]
            
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
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="active",
                maxResults=1
            ).execute()
            
            if not broadcasts.get('items'):
                logging.error("Crea una transmisión ACTIVA en YouTube Studio primero!")
                return False
            
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
        except Exception as e:
            logging.error(f"Error actualizando YouTube: {str(e)}")
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
            videos_validos = gestor.medios['videos']
            
            if not videos_validos:
                logging.error("No hay videos válidos disponibles")
                time.sleep(60)
                continue
            
            video = random.choice(videos_validos)
            logging.info(f"🎥 Video seleccionado: {video['name']}")
            
            # Selección de audios según fase
            if fase == 0:
                audios = gestor.medios['musica']
            elif fase == 1:
                audios = gestor.medios['sonidos_naturaleza']
            else:
                audios = gestor.medios['musica'] + gestor.medios['sonidos_naturaleza']
            
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
