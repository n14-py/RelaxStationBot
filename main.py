import os
import random
import subprocess
import logging
import time
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
            output_path = "/tmp/miniatura_nueva.jpg"
            subprocess.run([
                "ffmpeg",
                "-y", "-ss", "00:00:10",
                "-i", video_url,
                "-vframes", "1",
                "-q:v", "2",
                "-vf", "scale=1280:720,setsar=1",
                output_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path
        except Exception as e:
            logging.error(f"Error generando miniatura: {str(e)}")
            return None
    
    def crear_transmision(self, titulo, video_url):
        try:
            scheduled_start = datetime.utcnow() + timedelta(minutes=15)
            
            broadcast = self.youtube.liveBroadcasts().insert(
                part="snippet,status",
                body={
                  "snippet": {
                    "title": titulo,
                    "description": "...",  # Mantener descripción original
                    "scheduledStartTime": scheduled_start.isoformat() + "Z"
                  },
                  "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                    "enableAutoStart": False,  # Deshabilitar auto-start
                    "enableAutoStop": False,   # Deshabilitar auto-stop
                    "enableArchive": True,
                    "lifeCycleStatus": "created"  # Estado inicial
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
                self.youtube.thumbnails().set(
                    videoId=broadcast['id'],
                    media_body=thumbnail_path
                ).execute()
                os.remove(thumbnail_path)
            
            return {
                "rtmp": f"{rtmp_url}/{stream_name}",
                "scheduled_start": scheduled_start,
                "broadcast_id": broadcast['id']
            }
        except Exception as e:
            logging.error(f"Error creando transmisión: {str(e)}")
            return None
    
    def iniciar_transmision(self, broadcast_id):
        max_intentos = 6
        espera_base = 10
        
        for intento in range(max_intentos):
            try:
                self.youtube.liveBroadcasts().transition(
                    broadcastStatus="live",
                    id=broadcast_id,
                    part="id,status"
                ).execute()
                return True
            except Exception as e:
                if intento < max_intentos - 1:
                    espera = espera_base * (2 ** intento)
                    logging.warning(f"Intento {intento + 1} fallido. Reintentando en {espera} segundos...")
                    time.sleep(espera)
                else:
                    logging.error(f"Error iniciando transmisión después de {max_intentos} intentos: {str(e)}")
                    return False

def determinar_categoria(nombre_video):
    nombre = nombre_video.lower()
    for categoria, palabras in PALABRAS_CLAVE.items():
        if any(palabra in nombre for palabra in palabras):
            return categoria
    return random.choice(list(PALABRAS_CLAVE.keys()))

def generar_titulo(nombre_video, categoria):
    ubicaciones = {
        'departamento': ['Departamento Acogedor', 'Loft Moderno', 'Ático con Vista', 'Estudio Minimalista'],
        'cabaña': ['Cabaña en el Bosque', 'Refugio Montañoso', 'Chalet de Madera', 'Cabaña junto al Lago'],
        'cueva': ['Cueva con Acogedor', 'Gruta Acogedora', 'Cueva con Chimenea', 'Casa Cueva Moderna'],
        'selva': ['Cabaña en la Selva', 'Refugio Tropical', 'Habitación en la Jungla', 'Casa del Árbol'],
        'default': ['Entorno Relajante', 'Espacio Zen', 'Lugar de Paz', 'Refugio Natural']
    }
    
    ubicacion_keys = {
        'departamento': ['departamento', 'loft', 'ático', 'estudio', 'apartamento'],
        'cabaña': ['cabaña', 'chalet', 'madera', 'bosque', 'lago'],
        'cueva': ['cueva', 'gruta', 'caverna', 'roca'],
        'selva': ['selva', 'jungla', 'tropical', 'palmeras']
    }
    
    actividades = [
        ('Dormir', '🌙'), ('Estudiar', '📚'), ('Meditar', '🧘♂️'), 
        ('Trabajar', '💻'), ('Desestresarse', '😌'), ('Concentrarse', '🎯')
    ]
    
    beneficios = [
        'Aliviar el Insomnio', 'Reducir la Ansiedad', 'Mejorar la Concentración',
        'Relajación Profunda', 'Conexión con la Naturaleza', 'Sueño Reparador',
        'Calma Interior'
    ]

    ubicacion_tipo = 'default'
    nombre = nombre_video.lower()
    for key, words in ubicacion_keys.items():
        if any(palabra in nombre for palabra in words):
            ubicacion_tipo = key
            break
            
    ubicacion = random.choice(ubicaciones.get(ubicacion_tipo, ubicaciones['default']))
    actividad, emoji_act = random.choice(actividades)
    beneficio = random.choice(beneficios)
    
    plantillas = [
        f"{ubicacion} • Sonidos de {categoria.capitalize()} para {actividad} {emoji_act} | {beneficio}",
        f"{actividad} {emoji_act} con Sonidos de {categoria.capitalize()} en {ubicacion} | {beneficio}",
        f"{beneficio} • {ubicacion} con Ambiente de {categoria.capitalize()} {emoji_act}",
        f"Relájate en {ubicacion} • {categoria.capitalize()} para {actividad} {emoji_act} | {beneficio}"
    ]
    
    return random.choice(plantillas)

def manejar_transmision(stream_data, youtube):
       try:
        # Transición a TESTING primero
        logging.info("🟡 Transicionando a estado TESTING...")
        if not youtube.transicionar_estado("testing", stream_data['broadcast_id']):
            raise Exception("No se pudo iniciar estado testing")
        
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-rtbufsize", "100M",
            "-re",
            "-stream_loop", "-1",
            "-i", stream_data['video']['url'],
            "-stream_loop", "-1",
            "-i", stream_data['audio']['local_path'],
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
            "-flush_packets", "1",
            "-c:a", "aac",
            "-b:a", "96k",
            "-ar", "44100",
            "-f", "flv",
            stream_data['rtmp']
        ]
        
        proceso = subprocess.Popen(cmd)
        logging.info("🟢 FFmpeg iniciado - Transmitiendo a estado TESTING...")

        # Calcular tiempo restante hasta el inicio programado
        ahora = datetime.utcnow()
        tiempo_espera = (stream_data['start_time'] - ahora).total_seconds()
        
        if tiempo_espera > 0:
            logging.info(f"⏳ Esperando {tiempo_espera:.0f} segundos para transición a LIVE...")
            time.sleep(tiempo_espera)

        # Transición a LIVE
        logging.info("🟡 Transicionando a estado LIVE...")
        if youtube.transicionar_estado("live", stream_data['broadcast_id']):
            logging.info("🎥 Transmisión LIVE iniciada con éxito")
        else:
            raise Exception("No se pudo iniciar transmisión LIVE")

        # Monitorear transmisión por 8 horas
        tiempo_inicio = datetime.utcnow()
        while (datetime.utcnow() - tiempo_inicio) < timedelta(hours=8):
            if proceso.poll() is not None:
                logging.warning("⚡ Reconectando FFmpeg...")
                proceso.kill()
                proceso = subprocess.Popen(cmd)
            time.sleep(15)
        
        proceso.kill()
        logging.info("🛑 Transmisión completada (8 horas)")

       except Exception as e:
        logging.error(f"Error en hilo de transmisión: {str(e)}")



class YouTubeManager:
    def transicionar_estado(self, estado, broadcast_id):
        max_intentos = 6
        espera_base = 10
        
        for intento in range(max_intentos):
            try:
                self.youtube.liveBroadcasts().transition(
                    broadcastStatus=estado,
                    id=broadcast_id,
                    part="id,status"
                ).execute()
                return True
            except Exception as e:
                if intento < max_intentos - 1:
                    espera = espera_base * (2 ** intento)
                    logging.warning(f"Intento {intento + 1} fallido. Reintentando en {espera} segundos...")
                    time.sleep(espera)
                else:
                    logging.error(f"Error transicionando a {estado}: {str(e)}")
                    return False


def ciclo_transmision():
    gestor = GestorContenido()
    youtube = YouTubeManager()
    
    current_stream = None
    next_stream = None
    
    while True:
        try:
            if not current_stream:
                video = random.choice(gestor.medios['videos'])
                categoria = determinar_categoria(video['name'])
                
                # Filtrar audios por categoría del video (MODIFICACIÓN CLAVE)
                audios_compatibles = [
                    a for a in gestor.medios['sonidos_naturaleza'] 
                    if a['local_path'] and categoria in a['name'].lower()
                ]
                
                # Si no hay coincidencias, ampliar búsqueda
                if not audios_compatibles:
                    audios_compatibles = [
                        a for a in gestor.medios['sonidos_naturaleza']
                        if a['local_path'] and categoria in determinar_categoria(a['name'])
                    ]
                
                # Si sigue sin haber resultados, usar todos los audios disponibles
                if not audios_compatibles:
                    audios_compatibles = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                
                audio = random.choice(audios_compatibles)
                
                titulo = generar_titulo(video['name'], categoria)
                
                stream_info = youtube.crear_transmision(titulo, video['url'])
                if not stream_info:
                    raise Exception("No se pudo crear transmisión YouTube")
                
                logging.info(f"""
                🚀 NUEVA TRANSMISIÓN PROGRAMADA 🚀
                📍 Ubicación: {video.get('name', 'Desconocido')}
                🌳 Categoría: {categoria}
                🔊 Sonido: {audio.get('name', 'Desconocido')}
                🏷️ Título: {titulo}
                ⏰ Inicio: {stream_info['scheduled_start'].strftime('%Y-%m-%d %H:%M:%S UTC')}
                """)
                
                current_stream = {
                    "rtmp": stream_info['rtmp'],
                    "start_time": stream_info['scheduled_start'],
                    "video": video,
                    "audio": audio,
                    "broadcast_id": stream_info['broadcast_id'],
                    "end_time": stream_info['scheduled_start'] + timedelta(hours=8)
                }

                threading.Thread(
                    target=manejar_transmision,
                    args=(current_stream, youtube),
                    daemon=True
                ).start()
                
                next_stream_time = current_stream['start_time'] + timedelta(hours=7, minutes=45)
            
            else:
                if datetime.utcnow() >= next_stream_time and not next_stream:
                    video = random.choice(gestor.medios['videos'])
                    categoria = determinar_categoria(video['name'])
                    audios = [a for a in gestor.medios['sonidos_naturaleza'] if a['local_path']]
                    audio = random.choice(audios)
                    titulo = generar_titulo(video['name'], categoria)
                    
                    stream_info = youtube.crear_transmision(titulo, video['url'])
                    if stream_info:
                        next_stream = {
                            "rtmp": stream_info['rtmp'],
                            "start_time": stream_info['scheduled_start'],
                            "video": video,
                            "audio": audio,
                            "broadcast_id": stream_info['broadcast_id'],
                            "end_time": stream_info['scheduled_start'] + timedelta(hours=8)
                        }
                        logging.info(f"🔜 Nueva transmisión programada: {stream_info['scheduled_start']}")
                
                if datetime.utcnow() >= current_stream['end_time']:
                    if next_stream:
                        threading.Thread(
                            target=manejar_transmision,
                            args=(next_stream, youtube),
                            daemon=True
                        ).start()
                    current_stream = next_stream
                    next_stream = None
                    logging.info("🔄 Rotando a la próxima transmisión...")
                
                time.sleep(15)
        
        except Exception as e:
            logging.error(f"🔥 Error crítico: {str(e)}")
            current_stream = None
            next_stream = None
            time.sleep(60)

@app.route('/health')
def health_check():
    return "OK", 200


if __name__ == "__main__":
    logging.info("🎬 Iniciando servicio de streaming...")
    threading.Thread(target=ciclo_transmision, daemon=True).start()
    serve(app, host='0.0.0.0', port=10000)
