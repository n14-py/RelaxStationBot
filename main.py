FROM python:3.9-slim

# 1. Habilitar repositorios necesarios
RUN sed -i 's/main/main contrib non-free/' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    gnupg \
    software-properties-common

# 2. Añadir repositorio deb-multimedia para codecs
RUN echo "deb http://www.deb-multimedia.org buster main non-free" >> /etc/apt/sources.list && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 5C808C2B65558117 && \
    apt-get update

# 3. Instalar dependencias principales
RUN apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    libx264-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Continuar con el resto de la configuración...
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p videos musica_jazz
CMD ["python", "-u", "main.py"]
