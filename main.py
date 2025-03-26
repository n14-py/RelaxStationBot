import os
import random
import subprocess
import logging
import time
import requests
import hashlib
import threading
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
            ], check=True, timeout=30)
            return output_path
        except subprocess.TimeoutExpired:
            logging.warning("Timeout generando miniatura")
            return None
        except Exception as e:
            logging.error(f"Error generando miniatura: {str(e)}")
            return None
    
    def actualizar_transmision(self, titulo, video_url):
        try:
            if not self.youtube:
                logging.warning("No hay conexión con YouTube, omitiendo actualización")
                return
            
            # Generar miniatura en segundo plano
            def actualizar_miniatura_async(broadcast_id):
                try:
                    thumbnail_path = self.generar_miniatura(video_url)
                    if thumbnail_path:
                        self.youtube.thumbnails().set(
                            videoId=broadcast_id,
                            media_body=thumbnail_path
                        ).execute()
                        os.remove(thumbnail_path)
                except Exception as e:
                    logging.error(f"Error en miniatura: {str(e)}")

            broadcasts = self.youtube.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="active"
            ).execute()
            
            if not broadcasts.get('items'):
                logging.warning("No hay transmisión activa en YouTube, omitiendo actualización")
                return
            
            broadcast_id = broadcasts['items'][0]['id']
            
            # Actualizar título primero
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
            
            # Miniatura en segundo plano
            threading.Thread(target=actualizar_miniatura_async, args=(broadcast_id,), daemon=True).start()
            
            logging.info(f"Título YouTube actualizado: {titulo}")
        except Exception as e:
            logging.error(f"Error actualizando YouTube (no crítico): {str(e)}")

def generar_titulo(nombre_video, fase, sonido_natural=None):
    nombre = nombre_video.lower()
    ubicacion = next((p for p in ['Cabaña', 'Sala', 'Cueva', 'Montaña', 'Departamento', 'Cafetería'] if p.lower() in nombre), 'Entorno')
    
    if fase == 0:  # Música
        return f"{ubicacion} • Música Relajante 🌿 24/7"
    elif fase == 1:  # Naturaleza
        tema = sonido_natural if sonido_natural else next((t for t, keys in PALABRAS_CLAVE.items() if any(k in nombre for k in keys)), 'Naturaleza')
        return f"{ubicacion} • Sonidos de {tema.capitalize()} 🌿 24/7"
    else:  # Combinado
        tema = sonido_natural if sonido_natural else next((t for t, keys in PALABRAS_CLAVE.items() if any(k in nombre for k in keys)), 'Naturaleza')
        return f"{ubicacion} • Música y Sonidos de {tema.capitalize()} 🌿 24/7"

def crear_playlist_musica(audios_musica, duracion_horas=8):
    """Crea una playlist de música aleatoria para la duración especificada"""
    playlist_path = "/tmp/playlist_musica.txt"
    tiempo_total = duracion_horas * 3600  # Convertir a segundos
    tiempo_actual = 0
    
    with open(playlist_path, 'w') as f:
        while tiempo_actual < tiempo_total:
            audio = random.choice(audios_musica)
            if audio['local_path']:
                f.write(f"file '{os.path.abspath(audio['local_path'])}'\n")
                # Asumimos 3 minutos por canción
                tiempo_actual += 180
    
    return playlist_path

def iniciar_transmision_ffmpeg(cmd):
    """Inicia la transmisión FFmpeg y verifica que esté activa"""
    proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Esperar un momento para ver si falla inmediatamente
    time.sleep(10)
    
    if proceso.poll() is not None:
        # El proceso terminó prematuramente
        _, stderr = proceso.communicate()
        logging.error(f"FFmpeg falló al iniciar: {stderr.decode()}")
        return None
    
    return proceso

def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    while True:
        try:
            # Seleccionar fase
            fase = random.choice([0, 1, 2])  # 0=Música, 1=Naturaleza, 2=Combinado
            video = random.choice(gestor.medios['videos'])
            
            # Configurar contenido según fase
            sonido_natural = None
            if fase == 0:  # Solo música
                audios_musica = [a for a in gestor.medios['musica'] if a['local_path']]
                playlist_musica = crear_playlist_musica(audios_musica)
                playlist_naturaleza = None
                tipo_contenido = "Música Relajante"
                
            elif fase == 1:  # Solo naturaleza
                audios_naturaleza = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                audio_natural = random.choice(audios_naturaleza)
                sonido_natural = next((t for t, keys in PALABRAS_CLAVE.items() if any(k in audio_natural['name'].lower() for k in keys)), 'Naturaleza')
                
                # Crear playlist con el mismo sonido natural en bucle
                playlist_naturaleza = "/tmp/playlist_naturaleza.txt"
                with open(playlist_naturaleza, 'w') as f:
                    f.write(f"file '{os.path.abspath(audio_natural['local_path'])}'\n")
                
                playlist_musica = None
                tipo_contenido = f"Sonidos de {sonido_natural.capitalize()}"
                
            else:  # Combinado
                audios_musica = [a for a in gestor.medios['musica'] if a['local_path']]
                audios_naturaleza = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                audio_natural = random.choice(audios_naturaleza)
                sonido_natural = next((t for t, keys in PALABRAS_CLAVE.items() if any(k in audio_natural['name'].lower() for k in keys)), 'Naturaleza')
                
                # Playlist para música (aleatoria)
                playlist_musica = crear_playlist_musica(audios_musica)
                
                # Playlist para sonido natural (bucle)
                playlist_naturaleza = "/tmp/playlist_naturaleza.txt"
                with open(playlist_naturaleza, 'w') as f:
                    f.write(f"file '{os.path.abspath(audio_natural['local_path'])}'\n")
                
                tipo_contenido = f"Música y Sonidos de {sonido_natural.capitalize()}"
            
            # Generar título definitivo
            titulo_definitivo = generar_titulo(video['name'], fase, sonido_natural)
            
            # Comando FFmpeg
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",  # Bucle infinito para el video
                "-i", video['url'],
            ]
            
            # Configuración de audio según fase
            if fase == 0:  # Solo música
                cmd.extend([
                    "-f", "concat",
                    "-safe", "0",
                    "-stream_loop", "-1",
                    "-i", playlist_musica,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                ])
            elif fase == 1:  # Solo naturaleza
                cmd.extend([
                    "-f", "concat",
                    "-safe", "0",
                    "-stream_loop", "-1",
                    "-i", playlist_naturaleza,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                ])
            else:  # Combinado
                cmd.extend([
                    "-f", "concat",
                    "-safe", "0",
                    "-stream_loop", "-1",
                    "-i", playlist_naturaleza,
                    "-f", "concat",
                    "-safe", "0",
                    "-i", playlist_musica,
                    "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=3[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                ])
            
            # Configuración común
            cmd.extend([
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
            ])
            
            # Iniciar transmisión
            logging.info(f"""
            🚀 INICIANDO TRANSMISIÓN 🚀
            📺 Video: {video['name']} (en bucle)
            🎵 Tipo: {tipo_contenido}
            {'🎶 Música: Aleatoria' if fase in [0, 2] else ''}
            {'🌿 Sonido natural: ' + sonido_natural.capitalize() if fase in [1, 2] else ''}
            🏷️ Título: {titulo_definitivo}
            ⏳ Duración: 8 horas
            """)
            
            proceso = iniciar_transmision_ffmpeg(cmd)
            if proceso is None:
                raise Exception("No se pudo iniciar FFmpeg")
            
            # Esperar 30 segundos para que el stream esté estable
            time.sleep(30)
            
            # Actualizar título de YouTube (en segundo plano)
            threading.Thread(
                target=youtube.actualizar_transmision,
                args=(titulo_definitivo, video['url']),
                daemon=True
            ).start()
            
            # Esperar a que termine el stream (8 horas)
            proceso.wait()
            
            # Limpieza
            for playlist in [playlist_musica, playlist_naturaleza]:
                if playlist and os.path.exists(playlist):
                    os.remove(playlist)
            
            # Esperar antes de reiniciar
            logging.info("Transmisión completada. Esperando 60 segundos antes de reiniciar...")
            time.sleep(60)
            
        except Exception as e:
            logging.error(f"Error en transmisión: {str(e)}")
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    # Iniciar transmisión en segundo plano
    transmision_thread = threading.Thread(target=ciclo_transmision, daemon=True)
    transmision_thread.start()
    
    # Iniciar servidor web
    serve(app, host='0.0.0.0', port=10000)
