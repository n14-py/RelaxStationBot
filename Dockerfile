FROM python:3.9

# Instalar FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copiar archivos al contenedor
WORKDIR /app
COPY . /app

# Instalar dependencias
RUN pip install -r requirements.txt

# Ejecutar el script
CMD ["python", "main.py"]
