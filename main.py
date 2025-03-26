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
from urllib.parse import urlparse

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
            session = requests.Session()
            response = session.get(gdrive_url, allow_redirects=True, stream=True, timeout=10)
            if response.status_code == 200:
                return response.url
            return None
        except Exception as e:
            logging.error(f"Error resolviendo URL: {str(e)}")
            return None
    
    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            extension = '.mp3'
            nombre_archivo = f"{nombre_hash}{extension}"
            ruta_local = os.path.join(self.media_cache_dir, nombre_archivo)
            
            if os.path.exists(ruta_local) and os.path.getsize(ruta_local) > 1024:
                return ruta_local
                
            real_url = self.obtener_url_real(url)
            if not real_url:
                return None
                
            respuesta = requests.get(real_url, stream=True, timeout=30)
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
            
            valid_extensions = {
                'videos': ['.mp4', '.mov', '.mkv'],
                'musica': ['.mp3', '.wav'],
                'sonidos_naturaleza': ['.mp3', '.wav']
            }
            
            for categoria in ['videos', 'musica', 'sonidos_naturaleza']:
                datos[categoria] = [m for m in datos[categoria] 
                for medio in datos[categoria]:
                    ext = os.path.splitext(medio['url'])[1].lower()
                    if ext not in valid_extensions[categoria]:
                        logging.warning(f"Formato no soportado en {medio['name']}: {ext}")
                        medio['local_path'] = None
                    else:
                        if categoria == 'videos':
                            medio['local_path'] = self.obtener_url_real(medio['url'])
                        else:
                            medio['local_path'] = self.descargar_audio(medio['url'])
            
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
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", 
                "default=noprint_wrappers=1:nokey=1", video_url],
                capture_output=True,
                text=True,
                timeout=10
            )
            if probe.returncode != 0:
                raise ValueError("Video no accesible")
            
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
            logging.warning("Usando miniatura por defecto")
            return self.miniatura_default
    
    def actualizar_transmision(self, titulo, video_url):
        try:
            broadcasts = self.verificar_transmision()
            if not broadcasts:
                logging.error("No hay transmisión activa en YouTube")
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
                if thumbnail_path != self.miniatura_default:
                    os.remove(thumbnail_path)
            
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
                logging.error("NO HAY TRANSMISIÓN ACTIVA EN YOUTUBE")
                time.sleep(300)
                continue
                
            fase = random.choice([0, 1, 2])
            video = random.choice([v for v in gestor.medios['videos'] if v['local_path']])
            logging.info(f"🎥 Video seleccionado: {video['name']}")
            logging.info(f"🔧 Fase: {['Música', 'Naturaleza', 'Combinado'][fase]}")
            
            if fase == 0:
                audios = [a for a in gestor.medios['musica'] if a['local_path']]
            elif fase == 1:
                audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
            else:
                naturaleza = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                musica = [a for a in gestor.medios['musica'] if a['local_path']]
                audios = (random.choice(naturaleza), musica
            
            if not audios:
                logging.error("No hay audios disponibles")
                time.sleep(60)
                continue
                
            titulo = generar_titulo(video['name'], fase)
            logging.info(f"🏷️ Título: {titulo}")
            
            # Generar comando FFmpeg
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['local_path'],
                "-f", "concat",
                "-safe", "0",
                "-protocol_whitelist", "file,http,https,tcp,tls",
                "-stream_loop", "-1",
                "-i", "audio_input.txt",
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
                "-t", "28800",  # 8 horas
                "-f", "flv",
                RTMP_URL
            ]
            
            # Manejo especial para fase combinada
            if fase == 2:
                with open("naturaleza.txt", "w") as f:
                    f.write(f"file '{audios[0]['local_path']}'\n")
                with open("musica.txt", "w") as f:
                    for track in audios[1]:
                        f.write(f"file '{track['local_path']}'\n")
                
                cmd = [
                    "ffmpeg",
                    "-loglevel", "error",
                    "-re",
                    "-stream_loop", "-1",
                    "-i", video['local_path'],
                    "-f", "concat",
                    "-safe", "0",
                    "-stream_loop", "-1",
                    "-i", "naturaleza.txt",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", "musica.txt",
                    "-filter_complex",
                    "[1:a][2:a]amix=inputs=2:duration=longest[a]",
                    "-map", "0:v:0",
                    "-map", "[a]",
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
                    "-t", "28800",
                    "-f", "flv",
                    RTMP_URL
                ]
            
            logging.info("🚀 Iniciando transmisión...")
            proceso = subprocess.Popen(cmd)
            time.sleep(30)  # Esperar conexión
            
            if proceso.poll() is None:
                logging.info("🔴 Stream activo")
                youtube.actualizar_transmision(titulo, video['local_path'])
                proceso.wait()
            else:
                logging.error("❌ El stream falló al iniciar")
            
            # Limpieza
            for f in ["audio_input.txt", "naturaleza.txt", "musica.txt"]:
                if os.path.exists(f):
                    os.remove(f)
            
            logging.info("⏹️ Transmisión finalizada\n")
            
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
