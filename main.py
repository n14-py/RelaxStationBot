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
    
    def obtener_extension_segura(self, url):
        try:
            parsed = urlparse(url)
            path = parsed.path
            extension = os.path.splitext(path)[1]
            return extension if extension else '.mp3'
        except:
            return '.mp3'

    def descargar_audio(self, url):
        try:
            nombre_hash = hashlib.md5(url.encode()).hexdigest()
            extension = self.obtener_extension_segura(url)
            nombre_archivo = f"{nombre_hash}{extension}"
            ruta_local = os.path.join(self.media_cache_dir, nombre_archivo)
            
            if os.path.exists(ruta_local) and os.path.getsize(ruta_local) > 1024:
                return ruta_local
            
            respuesta = requests.get(url, stream=True, timeout=30)
            respuesta.raise_for_status()
            
            with open(ruta_local, 'wb') as f:
                for chunk in respuesta.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if os.path.getsize(ruta_local) == 0:
                raise ValueError("Archivo descargado vacío")
            
            return ruta_local
        except Exception as e:
            logging.error(f"Error descargando {url}: {str(e)}")
            return None

    def cargar_medios(self):
        try:
            respuesta = requests.get(MEDIOS_URL, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            
            if not all(key in datos for key in ["videos", "musica", "sonidos_naturaleza"]):
                raise ValueError("Estructura JSON inválida")
            
            for medio in datos['musica'] + datos['sonidos_naturaleza']:
                local_path = self.descargar_audio(medio['url'])
                if local_path and os.path.exists(local_path):
                    medio['local_path'] = local_path
                else:
                    medio['local_path'] = None
            
            logging.info("✅ Medios verificados y listos")
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

def generar_titulo(nombre_video, fase):
    nombre = nombre_video.lower()
    ubicacion = next((p for p in ['Cabaña', 'Sala', 'Cueva', 'Montaña', 'Departamento', 'Cafetería'] if p.lower() in nombre), 'Entorno')
    
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
            # Selección de fase y video
            fase = random.choice([0, 1, 2])
            video = random.choice(gestor.medios['videos'])
            logging.info(f"🎥 Video seleccionado: {video['name']}")
            logging.info(f"🔁 Fase seleccionada: {fase}")

            # Configuración de contenido
            if fase == 0:
                audios = [a for a in gestor.medios['musica'] if a['local_path']]
                tipo_contenido = "Música Relajante"
            elif fase == 1:
                audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                tipo_contenido = "Sonidos de Naturaleza"
            else:
                # Fase combinada
                naturaleza = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                if not naturaleza:
                    raise ValueError("No hay sonidos de naturaleza")
                naturaleza_audio = random.choice(naturaleza)
                musica = [a for a in gestor.medios['musica'] if a['local_path']]
                random.shuffle(musica)
                tipo_contenido = "Combinado Música/Naturaleza"

            if fase != 2 and (not audios or len(audios) == 0):
                logging.error("No hay audios disponibles")
                time.sleep(60)
                continue

            # Generar playlists
            if fase == 2:
                # Playlist para sonido de naturaleza en bucle
                playlist_naturaleza = "/tmp/naturaleza.txt"
                with open(playlist_naturaleza, 'w') as f:
                    f.write(f"file '{naturaleza_audio['local_path']}'\n")
                
                # Playlist para música aleatoria
                playlist_musica = "/tmp/musica.txt"
                with open(playlist_musica, 'w') as f:
                    for track in musica:
                        f.write(f"file '{track['local_path']}'\n")
            else:
                playlist_path = "/tmp/playlist.txt"
                with open(playlist_path, 'w') as f:
                    for audio in audios:
                        f.write(f"file '{audio['local_path']}'\n")

            # Generar título
            titulo = generar_titulo(video['name'], fase)
            logging.info(f"🏷️ Título generado: {titulo}")

            # Construir comando FFmpeg
            if fase == 2:
                cmd = [
                    "ffmpeg",
                    "-loglevel", "error",
                    "-re",
                    "-stream_loop", "-1",
                    "-i", video['url'],
                    "-f", "concat",
                    "-safe", "0",
                    "-stream_loop", "-1",
                    "-i", playlist_naturaleza,
                    "-f", "concat",
                    "-safe", "0",
                    "-i", playlist_musica,
                    "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest[a]",
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
            else:
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

            # Iniciar transmisión
            logging.info("🚀 Iniciando stream...")
            proceso = subprocess.Popen(cmd)
            
            # Esperar 30 segundos para asegurar conexión
            time.sleep(30)
            logging.info("🔴 Stream activo")
            
            # Actualizar YouTube después de iniciar
            if youtube.youtube:
                logging.info("🔄 Actualizando título en YouTube...")
                youtube.actualizar_transmision(titulo, video['url'])

            # Esperar finalización
            proceso.wait()
            logging.info("⏹️ Transmisión finalizada. Reiniciando...")

            # Limpiar archivos temporales
            if fase == 2:
                os.remove(playlist_naturaleza)
                os.remove(playlist_musica)
            else:
                os.remove(playlist_path)

        except Exception as e:
            logging.error(f"Error en ciclo: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    import threading
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
