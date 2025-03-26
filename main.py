import os
import re
import random
import subprocess
import logging
import time
import json
import requests
import tempfile
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

# Directorio temporal
TEMP_DIR = tempfile.gettempdir()

PALABRAS_CLAVE = {
    'lluvia': ['lluvia', 'rain', 'storm'],
    'fuego': ['fuego', 'fire', 'chimenea'],
    'bosque': ['bosque', 'jungla', 'forest'],
    'rio': ['rio', 'river', 'cascada'],
    'noche': ['noche', 'night', 'luna']
}

class DescargadorDrive:
    @staticmethod
    def descargar_archivo(url, destino):
        try:
            # Usar wget para manejar cookies y redirecciones
            comando = [
                "wget",
                "--no-check-certificate",
                "-O", destino,
                url
            ]
            result = subprocess.run(comando, capture_output=True, text=True)
            
            if result.returncode != 0:
                logging.error(f"Error descarga: {result.stderr}")
                return False
                
            return os.path.exists(destino)
            
        except Exception as e:
            logging.error(f"Error descargando {url}: {str(e)}")
            return False

class GestorContenido:
    def __init__(self):
        self.medios = self.cargar_medios()
    
    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=15)
            respuesta.raise_for_status()
            return respuesta.json()
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
    
    def generar_miniatura(self, video_path):
        try:
            output_path = os.path.join(TEMP_DIR, "miniatura.jpg")
            subprocess.run([
                "ffmpeg",
                "-y",
                "-ss", "00:00:05",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                output_path
            ], check=True)
            return output_path
        except Exception as e:
            logging.error(f"Error miniatura: {str(e)}")
            return None
    
    def actualizar_transmision(self, titulo, video_path):
        try:
            if not self.youtube:
                return

            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="active"
            ).execute()
            
            if not broadcasts.get('items'):
                logging.error("Crea una transmisión ACTIVA en YouTube Studio primero!")
                return
            
            broadcast_id = broadcasts['items'][0]['id']
            
            # Actualizar título
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
            
            # Actualizar miniatura
            thumbnail_path = self.generar_miniatura(video_path)
            if thumbnail_path:
                self.youtube.thumbnails().set(
                    videoId=broadcast_id,
                    media_body=thumbnail_path
                ).execute()
                os.remove(thumbnail_path)
            
            logging.info(f"Actualizado YouTube: {titulo}")
            
        except Exception as e:
            logging.error(f"Error YouTube API: {str(e)}")

def generar_titulo(nombre_video):
    nombre = nombre_video.lower()
    tema = next((t for t, keys in PALABRAS_CLAVE.items() if any(k in nombre for k in keys)), 'Naturaleza')
    ubicacion = next((p for p in ['Cabaña', 'Sala', 'Cueva', 'Montaña'] if p.lower() in nombre), 'Entorno')
    return f"{ubicacion} • Sonidos de {tema.capitalize()} 🌿 24/7"

def descargar_y_transmitir(video_url, audio_url):
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            # Descargar recursos
            video_path = os.path.join(tmp_dir, "video.mp4")
            audio_path = os.path.join(tmp_dir, "audio.mp3")
            
            logging.info("⬇️ Descargando video...")
            if not DescargadorDrive.descargar_archivo(video_url, video_path):
                return None
                
            logging.info("⬇️ Descargando audio...")
            if not DescargadorDrive.descargar_archivo(audio_url, audio_path):
                return None
                
            # Verificar archivos
            if not os.path.getsize(video_path) > 1024 or not os.path.getsize(audio_path) > 1024:
                logging.error("Archivos descargados inválidos")
                return None
                
            # Iniciar transmisión
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video_path,
                "-i", audio_path,
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
            return subprocess.Popen(cmd)
            
        except Exception as e:
            logging.error(f"Error en transmisión: {str(e)}")
            return None

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    fase = 0
    tiempo_inicio = datetime.now()
    
    while True:
        try:
            if (datetime.now() - tiempo_inicio).total_seconds() >= 28800:
                fase = (fase + 1) % 3
                tiempo_inicio = datetime.now()
                gestor.actualizar_medios()
                logging.info(f"🔄 Rotando fase: {['Música', 'Naturaleza', 'Combinado'][fase]}")
            
            # Selección de contenido
            if fase == 0:
                video = random.choice(gestor.medios['videos'])
                audio = random.choice(gestor.medios['musica'])
            elif fase == 1:
                video = random.choice(gestor.medios['videos'])
                audio = random.choice(gestor.medios['sonidos_naturaleza'])
            else:
                video = random.choice(gestor.medios['videos'])
                audio = random.choice(gestor.medios['musica'] + gestor.medios['sonidos_naturaleza'])
            
            titulo = generar_titulo(video['name'])
            
            logging.info(f"▶️ Iniciando transmisión:\nVideo: {video['name']}\nAudio: {audio['name']}")
            proceso = descargar_y_transmitir(video['url'], audio['url'])
            
            if not proceso:
                time.sleep(60)
                continue
                
            # Esperar inicialización
            time.sleep(30)
            
            # Actualizar YouTube
            if youtube.youtube:
                youtube.actualizar_transmision(titulo, os.path.join(TEMP_DIR, "video.mp4"))
            
            # Mantener transmisión
            proceso.wait()
            
        except Exception as e:
            logging.error(f"Error ciclo: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    import threading
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
