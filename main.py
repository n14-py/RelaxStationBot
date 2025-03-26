import os
import random
import subprocess
import logging
import time
import json
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import Flask
from waitress import serve

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
        self.media_cache_dir = "./media_cache"
        os.makedirs(self.media_cache_dir, exist_ok=True)
        self.medios = self.cargar_medios()
    
    def descargar_audio(self, url):
        try:
            nombre_archivo = hashlib.md5(url.encode()).hexdigest() + os.path.splitext(url)[1]
            ruta_local = os.path.join(self.media_cache_dir, nombre_archivo)
            
            if not os.path.exists(ruta_local):
                respuesta = requests.get(url, stream=True, timeout=30)
                respuesta.raise_for_status()
                with open(ruta_local, 'wb') as f:
                    for chunk in respuesta.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            return ruta_local
        except Exception as e:
            logging.error(f"Error descargando audio: {str(e)}")
            return url  # Fallback a URL directa
    
    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            if not all(key in datos for key in ["videos", "musica", "sonidos_naturaleza"]):
                raise ValueError("Estructura JSON inválida")
            
            # Descargar toda la música
            for medio in datos['musica'] + datos['sonidos_naturaleza']:
                medio['local_path'] = self.descargar_audio(medio['url'])
            
            logging.info("✅ Medios cargados y descargados")
            return datos
        except Exception as e:
            logging.error(f"Error cargando medios: {str(e)}")
            return {"videos": [], "musica": [], "sonidos_naturaleza": []}

    def actualizar_medios(self):
        self.medios = self.cargar_medios()

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
                "-y", "-ss", "00:00:01",
                "-i", video_url,
                "-vframes", "1",
                "-q:v", "2",
                output_path
            ], check=True)
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
                        "description": "Streaming 24/7 - Sonidos Naturales y Música Relajante",
                        "categoryId": "22"
                    }
                }
            ).execute()
            
            if thumbnail_path:
                self.youtube.thumbnails().set(
                    videoId=broadcast_id,
                    media_body=thumbnail_path
                ).execute()
                os.remove(thumbnail_path)
            
            logging.info(f"Actualizado YouTube: {titulo}")
        except Exception as e:
            logging.error(f"Error actualizando YouTube: {str(e)}")

def generar_titulo(nombre_video):
    nombre = nombre_video.lower()
    tema = next((t for t, keys in PALABRAS_CLAVE.items() if any(k in nombre for k in keys)), 'Naturaleza')
    ubicacion = next((p for p in ['Cabaña', 'Sala', 'Cueva', 'Montaña'] if p.lower() in nombre), 'Entorno')
    return f"{ubicacion} • Sonidos de {tema.capitalize()} 🌿 24/7"

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    while True:
        try:
            # Seleccionar fase cada 8 horas
            fase = random.choice([0, 1, 2])  # Aleatorizar fase inicial
            tiempo_inicio = datetime.now()
            gestor.actualizar_medios()
            
            # Configurar contenido según fase
            if fase == 0:
                audios = gestor.medios['musica']
            elif fase == 1:
                audios = gestor.medios['sonidos_naturaleza']
            else:
                audios = gestor.medios['musica'] + gestor.medios['sonidos_naturaleza']
            
            video = random.choice(gestor.medios['videos'])
            random.shuffle(audios)  # Mezclar audios inicialmente
            
            # Generar lista de reproducción aleatoria infinita
            playlist_path = "/tmp/playlist.txt"
            with open(playlist_path, 'w') as f:
                for audio in audios:
                    f.write(f"file '{audio.get('local_path', audio['url'])}'\n")
                f.write(f"file '{random.choice(audios).get('local_path', audio['url'])}'\n")  # Forzar bucle

            # Configurar FFmpeg para 8 horas
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-f", "concat",
                "-safe", "0",
                "-i", playlist_path,
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
                "-t", "28800",  # 8 horas exactas
                "-f", "flv",
                RTMP_URL
            ]
            
            logging.info(f"🎬 Iniciando ciclo de 8 horas\nVideo: {video['name']}\nAudios: {len(audios)} pistas mezcladas")
            
            # Ejecutar transmisión
            proceso = subprocess.Popen(cmd)
            proceso.wait()
            
            # Limpiar
            os.remove(playlist_path)
            
        except Exception as e:
            logging.error(f"Error en transmisión: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    import threading
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
