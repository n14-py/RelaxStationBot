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
    
    def convertir_audio(self, input_path):
        output_path = os.path.splitext(input_path)[0] + "_converted.aac"
        if os.path.exists(output_path):
            return output_path
            
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", input_path,
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
                "-hide_banner", "-loglevel", "error",
                output_path
            ], check=True)
            return output_path
        except Exception as e:
            logging.error(f"Error convirtiendo audio: {str(e)}")
            return None

    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            extension = os.path.splitext(urlparse(url).path)[1]
            nombre_archivo = f"{nombre_hash}{extension if extension else '.mp3'}"
            ruta_local = os.path.join(self.media_cache_dir, nombre_archivo)
            
            if os.path.exists(ruta_local) and os.path.getsize(ruta_local) > 1024:
                return self.convertir_audio(ruta_local)
            
            respuesta = requests.get(url, stream=True, timeout=30)
            respuesta.raise_for_status()
            
            with open(ruta_local, 'wb') as f:
                for chunk in respuesta.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return self.convertir_audio(ruta_local)
        except Exception as e:
            logging.error(f"Error descargando {url}: {str(e)}")
            return None

    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            for categoria in ['musica', 'sonidos_naturaleza']:
                for medio in datos[categoria]:
                    local_path = self.descargar_audio(medio['url'])
                    medio['local_path'] = local_path if local_path and os.path.exists(local_path) else None
            
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
                "ffmpeg", "-y",
                "-ss", "00:00:01",
                "-i", video_url,
                "-vframes", "1",
                "-q:v", "2",
                "-hide_banner",
                "-loglevel", "error",
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

def generar_titulo(nombre_video, fase, tema):
    ubicacion = next((p for p in ['Cabaña', 'Sala', 'Cueva', 'Montaña', 'Departamento', 'Cafetería'] if p.lower() in nombre_video.lower()), 'Entorno')
    
    if fase == 0:
        return f"{ubicacion} • Música Relajante 🌿 24/7"
    elif fase == 1:
        return f"{ubicacion} • Sonidos de {tema.capitalize()} 🌿 24/7"
    else:
        return f"{ubicacion} • Música y Sonidos de {tema.capitalize()} 🌿 24/7"

def obtener_tema(nombre_video):
    nombre = nombre_video.lower()
    for tema, palabras in PALABRAS_CLAVE.items():
        if any(p in nombre for p in palabras):
            return tema
    return 'Naturaleza'

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    fase_actual = random.choice([0, 1, 2])
    tiempo_inicio_fase = time.time()
    tema_actual = "Naturaleza"
    
    while True:
        try:
            # Verificar si debe cambiar de fase
            if (time.time() - tiempo_inicio_fase) >= 28800:  # 8 horas
                fase_actual = random.choice([0, 1, 2])
                tiempo_inicio_fase = time.time()
            
            # Seleccionar contenido
            video = random.choice(gestor.medios['videos'])
            tema_actual = obtener_tema(video['name'])
            
            # Configurar contenido según fase
            if fase_actual == 0:  # Solo música
                audios = [a for a in gestor.medios['musica'] if a['local_path']]
                filtro_audio = "[1:a]volume=0.8[audio]"
                map_audio = "[audio]"
                inputs = 1
            elif fase_actual == 1:  # Solo naturaleza
                audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path'] and tema_actual in a['name'].lower()]
                filtro_audio = "[1:a]volume=0.8[audio]"
                map_audio = "[audio]"
                inputs = 1
            else:  # Combinado
                musica = [a for a in gestor.medios['musica'] if a['local_path']]
                naturaleza = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path'] and tema_actual in a['name'].lower()]
                if not musica or not naturaleza:
                    continue
                audios = musica + naturaleza
                filtro_audio = "[1:a]volume=0.4[mus];[2:a]volume=0.8[nat];[mus][nat]amix=inputs=2:duration=longest[audio]"
                map_audio = "[audio]"
                inputs = 2
            
            if not audios:
                continue
            
            # Generar playlist
            playlist_path = "/tmp/playlist.txt"
            with open(playlist_path, 'w') as f:
                for audio in audios[:inputs]:
                    f.write(f"file '{audio['local_path']}'\n")
            
            # Generar título
            titulo = generar_titulo(video['name'], fase_actual, tema_actual)
            
            # Actualizar YouTube
            if youtube.youtube:
                youtube.actualizar_transmision(titulo, video['url'])
            
            # Construir comando FFmpeg
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video['url'],
                "-f", "concat",
                "-safe", "0",
                "-stream_loop", "-1",
                "-i", playlist_path,
            ]
            
            if fase_actual == 2:
                cmd += ["-i", naturaleza[0]['local_path']]
            
            cmd += [
                "-filter_complex", filtro_audio,
                "-map", "0:v:0",
                "-map", map_audio,
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
            
            # Log detallado
            logging.info(f"""
            🎬 INICIANDO TRANSMISIÓN 🎬
            📺 Video: {video['name']}
            🎵 Fase: {'Música' if fase_actual == 0 else 'Naturaleza' if fase_actual == 1 else 'Combinado'}
            🌿 Tema: {tema_actual.capitalize()}
            🎶 Audios: {len(audios)} pistas
            🏷️ Título: {titulo}
            ⏳ Duración: 8 horas
            """)
            
            proceso = subprocess.Popen(cmd)
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
    import threading
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
