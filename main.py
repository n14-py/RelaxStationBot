import os
import random
import subprocess
import logging
import time
import requests
import hashlib
import re
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
    handlers=[logging.StreamHandler()]
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

# Helper para limpiar /tmp
def limpiar_tmp():
    try:
        tmp_dir = '/tmp'
        for filename in os.listdir(tmp_dir):
            if filename.startswith('miniatura'):
                file_path = os.path.join(tmp_dir, filename)
                os.remove(file_path)
        logging.info("🧹 /tmp limpiado")
    except Exception as e:
        logging.error(f"Error limpiando /tmp: {str(e)}")

class GestorContenido:
    def __init__(self):
        self.media_cache_dir = os.path.abspath("./media_cache")
        os.makedirs(self.media_cache_dir, exist_ok=True)
        self.medios = self.cargar_medios()
    
    def limpiar_cache(self):
        try:
            for filename in os.listdir(self.media_cache_dir):
                file_path = os.path.join(self.media_cache_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logging.error(f"Error eliminando {file_path}: {e}")
            logging.info("✅ Cache de medios limpiado")
        except Exception as e:
            logging.error(f"Error limpiando cache: {e}")
    
    def descargar_video_temp(self, url):
        try:
            session = requests.Session()
            if "drive.google.com" in url:
                file_id = re.search(r'/d/([a-zA-Z0-9_-]+)', url).group(1) or url.split('id=')[-1].split('&')[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            temp_path = os.path.join(self.media_cache_dir, f"temp_video_{nombre_hash}.mp4")
            
            response = session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192*4):
                    if chunk:
                        f.write(chunk)
            return temp_path
        except Exception as e:
            logging.error(f"Error descargando video: {str(e)}")
            return None

    def descargar_audio(self, url):
        try:
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
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
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
            gestor = GestorContenido()
            video_path = gestor.descargar_video_temp(video_url)
            
            if not video_path or not os.path.exists(video_path):
                raise Exception("Video no descargado")
            
            output_path = "/tmp/miniatura_nueva.jpg"
            subprocess.run([
                "ffmpeg", "-y", "-ss", "00:00:10",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-vf", "scale=1280:720,setsar=1",
                output_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(video_path):
                os.remove(video_path)
            
            return output_path
        except Exception as e:
            logging.error(f"Error miniatura: {str(e)}")
            return None

    def crear_transmision(self, titulo, video_url):
        try:
            scheduled_start = datetime.utcnow() + timedelta(minutes=5)
            
            broadcast = self.youtube.liveBroadcasts().insert(
                part="snippet,status",
                body={
                  "snippet": {
                  "title": titulo,
                  "description": "Déjate llevar por la serenidad...",
                  "scheduledStartTime": scheduled_start.isoformat() + "Z"
                     },
                    "status": {
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": False,
                        "enableAutoStart": True,
                        "enableAutoStop": True,
                        "enableArchive": True,
                        "lifeCycleStatus": "created"
                    }
                }
            ).execute()
            
            stream = self.youtube.liveStreams().insert(
                part="snippet,cdn",
                body={
                    "snippet": {
                        "title": "Stream de ingesta principal"
                    },
                    "cdn": {
                        "format": "1080p",
                        "ingestionType": "rtmp",
                        "resolution": "1080p",
                        "frameRate": "30fps"
                    }
                }
            ).execute()
            
            self.youtube.liveBroadcasts().bind(
                part="id,contentDetails",
                id=broadcast['id'],
                streamId=stream['id']
            ).execute()
            
            rtmp_url = stream['cdn']['ingestionInfo']['ingestionAddress']
            stream_name = stream['cdn']['ingestionInfo']['streamName']
            
            thumbnail_path = self.generar_miniatura(video_url)
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    self.youtube.thumbnails().set(
                        videoId=broadcast['id'],
                        media_body=thumbnail_path
                    ).execute()
                finally:
                    os.remove(thumbnail_path)
            
            return {
                "rtmp": f"{rtmp_url}/{stream_name}",
                "scheduled_start": scheduled_start,
                "broadcast_id": broadcast['id'],
                "stream_id": stream['id']
            }
        except Exception as e:
            logging.error(f"Error creando transmisión: {str(e)}")
            return None
    
    def obtener_estado_stream(self, stream_id):
        try:
            response = self.youtube.liveStreams().list(
                part="status",
                id=stream_id
            ).execute()
            return response['items'][0]['status']['streamStatus'] if response.get('items') else None
        except Exception as e:
            logging.error(f"Error obteniendo estado del stream: {str(e)}")
            return None
    
    def transicionar_estado(self, broadcast_id, estado):
        try:
            self.youtube.liveBroadcasts().transition(
                broadcastStatus=estado,
                id=broadcast_id,
                part="id,status"
            ).execute()
            return True
        except Exception as e:
            logging.error(f"Error transicionando a {estado}: {str(e)}")
            return False

    def finalizar_transmision(self, broadcast_id):
        try:
            self.youtube.liveBroadcasts().transition(
                broadcastStatus="complete",
                id=broadcast_id,
                part="id,status"
            ).execute()
            return True
        except Exception as e:
            logging.error(f"Error finalizando transmisión: {str(e)}")
            return False

# Funciones de lógica principal
def determinar_categoria(nombre_video):
    nombre = nombre_video.lower()
    contador = {categoria: 0 for categoria in PALABRAS_CLAVE}
    for palabra in nombre.split():
        for categoria, palabras in PALABRAS_CLAVE.items():
            if palabra in palabras:
                contador[categoria] += 1
    return max(contador, key=contador.get) if max(contador.values()) > 0 else random.choice(list(PALABRAS_CLAVE.keys()))

def seleccionar_audio_compatible(gestor, categoria_video):
    audios_compatibles = [
        audio for audio in gestor.medios['sonidos_naturaleza']
        if audio['local_path'] and 
        any(palabra in audio['name'].lower() 
        for palabra in PALABRAS_CLAVE[categoria_video])
    ]
    return random.choice(audios_compatibles) if audios_compatibles else None

def generar_titulo(nombre_video, categoria):
    ubicaciones = {
        'departamento': ['Departamento Acogedor', 'Loft Moderno'],
        'cabaña': ['Cabaña en el Bosque', 'Refugio Montañoso'],
        'default': ['Entorno Relajante', 'Espacio Zen']
    }
    ubicacion = random.choice(ubicaciones.get('default', ubicaciones['default']))
    actividad, emoji_act = random.choice([
        ('Dormir', '🌙'), ('Estudiar', '📚'), 
        ('Meditar', '🧘♂️'), ('Trabajar', '💻')
    ])
    beneficio = random.choice(['Aliviar el Insomnio', 'Reducir la Ansiedad'])
    return f"{ubicacion} • Sonidos de {categoria.capitalize()} para {actividad} {emoji_act} | {beneficio}"

def manejar_transmision(stream_data, youtube, gestor):
    try:
        proceso = None
        try:
            tiempo_inicio_ffmpeg = stream_data['start_time'] - timedelta(minutes=1)
            espera_ffmpeg = (tiempo_inicio_ffmpeg - datetime.utcnow()).total_seconds()
            if espera_ffmpeg > 0:
                time.sleep(espera_ffmpeg)
            
            cmd = [
                "ffmpeg", "-loglevel", "error", "-rtbufsize", "100M", "-re",
                "-stream_loop", "-1", "-i", stream_data['video']['url'],
                "-stream_loop", "-1", "-i", stream_data['audio']['local_path'],
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,setsar=1",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-x264-params", "keyint=48:min-keyint=48", "-b:v", "3000k",
                "-maxrate", "3000k", "-bufsize", "6000k", "-r", "24", "-g", "48",
                "-threads", "1", "-flush_packets", "1", "-c:a", "aac", "-b:a", "96k",
                "-ar", "44100", "-f", "flv", stream_data['rtmp']
            ]
            
            proceso = subprocess.Popen(cmd)
            logging.info("🟢 FFmpeg iniciado")
            
            max_checks = 10
            for _ in range(max_checks):
                estado = youtube.obtener_estado_stream(stream_data['stream_id'])
                if estado == 'active':
                    youtube.transicionar_estado(stream_data['broadcast_id'], 'testing')
                    break
                time.sleep(5)
            
            tiempo_restante = (stream_data['start_time'] - datetime.utcnow()).total_seconds()
            if tiempo_restante > 0:
                time.sleep(tiempo_restante)
            
            youtube.transicionar_estado(stream_data['broadcast_id'], 'live')
            logging.info("🎥 Transmisión LIVE")
            
            tiempo_inicio = datetime.utcnow()
            while (datetime.utcnow() - tiempo_inicio) < timedelta(hours=8):
                if proceso.poll() is not None:
                    proceso = subprocess.Popen(cmd)
                time.sleep(15)
            
        finally:
            if proceso:
                proceso.kill()
            youtube.finalizar_transmision(stream_data['broadcast_id'])
            logging.info("🛑 Transmisión finalizada")
            
    except Exception as e:
        logging.error(f"Error en transmisión: {str(e)}")
    finally:
        gestor.limpiar_cache()
        limpiar_tmp()

def ciclo_transmision():
    while True:
        gestor = GestorContenido()
        youtube = YouTubeManager()
        try:
            logging.info("🔄 Preparando nueva transmisión...")
            
            video = random.choice(gestor.medios['videos'])
            categoria = determinar_categoria(video['name'])
            audio = seleccionar_audio_compatible(gestor, categoria)
            
            if not audio:
                raise Exception("No se encontró audio compatible")
            
            titulo = generar_titulo(video['name'], categoria)
            stream_info = youtube.crear_transmision(titulo, video['url'])
            
            if not stream_info:
                raise Exception("Error al crear transmisión")
            
            stream_data = {
                "rtmp": stream_info['rtmp'],
                "start_time": stream_info['scheduled_start'],
                "video": video,
                "audio": audio,
                "broadcast_id": stream_info['broadcast_id'],
                "stream_id": stream_info['stream_id']
            }
            
            stream_thread = threading.Thread(
                target=manejar_transmision,
                args=(stream_data, youtube, gestor),
                daemon=True
            )
            stream_thread.start()
            stream_thread.join()
            
            logging.info("⏳ Esperando 5 minutos...")
            time.sleep(300)
            
        except Exception as e:
            logging.error(f"Error crítico: {str(e)}")
            gestor.limpiar_cache()
            limpiar_tmp()
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    logging.info("🎬 Iniciando servicio...")
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
