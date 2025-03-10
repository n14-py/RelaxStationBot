FROM python:3.9-slim

# 1. Configurar repositorios esenciales
RUN echo "deb http://deb.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security buster/updates main contrib non-free" >> /etc/apt/sources.list

# 2. Instalar dependencias base
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 3. Instalar Node.js 18.x (LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# 4. Verificar instalación
RUN node -v && npm -v  # Debe mostrar: v18.x y 9.x

# 5. Continuar con configuración Python...
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 6. Variables críticas
ENV PYTHONUNBUFFERED=1
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libgomp.so.1

EXPOSE 3000

CMD ["sh", "-c", "python -u main.py & node server.js"]
