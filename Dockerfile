# Usa una imagen base de Node.js con Python
FROM node:16

# Instalar Python 3.9 y FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg python3.9 python3-pip && \
    ln -s /usr/bin/python3.9 /usr/bin/python

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar archivos necesarios para instalar dependencias
COPY package.json package.json /app/
COPY requirements.txt /app/

# Instalar dependencias de Node.js y Python
RUN npm install
RUN pip install -r requirements.txt

# Copiar el resto de los archivos del proyecto
COPY . /app

# Exponer el puerto (ajústalo según tu configuración)
EXPOSE 3000

# Ejecutar ambos servidores: Node.js y Python
CMD ["sh", "-c", "node server.js & python main.py"]
