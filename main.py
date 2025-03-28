import os
import random
import subprocess
import logging
import time
import requests
import hashlib
import threading
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
    level=logging.DEBUG,  # Cambiado a DEBUG para más detalles
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
    
    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            ruta_local = os.path.join(self.media_cache_dir, f"{nombre_hash}.wav")
            
            if os.path.exists(ruta_local):
                return ruta_local
            
            temp_path = os.path.join(self.media_cache_dir, f"temp_{nombre_hash}")
            
            respuesta = requests.get(url, stream=True, timeout=30)
            respuesta.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in respuesta.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            subprocess.run([
                "ffmpeg",
                "-y", "-i", temp_path,
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                ruta_local
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if not os.path.exists(ruta_local):  # Nueva verificación
                raise Exception(f"Error de conversión: {url}")
            
            os.remove(temp_path)
            return ruta_local
        except Exception as e:
            logging.error(f"Error procesando {url}: {str(e)}")
            return None

    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            for medio in datos['sonidos_naturaleza']:
                medio['local_path'] = self.descargar_audio(medio['url'])
            
            logging.info("✅ Medios verificados y listos")
            return datos
        except Exception as e:
            logging.error(f"Error cargando medios: {str(e)}")
            return {"videos": [], "sonidos_naturaleza": []}

class YouTubeManager:
    def __init__(self):
        self.youtube = self.autenticar()
    
    def autenticar(self):
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
    
    def actualizar_transmision(self, titulo, video_url):
        try:
            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="active"
            ).execute()
            
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
            
            logging.info(f"Título actualizado: {titulo}")
        except Exception as e:
            logging.error(f"Error YouTube: {str(e)}")

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

def ejecutar_transmision(video, audio):
    try:
        # Crear listas de reproducción
        with open("video.lst", "w") as f:
            f.write(f"file '{video['url']}'\n" * 1000)
            
        with open("audio.lst", "w") as f:
            f.write(f"file '{audio['local_path']}'\n" * 1000)

cmd = [
    "ffmpeg",
    "-loglevel", "warning",  # Reduce la cantidad de logs para ahorrar recursos
    "-re",
    "-f", "concat",
    "-safe", "0",
    "-protocol_whitelist", "file,http,https,tcp,tls",
    "-stream_loop", "-1",
    "-i", "video.lst",
    "-f", "concat",
    "-safe", "0",
    "-stream_loop", "-1",
    "-i", "audio.lst",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-vf", "scale=1280:720:force_original_aspect_ratio=decrease",  # Reducir resolución si es necesario
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-b:v", "1200k",
    "-maxrate", "1500k",
    "-bufsize", "2500k",
    "-g", "240",
    "-r", "30",  # Mantener 30 FPS para estabilidad
    "-c:a", "aac",
    "-b:a", "96k",  # Reducir el bitrate de audio para ahorrar recursos
    "-ar", "44100",
    "-f", "flv",
    RTMP_URL
]

        
        proceso = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Logs de FFmpeg en tiempo real
        def leer_logs():
            while True:
                output = proceso.stdout.readline()
                if output == '' and proceso.poll() is not None:
                    break
                if output:
                    logging.debug(output.strip())
        
        threading.Thread(target=leer_logs, daemon=True).start()
        
        # Temporizador de 8 horas
        start_time = time.time()
        while proceso.poll() is None:
            if time.time() - start_time >= 28800:
                proceso.terminate()
                logging.info("🕒 Transmisión finalizada por tiempo")
                break
            time.sleep(60)
            
        return True
        
    except Exception as e:
        logging.error(f"Error FFmpeg: {str(e)}")
        return False
    finally:
        for archivo in ["video.lst", "audio.lst"]:
            if os.path.exists(archivo):
                os.remove(archivo)

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    while True:
        try:
            video = random.choice(gestor.medios['videos'])
            categoria = determinar_categoria(video['name'])
            audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
            
            audios_filtrados = [a for a in audios if any(p in a['name'].lower() for p in PALABRAS_CLAVE[categoria])]
            audio = random.choice(audios_filtrados) if audios_filtrados else random.choice(audios)
            
            titulo = generar_titulo(video['name'], categoria)
            
            def actualizar_titulo():
                time.sleep(300)
                youtube.actualizar_transmision(titulo, video['url'])
            
            threading.Thread(target=actualizar_titulo, daemon=True).start()
            
            logging.info(f"""
            🎬 INICIANDO TRANSMISIÓN 🎬
            📺 Video: {video['name']}
            🔉 Audio: {audio['name']}
            🌿 Categoría: {categoria}
            🏷️ Título: {titulo}
            ⏳ Duración: 8 horas
            """)
            
            if ejecutar_transmision(video, audio):
                logging.info("🔄 Reiniciando transmisión en 1 minuto...")
                time.sleep(60)
            
        except Exception as e:
            logging.error(f"Error general: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
