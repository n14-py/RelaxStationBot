# Usa una imagen base de Node.js
FROM node:16

# Instalar FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar los archivos del proyecto al contenedor
COPY . /app

# Instalar las dependencias de Node.js
RUN npm install

# Exponer el puerto que usará la aplicación (por ejemplo, el 3000)
EXPOSE 3000

# Comando para ejecutar la aplicación
CMD ["npm", "start"]
