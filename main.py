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
            nombre_archivo = f"{nombre_hash}.wav"  # Convertimos todo a WAV
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
            
            # Conversión a WAV para compatibilidad
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
    
    def actualizar_transmision(self, titulo, video_url):
        try:
            thumbnail_path = self.generar_miniatura(video_url)
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="active"
            ).execute()
            
            if not broadcasts.get('items'):
                logging.error("¡Crea una transmisión ACTIVA en YouTube Studio primero!")
                return
            
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
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                self.youtube.thumbnails().set(
                    videoId=broadcast_id,
                    media_body=thumbnail_path
                ).execute()
                os.remove(thumbnail_path)
            
            logging.info(f"Actualizado YouTube: {titulo}")
        except Exception as e:
            logging.error(f"Error actualizando YouTube: {str(e)}")

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
            video = random.choice(gestor.medios['videos'])
            categoria = determinar_categoria(video['name'])
            
            palabras_clave = PALABRAS_CLAVE[categoria]
            audios = [a for a in gestor.medios['sonidos_naturaleza'] 
                     if a['local_path'] and any(p in a['name'].lower() for p in palabras_clave)]
            
            if not audios:
                audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                logging.warning("Usando todos los sonidos disponibles")
            
            random.shuffle(audios)
            
            playlist_path = "/tmp/playlist.txt"
            with open(playlist_path, 'w') as f:
                for audio in audios:
                    f.write(f"file '{os.path.abspath(audio['local_path'])}'\n")
            
            titulo = generar_titulo(video['name'], categoria)
            
            # Configuración optimizada 720p
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-f", "concat",
                "-safe", "0",
                "-protocol_whitelist", "file,http,https,tcp,tls",
                "-stream_loop", "-1",
                "-i", playlist_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", "scale=1280:720",  # Resolución 720p
                "-c:v", "libx264",
                "-preset", "veryfast",    # Balance entre CPU y calidad
                "-b:v", "1500k",          # Bitrate video
                "-maxrate", "2000k",
                "-bufsize", "3000k",
                "-g", "60",
                "-r", "30",
                "-c:a", "aac",
                "-b:a", "128k",           # Bitrate audio
                "-ar", "44100",
                "-ac", "2",
                "-t", "28800",
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info(f"""
            🎬 INICIANDO TRANSMISIÓN 🎬
            📺 Video: {video['name']}
            🌿 Categoría: {categoria}
            🎶 Audios seleccionados: {len(audios)} pistas
            🏷️ Título programado: {titulo}
            ⚙️ Configuración: 720p @ 1500kbps
            ⏳ Duración: 8 horas
            """)
            
            proceso = subprocess.Popen(cmd)
            
            def actualizar_youtube():
                time.sleep(300)  # 5 minutos
                if youtube.youtube:
                    youtube.actualizar_transmision(titulo, video['url'])
            
            threading.Thread(target=actualizar_youtube, daemon=True).start()
            
            proceso.wait()
            
            if os.path.exists(playlist_path):
                os.remove(playlist_path)
            
        except Exception as e:
            logging.error(f"Error en transmisión: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
