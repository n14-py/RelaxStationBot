# Usa Python 3.9 como base
FROM python:3.9

# Instalar FFmpeg y Node.js
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y nodejs

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar archivos necesarios
COPY package.json package.json /app/
COPY requirements.txt /app/

# Instalar dependencias de Python y Node.js
RUN pip install -r requirements.txt
RUN npm install

# Copiar el resto de los archivos del proyecto
COPY . /app

# Exponer el puerto 3000
EXPOSE 3000

# Ejecutar Python y Node.js en paralelo
CMD ["sh", "-c", "python main.py & node server.js"]
