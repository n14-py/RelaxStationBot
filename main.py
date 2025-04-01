import os
import random
import subprocess
import logging
import time
import json
import requests
import hashlib
from datetime import datetime, timedelta
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
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('stream_manager.log')
    ]
)

# Configuración
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
    
    def obtener_extension_segura(self, url):
        try:
            parsed = urlparse(url)
            path = parsed.path
            extension = os.path.splitext(path)[1].lower()
            return extension if extension in ['.mp3', '.wav'] else '.mp3'
        except:
            return '.mp3'

    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            extension = self.obtener_extension_segura(url)
            nombre_archivo = f"{nombre_hash}.wav"
            ruta_local = os.path.join(self.media_cache_dir, nombre_archivo)
            
            if os.path.exists(ruta_local):
                try:
                    subprocess.run(["ffprobe", ruta_local], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return ruta_local
                except:
                    os.remove(ruta_local)
            
            temp_path = os.path.join(self.media_cache_dir, f"temp_{nombre_hash}{extension}")
            
            respuesta = requests.get(url, stream=True, timeout=30)
            respuesta.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in respuesta.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            subprocess.run([
                "ffmpeg",
                "-y",
                "-i", temp_path,
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                ruta_local
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            os.remove(temp_path)
            return ruta_local
        except Exception as e:
            logging.error(f"Error procesando {url}: {str(e)}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return None

    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            if not all(key in datos for key in ["videos", "musica", "sonidos_naturaleza"]):
                raise ValueError("Estructura JSON inválida")
            
            for medio in datos['sonidos_naturaleza']:
                local_path = self.descargar_audio(medio['url'])
                medio['local_path'] = local_path if local_path else None
            
            logging.info("✅ Medios verificados y listos")
            return datos
        except Exception as e:
            logging.error(f"Error cargando medios: {str(e)}")
            return {"videos": [], "musica": [], "sonidos_naturaleza": []}

class YouTubeManager:
    def __init__(self):
        self.youtube = self.autenticar()
        self.ultima_transmision = None
    
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
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path
        except Exception as e:
            logging.error(f"Error generando miniatura: {str(e)}")
            return None
    
    def crear_transmision(self, titulo):
        try:
            # Crear broadcast
            broadcast_body = {
                "snippet": {
                    "title": titulo,
                    "description": "Streaming 24/7 - Sonidos Naturales Relajantes",
                    "scheduledStartTime": datetime.utcnow().isoformat() + "Z",
                    "categoryId": "22"
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                },
                "contentDetails": {
                    "latencyPreference": "low",
                    "enableAutoStart": True,
                    "enableAutoStop": True
                }
            }
            broadcast = self.youtube.liveBroadcasts().insert(
                part="snippet,status,contentDetails",
                body=broadcast_body
            ).execute()
            
            # Crear stream
            stream_body = {
                "snippet": {
                    "title": "Stream 24/7 - " + titulo,
                    "description": "Stream continuo de sonidos naturales"
                },
                "cdn": {
                    "format": "1080p",
                    "ingestionType": "rtmp",
                    "resolution": "1080p",
                    "frameRate": "24fps"
                }
            }
            stream = self.youtube.liveStreams().insert(
                part="snippet,cdn",
                body=stream_body
            ).execute()
            
            # Vincular broadcast y stream
            self.youtube.liveBroadcasts().bind(
                part="id,contentDetails",
                id=broadcast['id'],
                streamId=stream['id']
            ).execute()
            
            ingestion_info = stream['cdn']['ingestionInfo']
            rtmp_url = f"{ingestion_info['ingestionAddress']}/{ingestion_info['streamName']}"
            
            self.ultima_transmision = {
                'broadcast_id': broadcast['id'],
                'stream_id': stream['id'],
                'rtmp_url': rtmp_url
            }
            
            logging.info(f"Nueva transmisión creada: {broadcast['id']}")
            return rtmp_url, broadcast['id']
        
        except Exception as e:
            logging.error(f"Error creando transmisión: {str(e)}")
            return None, None
    
    def subir_miniatura(self, broadcast_id, thumbnail_path):
        try:
            if os.path.exists(thumbnail_path):
                self.youtube.thumbnails().set(
                    videoId=broadcast_id,
                    media_body=thumbnail_path
                ).execute()
                os.remove(thumbnail_path)
                logging.info("Miniatura actualizada")
        except Exception as e:
            logging.error(f"Error subiendo miniatura: {str(e)}")
    
    def finalizar_transmision(self, broadcast_id):
        try:
            self.youtube.liveBroadcasts().transition(
                broadcastStatus="complete",
                id=broadcast_id,
                part="id,snippet,status"
            ).execute()
            logging.info(f"Transmisión {broadcast_id} finalizada")
        except Exception as e:
            logging.error(f"Error finalizando transmisión: {str(e)}")

def determinar_categoria(nombre_video):
    nombre = nombre_video.lower()
    for categoria, palabras in PALABRAS_CLAVE.items():
        if any(palabra in nombre for palabra in palabras):
            return categoria
    return random.choice(list(PALABRAS_CLAVE.keys()))

def generar_titulo(nombre_video, categoria):
    ubicaciones = ['Cabaña', 'Sala', 'Cueva', 'Montaña', 'Departamento', 'Cafetería']
    ubicacion = next((p for p in ubicaciones if p.lower() in nombre_video.lower()), 'Entorno')
    return f"{ubicacion} • Sonidos de {categoria.capitalize()} 🌿 24/7"

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    while True:
        try:
            # Seleccionar contenido primero para generar título
            video = random.choice(gestor.medios['videos'])
            categoria = determinar_categoria(video['name'])
            titulo = generar_titulo(video['name'], categoria)
            
            # Crear nueva transmisión en YouTube
            rtmp_url, broadcast_id = youtube.crear_transmision(titulo)
            if not rtmp_url:
                time.sleep(60)
                continue
            
            # Seleccionar audio
            palabras_clave = PALABRAS_CLAVE[categoria]
            audios = [a for a in gestor.medios['sonidos_naturaleza'] 
                     if a['local_path'] and any(p in a['name'].lower() for p in palabras_clave)]
            
            if not audios:
                audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                logging.warning("Usando todos los sonidos disponibles")
            
            audio = random.choice(audios)
            audio_path = audio['local_path']
            
            # Generar y subir miniatura
            thumbnail_path = youtube.generar_miniatura(video['url'])
            if thumbnail_path:
                youtube.subir_miniatura(broadcast_id, thumbnail_path)
            
            # Configuración FFmpeg 1080p
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-stream_loop", "-1",
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-b:v", "4500k",
                "-maxrate", "6000k",
                "-bufsize", "9000k",
                "-g", "48",
                "-r", "24",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-f", "flv",
                rtmp_url
            ]
            
            logging.info(f"""
            🎬 INICIANDO NUEVO CICLO 🎬
            📺 Video: {video['name']}
            🌿 Categoría: {categoria}
            🔊 Audio: {audio['name']}
            🏷️ Título: {titulo}
            📡 RTMP: {rtmp_url}
            ⚙️ Configuración: 1080p24 @ 4500kbps
            """)
            
            # Ejecutar transmisión por 8 horas
            start_time = time.time()
            proceso = subprocess.Popen(cmd)
            
            while (time.time() - start_time) < 28800:  # 8 horas
                if proceso.poll() is not None:
                    logging.error("FFmpeg se detuvo. Reiniciando...")
                    proceso = subprocess.Popen(cmd)
                time.sleep(30)
            
            proceso.terminate()
            try:
                proceso.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proceso.kill()
            
            # Finalizar transmisión en YouTube
            youtube.finalizar_transmision(broadcast_id)
            
            logging.info("⏳ Esperando 10 minutos antes del próximo ciclo...")
            time.sleep(600)  # 10 minutos
        
        except Exception as e:
            logging.error(f"Error crítico en ciclo: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
