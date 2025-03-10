# Usa Node.js como base
FROM node:16

# Instalar FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar archivos necesarios para instalar dependencias primero
COPY package.json package-lock.json /app/

# Instalar dependencias
RUN npm install

# Copiar el resto de los archivos del proyecto
COPY . /app

# Exponer el puerto (ajústalo según tu configuración)
EXPOSE 3000

# Comando para iniciar el servidor
CMD ["npm", "start"]
