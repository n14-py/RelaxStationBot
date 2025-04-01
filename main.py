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
            # Corrección para Google Drive
            if "drive.google.com" in url:
                file_id = url.split('id=')[-1].split('&')[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
            
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            ruta_local = os.path.join(self.media_cache_dir, f"{nombre_hash}.wav")
            
            if os.path.exists(ruta_local):
                return ruta_local
                
            temp_path = os.path.join(self.media_cache_dir, f"temp_{nombre_hash}.mp3")
            
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # Filtra keep-alive chunks
                        open(temp_path, 'ab').write(chunk)
            
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_path,
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                ruta_local
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            os.remove(temp_path)
            return ruta_local
        except Exception as e:
            logging.error(f"Error procesando audio: {str(e)}")
            return None

    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=20)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            if not all(key in datos for key in ["videos", "musica", "sonidos_naturaleza"]):
                raise ValueError("Estructura JSON inválida")
            
            for medio in datos['sonidos_naturaleza']:
                medio['local_path'] = self.descargar_audio(medio['url'])
            
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
    
    def generar_miniatura(self, video_url):
        try:
            output_path = "/tmp/miniatura_actualizada.jpg"
            subprocess.run([
                "ffmpeg",
                "-y", "-ss", "00:01:00",
                "-i", video_url,
                "-vframes", "1",
                "-q:v", "2",
                "-vf", "format=yuvj420p",  # Formato compatible
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
                logging.error("¡Primero crea una transmisión ACTIVA en YouTube Studio!")
                return False
            
            broadcast_id = broadcasts['items'][0]['id']
            
            # Actualizar título
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
            
            # Actualizar miniatura
            if thumbnail_path and os.path.exists(thumbnail_path):
                self.youtube.thumbnails().set(
                    videoId=broadcast_id,
                    media_body=thumbnail_path
                ).execute()
                os.remove(thumbnail_path)
            
            return True
        except Exception as e:
            logging.error(f"Error en actualización: {str(e)}")
            return False

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
            # Selección de contenido
            video = random.choice(gestor.medios['videos'])
            categoria = determinar_categoria(video['name'])
            audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
            audio = random.choice(audios)
            titulo = generar_titulo(video['name'], categoria)
            
            logging.info(f"""
            🚀 TRANSMISIÓN INICIADA 🚀
            📍 Ubicación: {video.get('name', 'Desconocido')}
            🌳 Categoría: {categoria}
            🔊 Sonido: {audio.get('name', 'Desconocido')}
            🏷️ Título: {titulo}
            ⏱ Actualización a los 15 minutos
            """)
            
            # Configuración FFmpeg Estable
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-rtbufsize", "100M",  # Buffer grande
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-stream_loop", "-1",
                "-i", audio['local_path'],
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,setsar=1",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-x264-params", "keyint=48:min-keyint=48",
                "-b:v", "3000k",
                "-maxrate", "3000k",
                "-bufsize", "6000k",
                "-r", "24",
                "-g", "48",
                "-threads", "1",
                "-flush_packets", "1",  # Envío constante
                "-c:a", "aac",
                "-b:a", "96k",
                "-ar", "44100",
                "-f", "flv",
                RTMP_URL
            ]
            
            # Iniciar transmisión
            proceso = None
            start_time = time.time()
            actualizacion_realizada = [False]  # Estado mutable
            
            def actualizar_youtube():
                time.sleep(900)  # 15 minutos = 900 segundos
                if not actualizacion_realizada[0]:
                    logging.info("⏳ Intentando actualizar título y miniatura...")
                    if youtube.actualizar_transmision(titulo, video['url']):
                        logging.info("✅ ¡Actualización exitosa! (Título y miniatura)")
                        actualizacion_realizada[0] = True
                    else:
                        logging.warning("⚠️ Falló actualización, reintentando en 2 minutos...")
                        time.sleep(120)
                        if youtube.actualizar_transmision(titulo, video['url']):
                            logging.info("✅ ¡Actualización recuperada!")
                            actualizacion_realizada[0] = True
            
            threading.Thread(target=actualizar_youtube, daemon=True).start()
            
            # Ciclo de 8 horas con reconexión segura
            while (time.time() - start_time) < 28800:
                if proceso is None or proceso.poll() is not None:
                    if proceso:
                        proceso.kill()  # Terminar proceso anterior
                    logging.info("🔄 Iniciando/Reiniciando FFmpeg...")
                    proceso = subprocess.Popen(cmd)
                time.sleep(15)
            
            # Finalizar ciclo
            proceso.kill()
            logging.info("🛑 Ciclo completado. Esperando 10 minutos...")
            time.sleep(600)
            
        except Exception as e:
            logging.error(f"🔥 Error crítico: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    logging.info("🎬 Iniciando servicio de streaming...")
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
